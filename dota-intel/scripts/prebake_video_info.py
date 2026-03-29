import os
import sys
from pathlib import Path

# Add project root to path so we can import backend
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.append(str(PROJECT_ROOT))

import dotenv
dotenv.load_dotenv()

from backend.twelvelabs_client import TwelveLabsClient
from backend import cache

def prebake_all_videos():
    """
    Fetch info for all videos in the Twelve Labs index 
    and save it to the persistent cache.
    """
    print("[prebake] Initializing Twelve Labs client...")
    try:
        tl = TwelveLabsClient()
        if not tl.index_id:
            print("[prebake] No INDEX_ID found. Finding 'dota-intel' index...")
            tl.get_or_create_index("dota-intel")
        
        print(f"[prebake] Fetching video listing for index {tl.index_id}...")
        videos = tl.list_videos()
        print(f"[prebake] Found {len(videos)} videos in Twelve Labs index.")
        
        for v in videos:
            vid = v["video_id"]
            print(f"[prebake] Caching HLS info for video {vid} (filename: {v.get('filename')})...")
            # We already have the info in the list_videos response
            info = {
                "video_id": vid,
                "hls_url": v["hls_url"],
                "thumbnail_url": v["thumbnail_url"]
            }
            cache.write_video_info_cache(vid, info)
            
        print("[prebake] Pre-computation complete! All video info cached.")
    except Exception as e:
        print(f"[prebake] Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    prebake_all_videos()
