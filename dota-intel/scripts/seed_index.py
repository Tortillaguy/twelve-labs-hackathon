#!/usr/bin/env python3
"""
Resilient pre-demo seed pipeline for Dota Intel.

Stages (run independently or together):
  --stage download   Download match VOD segments from stream URLs
  --stage upload     Upload downloaded segments to TwelveLabs and wait for indexing
  --stage metadata   PATCH each TwelveLabs video with OpenDota match metadata
  --stage highlights Discover AI highlights for each player across indexed videos
  --stage score      Aggregate stats, rank players, write leaderboard + player JSONs

Run all stages in order (default):
  python scripts/seed_index.py

Run individual stages to resume after a failure:
  python scripts/seed_index.py --stage download
  python scripts/seed_index.py --stage upload
  python scripts/seed_index.py --stage metadata
  python scripts/seed_index.py --stage highlights
  python scripts/seed_index.py --stage score

State files written between stages (all under data/):
  data/match_segments.json       — input, produced by find_match_segments.py
  data/segments/match_NNN.mp4    — downloaded video segments (stage: download)
  data/video_map.json            — match_id → TwelveLabs video_id (stage: upload)
  data/match_details.json        — OpenDota raw match data, keyed by match_id (stage: upload)
  data/player_highlights.json    — discovered highlights per account_id (stage: highlights)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.opendota import OpenDotaClient
from backend.twelvelabs_client import TwelveLabsClient
from backend.ingestion import download_match_segment, ingest_vod, load_match_segments
from backend.highlights import discover_event_anchored, discover_discovery_first, merge_and_deduplicate
from backend.scoring import aggregate_player_stats, rank_players
from backend.models import (
    MatchDetail, KillEvent, MatchPlayer, MatchSummary,
    PlayerDetail, LeaderboardResponse, Highlight,
)
from backend import cache

# ── CONFIG ────────────────────────────────────────────────────────────────────
LEAGUE_NAME = os.environ.get("ESL_LEAGUE_NAME", "ESL One Birmingham 2026")

PLAYER_ROSTER: dict[int, dict] = {
    173978074: {"name": "NothingToSay", "team": "Team Zero"},
    321580662: {"name": "Yatoro",       "team": "Team Spirit"},
}

# Absolute paths derived from this file so they work regardless of CWD
_ROOT = Path(__file__).parent.parent
DATA_DIR          = _ROOT / "data"
SEGMENT_CACHE_DIR = DATA_DIR / "segments"
MATCH_SEGMENTS_PATH = DATA_DIR / "match_segments.json"
VIDEO_MAP_PATH      = DATA_DIR / "video_map.json"
MATCH_DETAILS_PATH  = DATA_DIR / "match_details.json"
PLAYER_HIGHLIGHTS_PATH = DATA_DIR / "player_highlights.json"

MAX_MATCHES = int(os.environ.get("MAX_MATCHES", "7"))
# ──────────────────────────────────────────────────────────────────────────────


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: Path, default):
    """Load a JSON state file, returning `default` if it doesn't exist."""
    if path.exists():
        return json.loads(path.read_text())
    return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f"[seed] Saved {path}")


def _build_match_detail(raw: dict) -> tuple[MatchDetail, list[KillEvent], list[MatchPlayer]]:
    """Parse an OpenDota raw match dict into our Pydantic models."""
    kills = [
        KillEvent(time=k["time"], killer_id=k.get("player_slot", 0), victim_id=0)
        for k in raw.get("kills_log", [])
    ]
    players = [
        MatchPlayer(
            account_id=p.get("account_id"),
            player_slot=p["player_slot"],
            hero_id=p["hero_id"],
            kills=p["kills"],
            deaths=p["deaths"],
            assists=p["assists"],
            gold_per_min=p["gold_per_min"],
            net_worth=p.get("net_worth", 0),
        )
        for p in raw.get("players", [])
    ]
    # Resolve slot→account_id in kills_log
    slot_to_account = {p.player_slot: p.account_id for p in players}
    for k in kills:
        k.killer_id = slot_to_account.get(k.killer_id, 0) or 0

    m_detail = MatchDetail(
        match_id=raw["match_id"],
        duration=raw["duration"],
        start_time=raw["start_time"],
        radiant_win=raw["radiant_win"],
        kills_log=kills,
        players=players,
    )
    return m_detail, kills, players

# ── Stages ────────────────────────────────────────────────────────────────────

