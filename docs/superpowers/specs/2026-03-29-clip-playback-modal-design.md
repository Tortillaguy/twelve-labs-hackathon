# Inline Clip Playback Modal — Design Spec
**Date:** 2026-03-29
**Status:** Ready for implementation

---

## Goal

Replace the fragmented in-page video player in `PlayerDetail.tsx` with a global modal overlay that plays any clip from anywhere in the app. Triggered by clicking any clip card, plays the HLS stream trimmed to `start → end`, shows relevant metadata.

---

## State Management Decision

**Chosen approach: React Context**

| Approach | Verdict |
|---|---|
| React Context + hook | **Recommended** — zero prop-drilling, clean separation, ~40 lines setup |
| URL params | Rejected — encoding HLS URLs in query strings is fragile; no sharing requirement |
| Prop drilling | Rejected — card components are 3+ levels deep across two separate page trees |

---

## Architecture

```
App.tsx
  └── ClipPlayerProvider                 (new — wraps entire tree)
        ├── ClipPlayerModal              (new — portal to document.body)
        └── BrowserRouter
              ├── Route "/" → Leaderboard
              └── Route "/players/:id" → PlayerDetail
                    ├── HighlightCard    (calls openClip)
                    └── SearchClipCard   (calls openClip)
```

`ClipPlayerModal` is rendered via `ReactDOM.createPortal` into `document.body` — above `Header`'s `z-50`. Returns `null` when `activeClip === null` (zero DOM cost when idle). The provider+modal are siblings to `BrowserRouter` so the modal survives route transitions.

---

## Data Type

```typescript
// src/context/ClipPlayerContext.tsx
export interface ClipData {
  hlsUrl: string
  start: number
  end: number
  playerName?: string
  hero?: string
  matchId?: number
  opponent?: string
  aiScore?: number        // excitement_score from Highlight, score from SearchClip
  eventLabel?: string     // RAMPAGE | TEAMFIGHT | GODLIKE | OBJECTIVE | CLUTCH
  transcription?: string
}
```

---

## Component Breakdown

### `src/context/ClipPlayerContext.tsx` — new file

- Defines and exports `ClipData` type
- `ClipPlayerContext` exposes `{ activeClip, openClip, closeClip }`
- `ClipPlayerProvider` holds `useState<ClipData | null>(null)`
- `useClipPlayer()` hook — throws if used outside provider

### `src/components/ClipPlayerModal.tsx` — new file

Renders `null` when `activeClip === null`.

When active:

```
<Portal to document.body>
  <div role="dialog" aria-modal="true"
       class="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center"
       onClick={closeClip}>
    <div class="relative w-full max-w-[900px] bg-obsidian-dark border border-obsidian-border rounded-xl overflow-hidden"
         onClick={e => e.stopPropagation()}>

      {/* Close button — autofocused on open */}
      <button ref={closeButtonRef} onClick={closeClip}
              class="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-black/70 hover:bg-black">
        <X size={16} />
      </button>

      {/* HLS Video (16:9 container) */}
      <HlsPlayerInModal hlsUrl={...} startTime={...} endTime={...} />

      {/* Metadata strip */}
      <div class="p-4 space-y-2">
        <EventLabelBadge label={eventLabel} />
        <div class="flex items-center justify-between">
          <span>{playerName} · {hero} · vs {opponent}</span>
          <AiScorePill score={aiScore} />
        </div>
        <div class="text-xs text-[#555568]">
          {formatTime(start)} – {formatTime(end)} in VOD
        </div>
        {transcription && (
          <blockquote class="text-xs italic text-[#9898B0]">"{transcription}"</blockquote>
        )}
      </div>
    </div>
  </div>
</Portal>
```

Keyboard: `useEffect` adds `keydown` listener for `Escape` → `closeClip()`. Removed on cleanup.

### `HlsPlayerInModal` — private component inside ClipPlayerModal.tsx

