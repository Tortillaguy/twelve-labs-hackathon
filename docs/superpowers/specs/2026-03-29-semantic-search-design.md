# Semantic Video Search — Design Spec
**Date:** 2026-03-29
**Status:** Ready for implementation

---

## 1. Overview

Repurpose the existing Header search bar to query TwelveLabs Marengo 3.0 for semantic video moments. When a user types "Rampage", "teamfight", or "Anti-Mage", the bar fires a debounced search against `/api/search`, displays matching VOD clips in a dropdown (thumbnail + timestamp + transcription), and lets the user preview the clip in a modal with an HLS player.

The backend endpoint (`GET /api/search`) is **already implemented** in `main.py`. No backend changes are required.

---

## 2. Architecture Overview

```
[User types in Header input]
        |
        v  350ms debounce + AbortController
[Header internal state: query, results, status]
        |
        v  fetch('/api/search?q=...&limit=6')
[FastAPI GET /api/search]
        |
        v
[TwelveLabsClient.search_highlights()]  — Marengo 3.0 semantic search
        |
        v
[clips: enriched with hls_url, video_thumbnail_url]
        |
        v
[SearchDropdown renders below input]
        |
        v  user clicks result
[ClipPreviewModal: HLS player seeked to clip.start]
```

**Key design decision:** Semantic search state lives entirely inside `Header`. The existing `onSearchChange` prop (used by Leaderboard for player name filtering) continues to fire on every keystroke, preserving backward compatibility.

---

## 3. API Contract

The endpoint is already implemented. No changes needed.

### Request

```
GET /api/search?q={query}&limit={n}
```

| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `q` | string | yes | — | Semantic query text |
| `limit` | int | no | 10 | Frontend requests 6 |

Frontend fires only when `q.length >= 2`.

### Response

```json
{
  "clips": [
    {
      "video_id": "abc123",
      "start": 1423.5,
      "end": 1438.0,
      "score": 0.87,
      "transcription": "OH THE RAMPAGE! He got all five!",
      "thumbnail_url": "https://cdn.twelvelabs.io/...",
      "hls_url": "https://stream.twelvelabs.io/...m3u8",
      "video_thumbnail_url": "https://cdn.twelvelabs.io/..."
    }
  ]
}
```

### Frontend TypeScript type

File: `dota-intel/frontend/src/types/search.ts`

```typescript
export interface SearchClip {
  video_id: string
  start: number
  end: number
  score: number
  transcription: string | null
  thumbnail_url: string | null
  hls_url: string | null
  video_thumbnail_url: string | null
}
```

---

## 4. Component Breakdown

### 4.1 `Header.tsx` — modifications

**Changes:**
- Import `SearchClip` type and `SearchDropdown`, `ClipPreviewModal` components
- Add internal state: `results: SearchClip[]`, `status: 'idle' | 'loading' | 'error' | 'done'`
- Add `selectedClip: SearchClip | null` state for modal
- Add `wrapperRef` on the search container div for click-outside detection
- Add `useEffect` with 350ms debounce + `AbortController` that fires when `query.length >= 2`
- On `Escape` keydown: clear results, reset to idle
- Continue calling `onSearchChange(value)` on every input change (player filter unchanged)
- Render `<SearchDropdown>` below the input when `status !== 'idle'`
- Render `<ClipPreviewModal>` when `selectedClip !== null`

**Input changes:**
- Placeholder changes to `"Search players or moments..."`
- Width increases to `w-[240px]` to fit longer placeholder
- Add loading spinner (replacing Search icon) when `status === 'loading'`

**`HeaderProps` interface:** No new required props. Internally self-contained.

### 4.2 `SearchDropdown.tsx` — new component

Location: `dota-intel/frontend/src/components/SearchDropdown.tsx`

```typescript
interface SearchDropdownProps {
  status: 'loading' | 'error' | 'done'
  clips: SearchClip[]
  query: string
  onSelect: (clip: SearchClip) => void
}
```

**Layout:** `absolute top-full mt-1.5 right-0 w-[420px] bg-obsidian-dark border border-obsidian-border rounded-lg overflow-hidden z-[100] shadow-2xl`

**States:**
- `loading`: 3 skeleton rows using `animate-pulse bg-obsidian-lighter` bars
- `error`: Single row with warning icon + "Search unavailable"
- `done` + empty: Single row with Search icon + `No moments found for "{query}"`
- `done` + results: Up to 6 `SearchResultRow` items

**Header row:** `"TWELVE LABS AI · {clips.length} moment{s} found"` in `text-[10px] text-accent-ai` — reinforces the TwelveLabs showcase for demo.

### 4.3 `SearchResultRow` — inline sub-component of SearchDropdown

For each clip:

