## Goal
Replace the current 480p indexed videos in the Twelve Labs engine with 720p variants to provide higher quality playback and potentially better AI analysis (OCR, feature extraction).

## Constraints
- **Indexing Limits**: Twelve Labs has a fixed number of indexing minutes. Re-uploading everything consumes these minutes.
- **Storage/Bandwidth**: 720p files are roughly 2.5x–3x larger than 480p files, increasing download times and upload durations.
- **State Persistence**: The project uses `video_map.json` and `match_segments.json` to avoid redundant work. These must be updated or cleared to recognize the new 720p videos.
- **Twelve Labs Filename Check**: The current `seed_index.py` skips uploads if it sees the same filename (e.g., `match_123.mp4`) already indexed.

## Known context
- `backend/ingestion.py`: Contains the `yt-dlp` command with hardcoded `--format "bestvideo[height<=480]..."`.
- `dota-intel/scripts/seed_index.py`: Manages the multi-stage pipeline (`download` -> `upload` -> `metadata` -> `highlights` -> `score`).
- `data/segments/`: Local cache directory for video files.
- `data/video_map.json`: Local mapping of `match_id` to Twelve Labs `video_id`.

## Risks
- **Inconsistent State**: If some videos are 480p and others are 720p, the UI experience might feel uneven.
- **Index Pollution**: Leaving old 480p videos in Twelve Labs might consume unnecessary storage/quota if not cleaned up.
- **Highlight Displacement**: If the 720p download has slightly different timing/offsets than the 480p version, existing highlight timestamps might be off by a few seconds.

## Options (2–4)
1.  **Selective Cleanup & Re-run**: Update the ingestion code, manually delete the `data/segments/` folder and `video_map.json`, then re-run the pipeline. This is the "cleanest" but most manual approach.
2.  **Add `--upgrade` flag to `seed_index.py`**: Modify the script to support an upgrade mode that ignores existing caches, deletes the old video from Twelve Labs via API, and proceeds with the 720p download/upload.
3.  **Global Format Update & Cache Invalidation**: Change the default format in `backend/ingestion.py`, and add a script/command to "bust" the cache for all current matches.

## Recommendation
I recommend **Option 3: Global Format Update & Cache Invalidation**. 
It's the most straightforward path for a hackathon:
1.  Update `backend/ingestion.py` to target `720p`.
2.  Provide a simple shell command or script to clear the local segments and reset the `video_map.json`.
3.  Re-run the standard `seed_index.py` pipeline.

## Acceptance criteria
- [ ] `backend/ingestion.py` uses `height<=720` for `yt-dlp`.
- [ ] Local `data/segments/*.mp4` files are replaced with 720p versions.
- [ ] `video_map.json` contains new `video_id`s corresponding to the 720p uploads.
- [ ] Highlights are re-discovered (Stage 4) to ensure timestamps align with the new files.
- [ ] Frontend displays higher resolution videos in the clip player.
