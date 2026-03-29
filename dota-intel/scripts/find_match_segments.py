#!/usr/bin/env python3
"""
Scans a list of stream URLs to find which time window contains each OpenDota match.

Usage:
  python scripts/find_match_segments.py \
    --league "ESL One" \
    --streams https://www.twitch.tv/videos/2345678901 \
              https://www.twitch.tv/videos/2345678902 \
              https://www.youtube.com/watch?v=XXXXXXXXXXX

Output:
  data/match_segments.json  —  {match_id: {stream_url, offset_seconds, ...}}

Run this once per event. Then run seed_index.py to download segments and index them.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.opendota import OpenDotaClient

BUFFER_BEFORE_SECONDS  = 600   # 10 min before match start (covers draft phase)
SEGMENT_DURATION_SECONDS = 6600  # 110 min total (draft + ~45-min match + 20-min buffer)

def format_hhmmss(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_stream_metadata(stream_url: str) -> dict:
    """
    Fetch metadata for a stream URL without downloading any video.
    Returns dict containing at minimum:
      timestamp  (int)  — Unix epoch when the broadcast began
      duration   (int)  — total stream length in seconds
      title      (str)  — broadcast title
    """
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-playlist", stream_url],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp metadata failed for {stream_url}:\n{result.stderr.strip()}"
        )
    return json.loads(result.stdout)

def find_matches_in_stream(
    stream_url: str,
    league_matches: list[dict],
    match_start_times: dict[int, int],
) -> list[dict]:
    """
    Compares each match's start_time against this stream's broadcast window.
    Returns a list of segment descriptors for every match found inside the stream.
    """
    meta = get_stream_metadata(stream_url)
    stream_start  = int(meta["timestamp"])
    stream_duration = int(meta.get("duration") or 0)
    stream_end    = stream_start + stream_duration

    print(f"  Title   : {meta.get('title', 'unknown')}")
    print(f"  Started : {stream_start}  (unix)")
    print(f"  Duration: {stream_duration // 3600}h {(stream_duration % 3600) // 60}m")

    found = []
    for lm in league_matches:
        mid = lm["match_id"]
        match_start = match_start_times.get(mid)
        if match_start is None:
            continue
        if not (stream_start <= match_start <= stream_end):
            continue  # this match is not inside this stream

        # Offset from stream start, minus the draft buffer
        offset = max(0, match_start - stream_start - BUFFER_BEFORE_SECONDS)
        seg_start = format_hhmmss(offset)
        seg_end   = format_hhmmss(offset + SEGMENT_DURATION_SECONDS)

        print(f"  ✓ Match {mid}: {seg_start} → {seg_end}  "
              f"({lm.get('radiant_team_name','?')} vs {lm.get('dire_team_name','?')})")

        found.append({
            "match_id":             mid,
            "stream_url":           stream_url,
            "stream_start_unix":    stream_start,
            "match_start_unix":     match_start,
            "offset_seconds":       offset,
            "duration_seconds":     SEGMENT_DURATION_SECONDS,
            "segment_start_hhmmss": seg_start,
            "segment_end_hhmmss":   seg_end,
            "radiant_team":         lm.get("radiant_team_name", "Unknown"),
            "dire_team":            lm.get("dire_team_name",    "Unknown"),
        })
    return found

def main():
    parser = argparse.ArgumentParser(
        description="Map OpenDota match IDs to their time windows inside broadcast streams"
    )
    parser.add_argument("--league",  required=True, help="League name to search on OpenDota")
    parser.add_argument("--streams", nargs="+", required=True, help="Stream URLs to scan")
    args = parser.parse_args()

    od = OpenDotaClient()

    print(f"[find] Looking up league: {args.league}")
    league = od.find_league(args.league)
    if not league:
        raise SystemExit(f"League '{args.league}' not found on OpenDota.")
    league_id = league["leagueid"]
    print(f"[find] Found: {league['name']} (id={league_id})")

    print(f"[find] Fetching match list...")
    league_matches = od.fetch_league_matches(league_id)
    print(f"[find] {len(league_matches)} matches in league")

    # Fetch start_time for each match (needed for offset calculation)
    print(f"[find] Mapping {len(league_matches)} matches...")
    match_start_times: dict[int, int] = {
        lm["match_id"]: lm["start_time"] for lm in league_matches if "start_time" in lm
    }

    all_segments: dict[str, dict] = {}  # keyed by str(match_id)


    for stream_url in args.streams:
        print(f"\n[find] Scanning: {stream_url}")
        try:
            segs = find_matches_in_stream(stream_url, league_matches, match_start_times)
            for seg in segs:
                all_segments[str(seg["match_id"])] = seg
        except Exception as e:
            print(f"  Error: {e}")

    out = Path("data/match_segments.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(all_segments, indent=2))

    print(f"\n[find] Mapped {len(all_segments)}/{len(league_matches)} matches → {out}")
    if len(all_segments) < len(league_matches):
        unmapped = [
            str(lm["match_id"]) for lm in league_matches
            if str(lm["match_id"]) not in all_segments
        ]
        print(f"[find] Unmapped match IDs (add their stream URLs and re-run):")
        for mid in unmapped:
            print(f"  {mid}")
    print("[find] Next step: python scripts/seed_index.py")

if __name__ == "__main__":
    main()
