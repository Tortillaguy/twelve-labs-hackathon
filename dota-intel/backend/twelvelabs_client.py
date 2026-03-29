import json
import os
import time
from pathlib import Path
import httpx
from twelvelabs import TwelveLabs

class ProgressFileReader:
    def __init__(self, filename):
        self.file = open(filename, 'rb')
        self.filename = filename
        self.size = os.path.getsize(filename)
        self.read_bytes = 0
        self.last_reported = 0

    @property
    def name(self):
        return self.filename

    def read(self, size=-1):
        chunk = self.file.read(size)
        self.read_bytes += len(chunk)
        if self.read_bytes - self.last_reported > 50 * 1024 * 1024 or self.read_bytes == self.size:
            percent = (self.read_bytes / self.size) * 100
            print(f"[tl-upload] {self.read_bytes / (1024*1024):.1f}MB / {self.size / (1024*1024):.1f}MB ({percent:.1f}%) uploaded...")
            self.last_reported = self.read_bytes
        return chunk
    
    def seek(self, offset, whence=0):
        return self.file.seek(offset, whence)
        
    def tell(self):
        return self.file.tell()

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()



# Pegasus generation uses text/summarize in 0.4.0
# The response schema for generate.text is different from analyze.

class TwelveLabsClient:
    BASE_URL = "https://api.twelvelabs.io/v1.3"

    def __init__(self, api_key: str = None, index_id: str = None):
        self._api_key = api_key or os.environ.get("TWELVELABS_API_KEY")
        if not self._api_key:
            raise ValueError("TWELVELABS_API_KEY not found in environment.")
        self._client = TwelveLabs(api_key=self._api_key)
        self.index_id = index_id or os.environ.get("TWELVELABS_INDEX_ID", "")

    def get_video_info(self, video_id: str) -> dict:
        """Return HLS stream URL and thumbnail for a video."""
        videos = list(self._client.index.video.list(self.index_id))
        for v in videos:
            if v.id == video_id:
                return {
                    "video_id": v.id,
                    "hls_url": v.hls.video_url if v.hls else None,
                    "thumbnail_url": v.hls.thumbnail_urls[0] if v.hls and v.hls.thumbnail_urls else None,
                }
        return None

    def list_videos(self) -> list[dict]:
        """Return all indexed videos with their HLS info and user_metadata."""
        videos = list(self._client.index.video.list(self.index_id))
        return [
            {
                "video_id": v.id,
                "filename": getattr(v.system_metadata, "filename", None),
                "hls_url": v.hls.video_url if v.hls else None,
                "thumbnail_url": v.hls.thumbnail_urls[0] if v.hls and v.hls.thumbnail_urls else None,
                "user_metadata": getattr(v, "user_metadata", None) or {},
            }
            for v in videos
        ]

    def update_video_metadata(self, video_id: str, user_metadata: dict) -> bool:
        """
        Retroactively attach arbitrary key/value metadata to a TwelveLabs video.
        Uses PATCH /v1.3/indexes/:index_id/videos/:video_id with user_metadata.
        Values must be str | int | float | bool (no nested objects/arrays).
        Returns True on success.
        """
        r = httpx.patch(
            f"{self.BASE_URL}/indexes/{self.index_id}/videos/{video_id}",
            headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
            json={"user_metadata": user_metadata},
            timeout=30,
        )
        r.raise_for_status()
        return True



    def get_or_create_index(self, name: str = "dota-intel") -> str:
        """Return existing index ID or create new one. Saves to self.index_id."""
        for index in self._client.index.list():
            if index.name == name:
                self.index_id = index.id
                return index.id
        index = self._client.index.create(
            name=name,
            models=[
                {"name": "marengo3.0", "options": ["visual", "audio"]}, # 0.4.0 keys
                {"name": "pegasus1.2", "options": ["visual", "audio"]},

            ]
        )

        self.index_id = index.id
        return index.id

    def upload_and_index(self, path: str) -> str:
        """
        Upload a local video file and wait for indexing to complete.
        Returns the video_id.
        """
        print(f"[tl] Starting upload & index task for {path}...")
        with ProgressFileReader(path) as f:
            task = self._client.task.create(
                index_id=self.index_id,
                file=f,
            )
        print(f"[tl] Task created: {task.id}. Waiting for processing...")

        
        # Helper method in 0.4.0 to wait
        # If not available, we poll task.retrieve
        while True:
            t = self._client.task.retrieve(task.id)
            if t.status == "ready":
                print(f"[tl] Indexing complete! video_id={t.video_id}")
                return t.video_id
            if t.status == "failed":
                raise RuntimeError("Indexing failed")
            
            # Print current processing state so user knows it's not stalled
            print(f"[tl] Task {task.id} is {t.status}...")
            time.sleep(15)

    def search_highlights(
        self,
        query: str,
        options: list[str] = None,
        page_limit: int = 10,
    ) -> list[dict]:
        """Search index for clips matching query. Returns list of clip dicts.

        Uses raw HTTP because the SDK's Pydantic models fail to deserialize
        the v1.3 search response (missing score/confidence fields).
        """
        opts = options or ["visual", "audio"]
        fields = [
            ("index_id", (None, self.index_id)),
            ("query_text", (None, query)),
            ("group_by", (None, "clip")),
            ("page_limit", (None, str(page_limit))),
        ]
        for opt in opts:
            fields.append(("search_options", (None, opt)))

        r = httpx.post(
            f"{self.BASE_URL}/search",
            headers={"x-api-key": self._api_key},
            files=fields,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json().get("data", [])

        clips = []
        for item in data:
            clips.append({
                "video_id": item.get("video_id"),
                "start": item.get("start"),
                "end": item.get("end"),
                "score": item.get("score"),
                "transcription": item.get("transcription"),
                "thumbnail_url": item.get("thumbnail_url"),
            })
        return clips

    def calibrate_game_start(self, video_id: str, first_blood_time: int = 0) -> float:
        """
        Find the game start (0:00 mark) by locating First Blood and counting backwards,
        or falling back to searching for the horn sound.
        """
        if first_blood_time > 0:
            fields = [
                ("index_id", (None, self.index_id)),
                ("query_text", (None, "First blood announcement in Dota 2")),
                ("search_options", (None, "visual")),
                ("search_options", (None, "audio")),
                ("group_by", (None, "clip")),
                ("page_limit", (None, "5")),
            ]
            try:
                r = httpx.post(
                    f"{self.BASE_URL}/search",
                    headers={"x-api-key": self._api_key},
                    files=fields,
                    timeout=30,
                )
                r.raise_for_status()
                data = r.json().get("data", [])
                for item in data:
                    if item.get("video_id") == video_id:
                        # Found first blood. The horn is exactly first_blood_time seconds earlier.
                        fb_start = item.get("start", 0)
                        horn_time = fb_start - first_blood_time
                        if horn_time > 0:
                            print(f"[tl] Found First Blood at {fb_start}s. Calculated horn at {horn_time}s.")
                            return horn_time
            except Exception as e:
                print(f"[tl] Warning in calibrate_game_start (First Blood): {e}")

        fields = [
            ("index_id", (None, self.index_id)),
            ("query_text", (None, "Dota 2 game countdown horn creep spawn sound")),
            ("search_options", (None, "audio")),
            ("group_by", (None, "clip")),
            ("page_limit", (None, "5")),
        ]
        try:
            r = httpx.post(
                f"{self.BASE_URL}/search",
                headers={"x-api-key": self._api_key},
                files=fields,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json().get("data", [])
            for item in data:
                if item.get("video_id") == video_id:
                    print(f"[tl] Found Horn sound at {item.get('start')}s.")
                    return item.get('start', 600.0)
        except Exception as e:
            print(f"[tl] Warning in calibrate_game_start (Horn): {e}")
        return 600.0

    def analyze_clip(self, video_id: str, start: float, end: float, target_player: str = None) -> dict:
        """
        Ask Pegasus to classify and score a clip at [start, end] seconds.
        Uses raw HTTP to /analyze (v1.3 NDJSON streaming endpoint).
        If target_player is provided, Pegasus is asked to focus on that player
        and check for in-game kill streak announcement banners mentioning them.
        """
        player_context = (
            f" The focus player is '{target_player}'. "
            f"Check whether in-game banners or the caster explicitly announce a kill streak "
            f"for '{target_player}' (e.g. '[{target_player}] is on a killing spree', "
            f"'[{target_player}] is dominating', '[{target_player}] RAMPAGE!'). "
            f"Also note if the caster mentions '{target_player}' positively."
        ) if target_player else ""

        prompt = (
            f"Analyze the moment from {start:.0f} to {end:.0f} seconds in this "
            f"Dota 2 broadcast.{player_context} "
            f"Return JSON with: "
            f"play_type (one of RAMPAGE, GODLIKE, TEAMFIGHT, OBJECTIVE, CLUTCH), "
            f"excitement_score (0-10 based on caster voice intensity and crowd reaction), "
            f"streak_tier (the kill streak tier announced in-game or by casters, e.g. "
            f"'killing spree', 'dominating', 'mega kill', 'ultra kill', 'rampage', "
            f"'godlike', 'beyond godlike', 'wicked sick' — or null if none), "
            f"description (one sentence focusing on what {target_player or 'the player'} did), "
            f"player_name (the player name spoken by casters or shown in an in-game banner, or null)."
        )
        try:
            r = httpx.post(
                f"{self.BASE_URL}/analyze",
                headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
                json={"video_id": video_id, "prompt": prompt, "temperature": 0.2},
                timeout=120,
            )
            r.raise_for_status()
            full_text = ""
            for line in r.text.strip().split("\n"):
                event = json.loads(line)
                if event.get("event_type") == "text_generation":
                    full_text += event.get("text", "")
            if "{" in full_text and "}" in full_text:
                json_part = full_text[full_text.find("{"):full_text.rfind("}")+1]
                return json.loads(json_part)
            return {"description": full_text.strip(), "play_type": "TEAMFIGHT", "excitement_score": 7.0}
        except Exception as e:
            print(f"[tl] Warning in analyze_clip: {e}")
            return {"description": "Highlight moment", "play_type": "TEAMFIGHT", "excitement_score": 5.0}

