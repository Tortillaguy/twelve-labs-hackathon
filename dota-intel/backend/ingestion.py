import json
import subprocess
from pathlib import Path

BUFFER_BEFORE_SECONDS    = 600
SEGMENT_DURATION_SECONDS = 6600

def format_hhmmss(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def download_match_segment(
    stream_url: str,
    offset_seconds: int,
    duration_seconds: int,
    output_path: str,
) -> Path:
    """
    Download a specific time window from a 10-12hr stream using yt-dlp.
    Uses --download-sections to avoid pulling the entire broadcast.
    output_path must end in .mp4.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    start_ts = format_hhmmss(offset_seconds)
    end_ts   = format_hhmmss(offset_seconds + duration_seconds)

    print(f"[ingest] Starting yt-dlp download for {path}...")
    result = subprocess.run(
        [
            "yt-dlp",
            "--download-sections", f"*{start_ts}-{end_ts}",
            "--format", "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "--merge-output-format", "mp4",
            "--output", str(path),
            stream_url,
        ],
        capture_output=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp segment download failed with exit code {result.returncode}"
        )
    return path

def ingest_vod(vod_path: str, tl_client, match_id: int) -> dict:
    """
    Upload a local video segment to TwelveLabs and index it.
    Blocks until the index task completes (~30-40% of video duration).
    """
    print(f"[ingest] Uploading {vod_path} (match {match_id})...")
    print(f"[ingest] This involves sending a heavy MP4 file securely over the network. Please wait ~1-2 minutes...")
    video_id = tl_client.upload_and_index(vod_path)
    print(f"[ingest] Indexing complete → video_id={video_id}")

    return {
        "video_id":        video_id,
        "indexed_asset_id": video_id, # for backwards compatibility
        "match_id":        match_id,
    }


def load_match_segments(segments_path: str = "data/match_segments.json") -> dict:
    """
    Load the mapping produced by find_match_segments.py.
    """
    path = Path(segments_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{segments_path} not found.\n"
            f"Run: python scripts/find_match_segments.py --league '<name>' --streams <urls>"
        )
    return json.loads(path.read_text())