def stage_download():
    """
    Stage 1: Download match VOD segments from stream URLs.
    Skips matches already downloaded. Writes .mp4 files to data/segments/.
    """
    print("\n=== STAGE: download ===")
    match_segments = load_match_segments(str(MATCH_SEGMENTS_PATH))
    od = OpenDotaClient()

    processed = 0
    for mid_str, seg in match_segments.items():
        mid = int(mid_str)
        if processed >= MAX_MATCHES:
            break

        seg_path = SEGMENT_CACHE_DIR / f"match_{mid}.mp4"
        if seg_path.exists():
            print(f"[download] match {mid}: already cached ({seg_path.stat().stat().st_size / 1024**2:.0f} MB), skipping.")
            processed += 1
            continue

        # Fetch match detail to compute precise offsets
        print(f"[download] Fetching OpenDota detail for match {mid}...")
        raw = od.fetch_match_detail(mid)

        # Broaden duration to include full VOD segments (up to ~110m)
        if not (1200 <= raw["duration"] <= 7200):
            print(f"[download] match {mid}: duration {raw['duration']//60}m outside 20–120m window, skipping.")
            continue

        stream_start_unix = seg["stream_start_unix"]
        match_start_unix  = raw["start_time"]
        match_duration    = raw["duration"]
        total_pauses      = sum(p.get("duration", 0) for p in raw.get("pauses", []))

        # Skip draft (~15 min) + cover full match + pauses + 30s buffer
        start_offset = max(0, (match_start_unix - stream_start_unix) + 900)
        duration     = match_duration + total_pauses + 30

        print(f"[download] match {mid}: {seg['radiant_team']} vs {seg['dire_team']} "
              f"({duration//60}m to download)...")
        SEGMENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        download_match_segment(
            stream_url=seg["stream_url"],
            offset_seconds=start_offset,
            duration_seconds=duration,
            output_path=str(seg_path),
        )
        size_mb = seg_path.stat().st_size / 1024**2
        print(f"[download] match {mid}: done — {size_mb:.0f} MB at {seg_path}")
        processed += 1

    print(f"[download] Complete. {processed} segment(s) ready in {SEGMENT_CACHE_DIR}")


def stage_upload():
    """
    Stage 2: Upload downloaded segments to TwelveLabs, wait for indexing.
    Skips videos already present in the TwelveLabs index (checks by filename).
    Writes data/video_map.json (match_id → video_id) and data/match_details.json.
    """
    print("\n=== STAGE: upload ===")
    tl = TwelveLabsClient()
    od = OpenDotaClient()
    tl.get_or_create_index("dota-intel")

    # Build filename → video_id map from already-indexed videos
    existing_videos = tl.list_videos()
    indexed_filenames: dict[str, str] = {
        v["filename"]: v["video_id"]
        for v in existing_videos
        if v.get("filename")
    }
    print(f"[upload] {len(indexed_filenames)} video(s) already in TwelveLabs index.")

    video_map: dict[str, str]  = _load_json(VIDEO_MAP_PATH, {})   # match_id(str) → video_id
    match_details_raw: dict[str, dict] = _load_json(MATCH_DETAILS_PATH, {})

    match_segments = load_match_segments(str(MATCH_SEGMENTS_PATH))
    processed = 0

    for mid_str, seg in match_segments.items():
        mid = int(mid_str)
        if processed >= MAX_MATCHES:
            break

        seg_path = SEGMENT_CACHE_DIR / f"match_{mid}.mp4"
        if not seg_path.exists():
            print(f"[upload] match {mid}: segment not downloaded yet, skipping. Run --stage download first.")
            continue

        expected_filename = f"match_{mid}.mp4"

        if mid_str in video_map:
            print(f"[upload] match {mid}: already in video_map ({video_map[mid_str]}), skipping.")
            processed += 1
            # Still fetch/cache match detail if missing
            if mid_str not in match_details_raw:
                print(f"[upload] match {mid}: fetching OpenDota detail for metadata stage...")
                match_details_raw[mid_str] = od.fetch_match_detail(mid)
                _save_json(MATCH_DETAILS_PATH, match_details_raw)
            continue

        if expected_filename in indexed_filenames:
            vid = indexed_filenames[expected_filename]
            print(f"[upload] match {mid}: already indexed as {vid}, adding to video_map.")
            video_map[mid_str] = vid
            _save_json(VIDEO_MAP_PATH, video_map)
            processed += 1
            if mid_str not in match_details_raw:
                match_details_raw[mid_str] = od.fetch_match_detail(mid)
                _save_json(MATCH_DETAILS_PATH, match_details_raw)
            continue

        print(f"[upload] match {mid}: uploading {seg_path.stat().st_size / 1024**2:.0f} MB to TwelveLabs...")
        record = ingest_vod(str(seg_path), tl, mid)
        video_id = record["indexed_asset_id"]
        video_map[mid_str] = video_id
        _save_json(VIDEO_MAP_PATH, video_map)
        print(f"[upload] match {mid}: indexed as video_id={video_id}")

        if mid_str not in match_details_raw:
            match_details_raw[mid_str] = od.fetch_match_detail(mid)
            _save_json(MATCH_DETAILS_PATH, match_details_raw)

        processed += 1

    print(f"[upload] Complete. video_map has {len(video_map)} entries.")