| Region | Content |
|--------|---------|
| Left (60×34px) | `thumbnail_url` img, fallback to `video_thumbnail_url`, fallback to gray div |
| Center | Timestamp badge (`MM:SS` from `start`), score dot (green ≥0.8, yellow ≥0.6, red <0.6), truncated `transcription` (2 lines max, `text-[12px]`) |
| Right | Play icon button |

Row height: `h-[54px] px-3`. On hover: `bg-obsidian-lighter/30`. On click: `onSelect(clip)`.

Thumbnail uses `<img loading="lazy">` — no HLS seek in the dropdown.

### 4.4 `ClipPreviewModal.tsx` — new component

Location: `dota-intel/frontend/src/components/ClipPreviewModal.tsx`

```typescript
interface ClipPreviewModalProps {
  clip: SearchClip
  onClose: () => void
}
```

**Layout:** `fixed inset-0 z-[200] bg-black/80 backdrop-blur-sm flex items-center justify-center`

**Inner panel:** `bg-obsidian-dark border border-obsidian-border rounded-xl w-[760px] max-w-[90vw] overflow-hidden`

**Video player:**
- `<video>` element using the same `Hls.js` initialization pattern from `PlayerDetail.tsx` (lines 62–77)
- Auto-seeks to `clip.start` on `MANIFEST_PARSED`
- `autoPlay muted controls` attributes
- 16:9 aspect ratio container

**Below player:**
- Timestamp range: `MM:SS → MM:SS`
- Score badge with color coding
- `transcription` text if present
- `X` close button in top-right corner

Click outside the inner panel: calls `onClose()`. `Escape` key: calls `onClose()`.

---

## 5. Data Flow Diagram

```
User input event
      │
      ▼
Header.onChange(value)
      ├──► onSearchChange(value)   [prop call — Leaderboard player filter still works]
      └──► setQuery(value)         [internal state]
                │
                ▼
       debounce timer (350ms)
       AbortController created,
       previous request aborted
                │
         query.length >= 2?
         NO ──► status = 'idle', results = []
         YES ──► status = 'loading'
                │
                ▼
       fetch('/api/search?q=...&limit=6', { signal })
                │
         response OK?
         NO ──► status = 'error'
         YES ──► results = data.clips, status = 'done'
                │
                ▼
       <SearchDropdown status results query onSelect />
                │
          user clicks row
                │
                ▼
       setSelectedClip(clip)
                │
                ▼
       <ClipPreviewModal clip onClose />
```

---

## 6. Error and Empty States

| State | Trigger | UI |
|-------|---------|-----|
| Idle | `query.length < 2` | Dropdown not rendered |
| Loading | Request in-flight | 3 skeleton rows, `animate-pulse` |
| Empty | `clips.length === 0` | "No moments found for '{query}'" |
| Error | HTTP error / network failure | "Search unavailable" |
| Stale close | Click outside or `Escape` | Dropdown unmounts, status → 'idle' |

---

## 7. Performance Considerations

- **Debounce: 350ms.** Responsive without hammering TwelveLabs on every keystroke.
- **Result limit: 6.** Dropdown fits without scrolling; enough for demo impact.
- **AbortController.** Each new request cancels the previous in-flight one. Prevents stale results from a slow earlier query landing after a faster later query.
- **Minimum query length: 2 characters.** Prevents API calls on single-character inputs.
- **No HLS in dropdown thumbnails.** Use static `thumbnail_url` from TwelveLabs. The HLS seek-and-capture pattern is expensive — only run it inside the modal when the user explicitly opens a clip.
- **No frontend result caching.** Demo should show live TwelveLabs responses. Freshness > performance for a hackathon showcase.
- **`<img loading="lazy">`** on thumbnails so off-screen rows don't block rendering.

---

## 8. What NOT to Build

- No backend changes — `/api/search` is already implemented and correct
- No `/search` page route — dropdown-in-header is the complete UX
- No server-side caching (Redis, etc.)
- No pagination or "load more" in the dropdown
- No keyboard arrow-key navigation in dropdown results
- No query history or recent searches
- No search analytics
- No debounce hook extraction into a shared utility file
- No strict player name matching in the modal CTA
- No dedicated search result page that persists after navigation

---

## 9. Files to Create / Modify

| Action | Path |
|--------|------|
| Modify | `dota-intel/frontend/src/components/Header.tsx` |
| Create | `dota-intel/frontend/src/components/SearchDropdown.tsx` |
| Create | `dota-intel/frontend/src/components/ClipPreviewModal.tsx` |
| Create | `dota-intel/frontend/src/types/search.ts` |
| No change | `dota-intel/backend/main.py` |
| No change | `dota-intel/backend/twelvelabs_client.py` |
