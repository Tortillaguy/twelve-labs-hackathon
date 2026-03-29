# Twitch API Research: Video Metadata & Correlation

This file summarizes the research on the Twitch API (`https://dev.twitch.tv/docs/api/videos`) and how it can be used to correlate Dota 2 matches with Twitch VOD segments for the **Dota Intel** project.

## Key Endpoints

### 1. [Get Videos](https://dev.twitch.tv/docs/api/reference#get-videos)
- **Endpoint**: `GET https://api.twitch.tv/helix/videos`
- **Purpose**: Retrieve metadata for VODs, highlights, or uploads.
- **Key Response Fields**:
    - `id`: Unique ID of the video.
    - `created_at`: **Critical**. ISO 8601 timestamp (UTC) of when the video was created. For "archive" types (VODs), this is the **stream start time**.
    - `duration`: The length of the video (e.g., `3h42m12s`).
    - `url`: Direct link to the VOD.
    - `type`: `archive` (VOD), `highlight`, or `upload`.

### 2. [Get Users](https://dev.twitch.tv/docs/api/reference#get-users)
- **Endpoint**: `GET https://api.twitch.tv/helix/users`
- **Purpose**: Resolve a channel login name (e.g., `pgl_dota2`) to a `user_id`, which is required for the `Get Videos` endpoint.

---

## Correlation Logic (Twitch API vs. yt-dlp)

The core requirement in **Task 7** is finding the offset of a match within a VOD:
`Offset = Match Start Time - Stream Start Time`

### Comparison:
| Method | Tool | Metadata Field | Pros | Cons |
| :--- | :--- | :--- | :--- | :--- |
| **Twitch API** | REST API | `created_at` | Official, reliable source. | Requires OAuth (App Access Token), Client ID. Twitch-only. |
| **yt-dlp** | Subprocess | `timestamp` | Works for YouTube & Twitch. No auth (usually). | Relies on yt-dlp extraction logic. |

**Conclusion**: The Twitch API confirms that `created_at` is the reliable "zero-point" for the VOD. Since the project needs to support both Twitch and YouTube (per Task 7), **`yt-dlp` remains the most versatile choice**, but the Twitch API can serve as a fallback or verification layer if `yt-dlp` metadata fails.

---

## Authentication & Rate Limits

- **Auth**: Requires `Client-Id` and `Authorization: Bearer <token>`. Recommended: **Client Credentials Grant** (App Access Token).
- **Rate Limits**: 800 requests per minute for most apps.
- **Header for Rate Limit**: `Ratelimit-Remaining`, `Ratelimit-Reset`.

---

## Implementation Recommendations for find_match_segments.py

If a Twitch VOD is provided, the `created_at` timestamp can be used to cross-verify the `timestamp` extracted by `yt-dlp`.

```python
# Example logic for Twitch-specific metadata via API
def get_twitch_start_time(video_id: str, access_token: str, client_id: str):
    headers = {
        "Client-Id": client_id,
        "Authorization": f"Bearer {access_token}"
    }
    url = f"https://api.twitch.tv/helix/videos?id={video_id}"
    # ... parse response["data"][0]["created_at"] ...
```
