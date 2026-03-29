import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "dota-intel"))
load_dotenv()

from backend.twelvelabs_client import TwelveLabsClient

def main():
    tl = TwelveLabsClient()
    print("--- Tasks ---")
    tasks = tl._client.task.list()
    for t in tasks:
        print(f"Task ID: {t.id}, Status: {t.status}, Video ID: {getattr(t, 'video_id', 'N/A')}, Index ID: {t.index_id}")

if __name__ == "__main__":
    main()
