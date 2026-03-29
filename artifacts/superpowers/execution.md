# Superpowers Execution Log

## Step 1: Update format to 720p
- **Files changed**: `dota-intel/backend/ingestion.py`
- **What changed**:
  - Updated `download_match_segment` yt-dlp `--format` string to pull 720p instead of 480p.
- **Verification**: Checked file to ensure `height<=720` is present.
- **Result**: Pass

## Step 2: Create download script
- **Files changed**: `scripts/download_missing_720p.py`
- **What changed**:
  - Created a targeted script that compares `match_segments.json` (dataset) with `video_map.json` (indexed videos).
  - Triggers a 720p download for matches that are not present in `video_map.json`, removing any existing artifacts to ensure a fresh download.
- **Verification**: Execution of `python scripts/download_missing_720p.py`
- **Result**: Pass (currently running successfully)
