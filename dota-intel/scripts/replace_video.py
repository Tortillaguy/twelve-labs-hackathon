#!/usr/bin/env python3
"""
Replace a video in TwelveLabs with a higher-quality version and re-ingest.

Usage:
  1. Place the new .mp4 at data/segments/match_<MATCH_ID>.mp4
  2. Run:  python scripts/replace_video.py <MATCH_ID>
     e.g.: python scripts/replace_video.py 8747660830

What it does:
  - Deletes the OLD video from TwelveLabs index
  - Removes stale entries from video_map.json + video_info_cache.json
  - Uploads the new .mp4 and waits for indexing
  - Re-patches metadata from match_details.json
  - Re-runs prebake + score stages so highlights get new HLS URLs

After this script completes, run:
  python scripts/seed_index.py --stage highlights
to re-discover highlights for the affected players with the new video.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.twelvelabs_client import TwelveLabsClient
from backend.ingestion import ingest_vod

_ROOT = Path(__file__).parent.parent
DATA_DIR            = _ROOT / "data"
SEGMENT_CACHE_DIR   = DATA_DIR / "segments"
VIDEO_MAP_PATH      = DATA_DIR / "video_map.json"
VIDEO_INFO_CACHE    = DATA_DIR / "video_info_cache.json"
# Also check repo-root fallback used by the frontend
VIDEO_INFO_CACHE_ROOT = _ROOT.parent / "data" / "video_info_cache.json"
MATCH_DETAILS_PATH  = DATA_DIR / "match_details.json"
MATCH_SEGMENTS_PATH = DATA_DIR / "match_segments.json"
PLAYER_HIGHLIGHTS_PATH = DATA_DIR / "player_highlights.json"


def _load_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text())
    return default if default is not None else {}


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f"  saved → {path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/replace_video.py <MATCH_ID>")
        sys.exit(1)

    match_id = sys.argv[1]
    seg_path = SEGMENT_CACHE_DIR / f"match_{match_id}.mp4"

    if not seg_path.exists():
        print(f"ERROR: New video not found at {seg_path}")
        print(f"Place the 720p .mp4 there first, then re-run.")
        sys.exit(1)

    size_mb = seg_path.stat().st_size / 1024**2
    print(f"Found new video: {seg_path} ({size_mb:.0f} MB)")

    # ── Load state ────────────────────────────────────────────────────────────
    video_map = _load_json(VIDEO_MAP_PATH, {})
    old_video_id = video_map.get(match_id)

    if not old_video_id:
        print(f"WARNING: match {match_id} not in video_map.json — nothing to delete.")
        print(f"Will proceed with fresh upload.")
    else:
        print(f"Old video_id: {old_video_id}")

    # ── Step 1: Delete old video from TwelveLabs ──────────────────────────────
    tl = TwelveLabsClient()
    tl.get_or_create_index("dota-intel")

    if old_video_id:
        print(f"\n[1/5] Deleting old video {old_video_id} from TwelveLabs...")
        try:
            tl._client.index.video.delete(tl.index_id, old_video_id)
            print(f"  Deleted successfully.")
        except Exception as e:
            print(f"  WARNING: delete failed ({e}). May already be gone. Continuing...")

    # ── Step 2: Remove stale local state ──────────────────────────────────────
    print(f"\n[2/5] Cleaning local state files...")

    # video_map.json
    if match_id in video_map:
        del video_map[match_id]
        _save_json(VIDEO_MAP_PATH, video_map)

    # video_info_cache.json (dota-intel/data/)
    vic = _load_json(VIDEO_INFO_CACHE, {})
    if old_video_id and old_video_id in vic:
        del vic[old_video_id]
        _save_json(VIDEO_INFO_CACHE, vic)

    # video_info_cache.json (repo root data/)
    if VIDEO_INFO_CACHE_ROOT.exists():
        vic_root = _load_json(VIDEO_INFO_CACHE_ROOT, {})
        if old_video_id and old_video_id in vic_root:
            del vic_root[old_video_id]
            _save_json(VIDEO_INFO_CACHE_ROOT, vic_root)

    # player_highlights.json — remove highlights referencing old video_id
    if old_video_id:
        ph = _load_json(PLAYER_HIGHLIGHTS_PATH, {})
        removed_count = 0
        for aid_str, highlights in ph.items():
            before = len(highlights)
            ph[aid_str] = [h for h in highlights if h.get("video_id") != old_video_id]
            removed_count += before - len(ph[aid_str])
        if removed_count > 0:
            _save_json(PLAYER_HIGHLIGHTS_PATH, ph)
            print(f"  Removed {removed_count} stale highlight(s) from player_highlights.json")

    # ── Step 3: Upload new video ──────────────────────────────────────────────
    print(f"\n[3/5] Uploading new 720p video to TwelveLabs...")
    print(f"  This may take several minutes depending on file size.")
    new_video_id = tl.upload_and_index(str(seg_path))
    print(f"  New video_id: {new_video_id}")

    # Update video_map
    video_map[match_id] = new_video_id
    _save_json(VIDEO_MAP_PATH, video_map)

    # ── Step 4: Patch metadata ────────────────────────────────────────────────
    print(f"\n[4/5] Patching metadata on new video...")
    match_details_raw = _load_json(MATCH_DETAILS_PATH, {})
    match_segments = _load_json(MATCH_SEGMENTS_PATH, {})

    raw = match_details_raw.get(match_id)
    seg = match_segments.get(match_id, {})

    if raw:
        players = raw.get("players", [])
        top = sorted(players, key=lambda p: p.get("kills", 0), reverse=True)[:3]
        top_summary = ", ".join(
            f"{p.get('personaname') or p.get('name') or f'slot{p[\"player_slot\"]}'} "
            f"{p.get('kills',0)}/{p.get('deaths',0)}/{p.get('assists',0)}"
            for p in top
        )

        meta = {
            "match_id":         int(match_id),
            "league":           "ESL One Birmingham 2026",
            "duration_secs":    raw["duration"],
            "radiant_win":      raw["radiant_win"],
            "radiant_team":     seg.get("radiant_team", "Unknown"),
            "dire_team":        seg.get("dire_team", "Unknown"),
            "first_blood_time": raw.get("first_blood_time", 0),
            "top_player_summary": top_summary,
        }
        tl.update_video_metadata(new_video_id, meta)
        print(f"  Metadata patched.")
    else:
        print(f"  WARNING: No match_details cached for {match_id}. Skipping metadata patch.")

    # ── Step 5: Refresh video_info_cache ──────────────────────────────────────
    print(f"\n[5/5] Refreshing video info cache...")
    info = tl.get_video_info(new_video_id)
    if info:
        now = time.time()
        cache_entry = {
            "video_id": new_video_id,
            "hls_url": info["hls_url"],
            "thumbnail_url": info["thumbnail_url"],
            "cached_at": now,
        }
        vic = _load_json(VIDEO_INFO_CACHE, {})
        vic[new_video_id] = cache_entry
        _save_json(VIDEO_INFO_CACHE, vic)

        if VIDEO_INFO_CACHE_ROOT.exists():
            vic_root = _load_json(VIDEO_INFO_CACHE_ROOT, {})
            vic_root[new_video_id] = cache_entry
            _save_json(VIDEO_INFO_CACHE_ROOT, vic_root)
    else:
        print(f"  WARNING: Could not fetch video info. HLS URLs may not be available yet.")
        print(f"  Run 'python scripts/seed_index.py --stage prebake' later to fix.")

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Video replaced successfully!")
    print(f"  Match:        {match_id}")
    print(f"  Old video_id: {old_video_id or '(none)'}")
    print(f"  New video_id: {new_video_id}")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"  1. Re-discover highlights:")
    print(f"     python scripts/seed_index.py --stage highlights")
    print(f"  2. Re-bake HLS URLs into player JSONs:")
    print(f"     python scripts/seed_index.py --stage prebake")
    print(f"  3. Re-score leaderboard:")
    print(f"     python scripts/seed_index.py --stage score")


if __name__ == "__main__":
    main()