Extracted verbatim from existing `HlsPlayer` in `PlayerDetail.tsx` (lines 443–493). No logic changes:
- `Hls` config: `{ startPosition: startTime, maxBufferLength: 30, maxMaxBufferLength: 60 }`
- `MANIFEST_PARSED` → `video.play()`
- `timeupdate` listener → `video.pause()` when `currentTime >= endTime`
- Safari fallback: `canPlayType('application/vnd.apple.mpegurl')` → native src + `loadedmetadata` seek
- `useEffect` cleanup: `hls.destroy()` — handles modal-close unmount correctly

`EventLabelBadge`: reuses `typeColors` map from existing `HighlightCard`. `AiScorePill`: reuses `Mic2` + gold number pattern.

### Changes to `src/pages/PlayerDetail.tsx`

**Remove:**
- `activeClip` state (`useState`)
- Inline `{activeClip && <div>...<HlsPlayer /></div>}` render block
- `HlsPlayer` component definition (lines 443–493) — moved to `ClipPlayerModal.tsx`

**Add:**
```typescript
const { openClip } = useClipPlayer()
```

**Update `HighlightCard` call sites:**
```typescript
onPlay={() => hl.hls_url && openClip({
  hlsUrl: hl.hls_url,
  start: hl.start,
  end: hl.end,
  playerName: player.name,
  eventLabel: hl.play_type,
  aiScore: hl.excitement_score,
  opponent: hl.opponent,
  matchId: hl.match_id,
})}
```

`HighlightCard` and `SearchClipCard` component signatures unchanged — they still receive `onPlay: () => void`.

### Changes to `src/App.tsx`

```typescript
import { ClipPlayerProvider } from './context/ClipPlayerContext'
import ClipPlayerModal from './components/ClipPlayerModal'

export default function App() {
  return (
    <ClipPlayerProvider>
      <ClipPlayerModal />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Leaderboard />} />
          <Route path="/players/:accountId" element={<PlayerDetail />} />
        </Routes>
      </BrowserRouter>
    </ClipPlayerProvider>
  )
}
```

### `Leaderboard.tsx` — No changes

The leaderboard "N clips" badge currently navigates to PlayerDetail. This is the correct UX and stays as-is.

---

## HLS Playback: Start/End Time Trimming

- **Seek to start:** `startPosition: startTime` in the `Hls` constructor config
- **Pause at end:** `timeupdate` listener checks `currentTime >= endTime` → `video.pause()`
- **Cleanup:** Modal unmount triggers `useEffect` cleanup → `hls.destroy()` + listener removal
- **Re-open same clip:** `useEffect` dependency array handles re-initialization

---

## Keyboard and Accessibility

| Behavior | Implementation |
|---|---|
| `Escape` closes | `keydown` listener on `window`, removed on cleanup |
| Backdrop click closes | `onClick={closeClip}` on outer div; `stopPropagation` on inner panel |
| Close button | `onClick={closeClip}` |
| Focus on open | `closeButtonRef.current?.focus()` in mount `useEffect` |
| `aria-modal` | `role="dialog" aria-modal="true" aria-label="Clip player"` |
| Focus trap | Out of scope for hackathon |
| Return focus on close | Out of scope for hackathon |

---

## What NOT to Build

- Clip queue / playlist
- Shareable deep-link URL (separate spec)
- Fullscreen API
- Custom playback controls (use native `controls` attribute)
- Open/close animation
- Keyboard scrubbing shortcuts (J/K/L)
- Mobile / touch optimizations
- Changes to Leaderboard clip cards (they navigate to PlayerDetail — that's fine)

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `src/context/ClipPlayerContext.tsx` | Create |
| `src/components/ClipPlayerModal.tsx` | Create |
| `src/App.tsx` | Add provider + modal |
| `src/pages/PlayerDetail.tsx` | Remove local state/player, wire `openClip` |

Total: 2 new files, 2 modified. No new dependencies (`hls.js` already installed, `createPortal` is built into React 19).

---

## Success Criteria

- Clicking any `HighlightCard` or `SearchClipCard` opens the modal with the correct clip
- Video begins playing from `start` seconds within 2 seconds of modal open
- Video pauses at `end` seconds
- `Escape` and backdrop click both close the modal
- HLS instance is destroyed on close (no network leak)
- Navigating between routes while modal is open keeps modal visible (portal survives route change)
- No regression on thumbnail capture (`useClipThumbnail` hook is unchanged)
