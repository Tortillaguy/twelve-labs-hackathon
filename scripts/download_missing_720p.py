import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "dota-intel"))

from backend.ingestion import download_match_segment, load_match_segments
from backend.opendota import OpenDotaClient

DATA_DIR = Path("data")
SEGMENT_CACHE_DIR = DATA_DIR / "segments"
MATCH_SEGMENTS_PATH = DATA_DIR / "match_segments.json"
VIDEO_MAP_PATH = DATA_DIR / "video_map.json"

def main():
    if not MATCH_SEGMENTS_PATH.exists():
        print("No match_segments.json found.")
        return
        
    match_segments = json.loads(MATCH_SEGMENTS_PATH.read_text())
    
    video_map = {}
    if VIDEO_MAP_PATH.exists():
        video_map = json.loads(VIDEO_MAP_PATH.read_text())
        
    od = OpenDotaClient()
    
    for str_mid, seg in match_segments.items():
        if str_mid not in video_map:
            print(f"Match {str_mid} is MISSING in TwelveLabs but accounted for in dataset. Downloading 720p...")
            mid = int(str_mid)
            seg_path = SEGMENT_CACHE_DIR / f"match_{mid}.mp4"
            
            # Delete if it already exists (to force 720p redownload)
            if seg_path.exists():
                print(f"Removing existing {seg_path.name} to force 720p download.")
                seg_path.unlink()
                
            raw = od.fetch_match_detail(mid)
            if not (1200 <= raw["duration"] <= 7200):
                print(f"match {mid}: duration {raw['duration']//60}m outside 20–120m window, skipping.")
                continue

            stream_start_unix = seg["stream_start_unix"]
            match_start_unix  = raw["start_time"]
            match_duration    = raw["duration"]
            total_pauses      = sum(p.get("duration", 0) for p in raw.get("pauses", []))

            start_offset = max(0, (match_start_unix - stream_start_unix) + 900)
            duration     = match_duration + total_pauses + 30

            print(f"Attempting download for {mid}...")
            SEGMENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            download_match_segment(
                stream_url=seg["stream_url"],
                offset_seconds=start_offset,
                duration_seconds=duration,
                output_path=str(seg_path),
            )
            print(f"Finished downloading 720p for {mid}")

if __name__ == "__main__":
    main()
