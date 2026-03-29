import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from backend import cache
from backend.models import LeaderboardResponse, PlayerDetail, Highlight
from backend.twelvelabs_client import TwelveLabsClient
from backend.highlights import merge_and_deduplicate, discover_discovery_first

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
    print(f"[debug] Fetching player {account_id} (demo={demo})")
    detail = cache.read_player(account_id, demo=demo)
    if not detail:
        raise HTTPException(status_code=404, detail="Player not found.")

    # hls_url is pre-baked into highlights by `seed_index.py --stage prebake`.
    # Fall back to the video_info_cache for any highlights that were added before
    # prebake ran (e.g. demo/mock data).
    result = detail.model_dump()
    video_cache: dict[str, dict] = {}
    for hl in result["highlights"]:
        if hl.get("hls_url"):
            continue  # already baked in — no API call needed
        vid = hl["video_id"]
        if vid not in video_cache:
            video_cache[vid] = cache.read_video_info_cache(vid) or {}
        info = video_cache[vid]
        hl["hls_url"] = info.get("hls_url")
        if not hl.get("thumbnail_url"):
            hl["thumbnail_url"] = info.get("thumbnail_url")
    return result



@app.get("/api/search")
def search_clips(q: str, limit: int = 10):
    """Search across all indexed videos for moments matching a query."""
    tl = get_tl()
    clips = tl.search_highlights(q, page_limit=limit)
    # Enrich each clip with the HLS URL for its video
    video_cache: dict[str, dict] = {}
    for clip in clips:
        vid = clip["video_id"]
        if vid not in video_cache:
            try:
                video_cache[vid] = tl.get_video_info(vid) or {}
            except Exception as e:
                print(f"[search] Warning: could not fetch video info for {vid}: {e}")
                video_cache[vid] = {}
        clip["hls_url"] = video_cache[vid].get("hls_url")
        clip["video_thumbnail_url"] = video_cache[vid].get("thumbnail_url")
    return {"clips": clips}

@app.post("/api/discover-highlights")
def discover_highlights(
    player_name: str,
    video_id: str,
    match_id: int | None = None,
    opponent: str | None = None,
    hero_name: str | None = None,
):
    """Run AI highlight discovery for a player on a specific video."""
    tl = get_tl()
    highlights = discover_discovery_first(
        index_id=tl.index_id,
        video_id=video_id,
        player_name=player_name,
        tl_client=tl,
        match_id=match_id,
        opponent=opponent,
        hero_name=hero_name,
    )
    deduped = merge_and_deduplicate(highlights)
    return {"highlights": [h.model_dump() for h in deduped]}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