def stage_metadata():
    """
    Stage 3: PATCH each TwelveLabs video with OpenDota match metadata.
    This attaches structured data (match_id, duration, radiant_team, etc.)
    as user_metadata on the video so it's searchable/filterable in TwelveLabs.
    Skips videos that already have match_id in their user_metadata.
    """
    print("\n=== STAGE: metadata ===")
    tl = TwelveLabsClient()
    tl.get_or_create_index("dota-intel")

    video_map: dict[str, str] = _load_json(VIDEO_MAP_PATH, {})
    match_details_raw: dict[str, dict] = _load_json(MATCH_DETAILS_PATH, {})
    match_segments = _load_json(MATCH_SEGMENTS_PATH, {})

    if not video_map:
        print("[metadata] video_map.json is empty. Run --stage upload first.")
        return

    # Fetch current user_metadata to skip already-patched videos
    existing_videos = {v["video_id"]: v for v in tl.list_videos()}

    patched = 0
    for mid_str, video_id in video_map.items():
        existing = existing_videos.get(video_id, {})
        current_meta = existing.get("user_metadata", {})

        if str(current_meta.get("match_id", "")) == mid_str:
            print(f"[metadata] video {video_id} (match {mid_str}): already patched, skipping.")
            continue

        raw = match_details_raw.get(mid_str)
        if not raw:
            print(f"[metadata] match {mid_str}: no raw detail cached, skipping.")
            continue

        seg = match_segments.get(mid_str, {})

        # TwelveLabs user_metadata values must be scalar (str/int/float/bool)
        meta = {
            "match_id":       int(mid_str),
            "league":         LEAGUE_NAME,
            "duration_secs":  raw["duration"],
            "radiant_win":    raw["radiant_win"],
            "radiant_team":   seg.get("radiant_team", "Unknown"),
            "dire_team":      seg.get("dire_team", "Unknown"),
            "first_blood_time": raw.get("first_blood_time", 0),
            # Store top-player KDA as a string for context in Pegasus analysis
            "top_player_summary": _summarize_players(raw),
        }

        try:
            tl.update_video_metadata(video_id, meta)
            print(f"[metadata] Patched video {video_id} (match {mid_str}) with OpenDota metadata.")
            patched += 1
        except Exception as e:
            print(f"[metadata] WARNING: failed to patch {video_id}: {e}")

    print(f"[metadata] Complete. {patched} video(s) patched.")


def _summarize_players(raw: dict) -> str:
    """Build a compact string of top performers for Pegasus context."""
    players = raw.get("players", [])
    # Sort by kills desc, take top 3
    top = sorted(players, key=lambda p: p.get("kills", 0), reverse=True)[:3]
    parts = []
    for p in top:
        name = p.get("personaname") or p.get("name") or f"slot{p['player_slot']}"
        parts.append(f"{name} {p.get('kills',0)}/{p.get('deaths',0)}/{p.get('assists',0)}")
    return ", ".join(parts)


