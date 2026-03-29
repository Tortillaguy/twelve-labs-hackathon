import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from backend import cache
from backend.models import LeaderboardResponse, PlayerDetail, Highlight
from backend.twelvelabs_client import TwelveLabsClient
from backend.highlights import merge_and_deduplicate

app = FastAPI(title="Dota Intel API")

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-init TwelveLabs client
_tl: TwelveLabsClient | None = None

def get_tl() -> TwelveLabsClient:
    global _tl
    if _tl is None:
        _tl = TwelveLabsClient()
        _tl.get_or_create_index("dota-intel")
    return _tl


@app.get("/")
async def root():
    return {"status": "online", "project": "Dota Intel"}

@app.get("/api/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(demo: bool = False):
    lb = cache.read_leaderboard(demo=demo)
    if not lb:
        raise HTTPException(status_code=404, detail="Leaderboard not found. Run the seed script.")
    return lb

@app.get("/api/players/{account_id}")
async def get_player(account_id: int, demo: bool = False):
    detail = cache.read_player(account_id, demo=demo)
    if not detail:
        raise HTTPException(status_code=404, detail="Player not found.")
    # Enrich highlights with hls_url so the frontend can capture per-segment thumbnail frames.
    # Build a per-video cache to avoid repeated TwelveLabs calls.
    try:
        tl = get_tl()
        video_cache: dict[str, dict] = {}
        enriched = []
        for hl in detail.highlights:
            vid = hl.video_id
            if vid not in video_cache:
                video_cache[vid] = tl.get_video_info(vid) or {}
            hl_dict = hl.model_dump()
            hl_dict["hls_url"] = video_cache[vid].get("hls_url")
            enriched.append(hl_dict)
        result = detail.model_dump()
        result["highlights"] = enriched
        return result
    except Exception:
        # If TwelveLabs is unavailable, fall back to cached data without hls_url
        return detail



# ── Video & Highlight endpoints ──────────────────────────────────────────────

@app.get("/api/videos")
async def list_videos():
    """List all indexed videos with HLS streaming URLs."""
    tl = get_tl()
    videos = tl.list_videos()
    # Attach match_id from filename (match_NNNN.mp4)
    for v in videos:
        m = re.search(r"match_(\d+)", v.get("filename") or "")
        v["match_id"] = int(m.group(1)) if m else None
    return {"videos": videos}

@app.get("/api/videos/{video_id}")
async def get_video(video_id: str):
    """Get HLS stream URL and thumbnail for a specific video."""
    tl = get_tl()
    info = tl.get_video_info(video_id)
    if not info:
        raise HTTPException(status_code=404, detail="Video not found in index.")
    return info

@app.get("/api/search")
async def search_clips(q: str, limit: int = 10):
    """Search across all indexed videos for moments matching a query."""
    tl = get_tl()
    clips = tl.search_highlights(q, page_limit=limit)
    # Enrich each clip with the HLS URL for its video
    video_cache: dict[str, dict] = {}
    for clip in clips:
        vid = clip["video_id"]
        if vid not in video_cache:
            video_cache[vid] = tl.get_video_info(vid) or {}
        clip["hls_url"] = video_cache[vid].get("hls_url")
        clip["video_thumbnail_url"] = video_cache[vid].get("thumbnail_url")
    return {"clips": clips}

@app.post("/api/discover-highlights")
async def discover_highlights(
    player_name: str,
    video_id: str,
    match_id: int | None = None,
    opponent: str | None = None,
):
    """Run AI highlight discovery for a player on a specific video."""
    tl = get_tl()
    from backend.highlights import discover_discovery_first
    highlights = discover_discovery_first(
        index_id=tl.index_id,
        video_id=video_id,
        player_name=player_name,
        tl_client=tl,
        match_id=match_id,
        opponent=opponent,
    )
    deduped = merge_and_deduplicate(highlights)
    return {"highlights": [h.model_dump() for h in deduped]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
