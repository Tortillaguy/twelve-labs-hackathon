import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add dota-intel to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "dota-intel"))

load_dotenv()

from backend.twelvelabs_client import TwelveLabsClient

def main():
    tl = TwelveLabsClient()
    print("--- Indexes in Account ---")
    indexes = tl._client.index.list()
    for idx in indexes:
        print(f"\n--- Videos in {idx.name} ({idx.id}) ---")
        try:
            videos = list(tl._client.index.video.list(idx.id))
            for v in videos:
                filename = getattr(v.system_metadata, "filename", "N/A")
                title = getattr(v.system_metadata, "title", "N/A")
                duration = getattr(v.system_metadata, "duration", "N/A")
                user_meta = getattr(v, "user_metadata", {})
                print(f"Video ID: {v.id}, Filename: {filename}, Title: {title}, Duration: {duration}, UserMeta: {user_meta}")
        except Exception as e:
            print(f"Error listing videos in {idx.id}: {e}")

if __name__ == "__main__":
    main()