def stage_highlights():
    """
    Stage 4: Discover AI highlights for each player using both discovery strategies.
    Reads video_map.json and match_details.json.
    Writes data/player_highlights.json keyed by account_id.
    """
    print("\n=== STAGE: highlights ===")
    tl = TwelveLabsClient()
    od = OpenDotaClient()
    tl.get_or_create_index("dota-intel")

    video_map: dict[str, str] = _load_json(VIDEO_MAP_PATH, {})
    match_details_raw: dict[str, dict] = _load_json(MATCH_DETAILS_PATH, {})
    match_segments = _load_json(MATCH_SEGMENTS_PATH, {})

    if not video_map:
        print("[highlights] video_map.json is empty. Run --stage upload first.")
        return

    # Load any previously discovered highlights to allow incremental resumption
    raw_highlights: dict[str, list[dict]] = _load_json(PLAYER_HIGHLIGHTS_PATH, {})

    for mid_str, video_id in video_map.items():
        raw = match_details_raw.get(mid_str)
        if not raw:
            print(f"[highlights] match {mid_str}: no detail cached, skipping.")
            continue

        _, kills, players = _build_match_detail(raw)
        seg = match_segments.get(mid_str, {})

        print(f"\n[highlights] Calibrating game start for video {video_id}...")
        horn_offset = tl.calibrate_game_start(
            video_id, first_blood_time=raw.get("first_blood_time", 0)
        )
        print(f"[highlights] Horn offset: {horn_offset:.0f}s")

        for aid, info in PLAYER_ROSTER.items():
            aid_str = str(aid)
            p_in_match = next((p for p in players if p.account_id == aid), None)
            if not p_in_match:
                continue

            # Skip if already discovered highlights for this player+video combo
            already_done = [
                h for h in raw_highlights.get(aid_str, [])
                if h.get("video_id") == video_id
            ]
            if already_done:
                print(f"[highlights] {info['name']} × video {video_id}: already have "
                      f"{len(already_done)} highlights, skipping.")
                continue

            print(f"[highlights] {info['name']} × match {mid_str}...")
            opponent = (seg.get("dire_team", "Unknown") if p_in_match.player_slot < 128
                        else seg.get("radiant_team", "Unknown"))

            # Strategy A: event-anchored (kill events from OpenDota)
            event_clips = discover_event_anchored(
                kills_log=kills,
                video_id=video_id,
                game_start_offset=horn_offset,
                player_account_id=p_in_match.player_slot,
                player_name=info["name"],
                tl_client=tl,
                match_id=int(mid_str),
                opponent=opponent,
            )
            print(f"  [A] event-anchored: {len(event_clips)} clips")

            # Strategy B: discovery-first (caster mention + kill streak + in-game banners)
            discovery_clips = discover_discovery_first(
                index_id=tl.index_id,
                video_id=video_id,
                player_name=info["name"],
                tl_client=tl,
                match_id=int(mid_str),
                opponent=opponent,
            )
            print(f"  [B] discovery-first: {len(discovery_clips)} clips")

            merged = merge_and_deduplicate(event_clips + discovery_clips)
            print(f"  → merged + deduped: {len(merged)} highlights")

            if aid_str not in raw_highlights:
                raw_highlights[aid_str] = []
            raw_highlights[aid_str].extend([h.model_dump() for h in merged])

        # Save after each video so a crash mid-loop doesn't lose work
        _save_json(PLAYER_HIGHLIGHTS_PATH, raw_highlights)

    print(f"\n[highlights] Complete.")


def stage_score():
    """
    Stage 5: Aggregate stats, rank players, write leaderboard + per-player JSONs.
    Reads match_details.json, player_highlights.json, match_segments.json.
    """
    print("\n=== STAGE: score ===")
    od = OpenDotaClient()

    match_details_raw: dict[str, dict] = _load_json(MATCH_DETAILS_PATH, {})
    raw_highlights: dict[str, list[dict]] = _load_json(PLAYER_HIGHLIGHTS_PATH, {})
    match_segments = _load_json(MATCH_SEGMENTS_PATH, {})

    if not match_details_raw:
        print("[score] match_details.json is empty. Run --stage upload first.")
        return

    # Reconstruct MatchDetail objects
    match_details: list[MatchDetail] = []
    for mid_str, raw in match_details_raw.items():
        m_detail, _, _ = _build_match_detail(raw)
        match_details.append(m_detail)

    ranked_input = []
    for aid, info in PLAYER_ROSTER.items():
        aid_str = str(aid)
        player_matches = [m for m in match_details
                          if any(p.account_id == aid for p in m.players)]
        if not player_matches:
            print(f"[score] No matched matches for {info['name']}, skipping.")
            continue

        stats = aggregate_player_stats(player_matches, aid, info["name"], info["team"])
        highlights = [
            Highlight(**h) for h in raw_highlights.get(aid_str, [])
        ]
        h_dedup = merge_and_deduplicate(highlights)[:14]  # cap per player

        # Build match summaries
        match_summaries: list[MatchSummary] = []
        for md in sorted(player_matches, key=lambda m: m.start_time, reverse=True):
            mid_str = str(md.match_id)
            player = next(p for p in md.players if p.account_id == aid)
            is_radiant = player.player_slot < 128
            seg = match_segments.get(mid_str, {})
            opponent = (seg.get("dire_team", "Unknown") if is_radiant
                        else seg.get("radiant_team", "Unknown"))
            won = (is_radiant and md.radiant_win) or (not is_radiant and not md.radiant_win)
            clip_count = sum(1 for h in h_dedup if h.match_id == md.match_id)
            dur_m, dur_s = divmod(md.duration, 60)

            match_summaries.append(MatchSummary(
                match_id=md.match_id,
                opponent=opponent,
                won=won,
                duration_str=f"{dur_m}:{dur_s:02d}",
                kills=player.kills,
                deaths=player.deaths,
                assists=player.assists,
                gpm=player.gold_per_min,
                hero_id=player.hero_id,
                clip_count=clip_count,
            ))

        ranked_input.append({
            "stats": stats,
            "highlights": h_dedup,
            "match_summaries": match_summaries,
        })

    if not ranked_input:
        print("[score] No player data to rank.")
        return

    final_ranked = rank_players(ranked_input)
    ranked_by_id = {p.account_id: p for p in final_ranked}

    for entry in ranked_input:
        aid = entry["stats"].account_id
        p_detail = PlayerDetail(
            player=ranked_by_id[aid],
            recent_matches=entry["match_summaries"][:8],
            highlights=entry["highlights"],
        )
        cache.write_player(aid, p_detail)
        print(f"[score] Wrote player: {entry['stats'].name} (rank {ranked_by_id[aid].rank})")

    top10 = final_ranked[:10]
    avg_kda = sum(p.avg_kda_ratio for p in top10) / max(1, len(top10))
    lb = LeaderboardResponse(
        competition=LEAGUE_NAME,
        total_matches=len(match_details),
        total_teams=len(set(p.team for p in final_ranked)),
        total_highlights=sum(p.highlight_count for p in final_ranked),
        avg_kda_top10=round(avg_kda, 2),
        players=final_ranked,
    )
    cache.write_leaderboard(lb)
    print(f"[score] Leaderboard written: {len(final_ranked)} players, "
          f"{lb.total_highlights} highlights.")

# ── Entry point ───────────────────────────────────────────────────────────────

ALL_STAGES = ["download", "upload", "metadata", "highlights", "score"]

STAGE_FN = {
    "download":   stage_download,
    "upload":     stage_upload,
    "metadata":   stage_metadata,
    "highlights": stage_highlights,
    "score":      stage_score,
}

def main():
    parser = argparse.ArgumentParser(
        description="Resilient Dota Intel seed pipeline. Run all stages or one at a time.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Stages (in order):
  download    Download VOD segments from stream URLs → data/segments/
  upload      Upload segments to TwelveLabs, cache video_id mapping
  metadata    PATCH TwelveLabs videos with OpenDota match data
  highlights  Discover AI highlights for each player
  score       Rank players, write leaderboard + player JSON files

Examples:
  python scripts/seed_index.py                      # run all stages
  python scripts/seed_index.py --stage download     # only download
  python scripts/seed_index.py --stage upload       # only upload (resumes safely)
  python scripts/seed_index.py --stage metadata     # attach OpenDota data to existing videos
  python scripts/seed_index.py --stage highlights   # (re)run highlight discovery
  python scripts/seed_index.py --stage score        # recompute rankings from cached data
""",
    )
    parser.add_argument(
        "--stage",
        choices=ALL_STAGES,
        default=None,
        help="Run a single pipeline stage instead of all stages.",
    )
    args = parser.parse_args()

    stages = [args.stage] if args.stage else ALL_STAGES

    for stage in stages:
        try:
            STAGE_FN[stage]()
        except KeyboardInterrupt:
            print(f"\n[seed] Interrupted during stage '{stage}'. "
                  f"Re-run with --stage {stage} to resume.")
            sys.exit(1)
        except Exception as e:
            print(f"\n[seed] ERROR in stage '{stage}': {e}")
            print(f"[seed] Fix the issue and re-run with: python scripts/seed_index.py --stage {stage}")
            raise

    print("\n[seed] All stages complete.")


if __name__ == "__main__":
    main()
