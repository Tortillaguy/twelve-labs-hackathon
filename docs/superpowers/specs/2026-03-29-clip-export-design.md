# Clip Export / Copy Link — Design Spec
**Date:** 2026-03-29
**Scope:** Frontend only. No backend changes. No new API endpoints.

---

## Business Case

Social teams need to grab a shareable link to a specific highlight moment before the broadcast ends. This closes the "minute-zero social monetization" loop: find the play via AI, copy the link, paste into Slack/Discord/Twitter draft. Zero friction.

---

## URL Schema

```
/players/{accountId}?clip={video_id}:{start}:{end}[&demo=true]
```

Examples:
```
/players/321580662?clip=abc123vid:1059:1066
/players/321580662?clip=abc123vid:1059:1066&demo=true
```

- `video_id`: TwelveLabs video ID (alphanumeric UUID — no colons, safe delimiter)
- `start` / `end`: integer seconds matching `Highlight.start` / `Highlight.end`
- `demo`: preserved from current page state

**Does the deep-link resolve to something?** Yes. When `PlayerDetail` mounts with a `clip` param, a `useEffect` waits for highlights to load, finds the matching highlight by `video_id + start + end`, and calls `setActiveClip`. The video player opens automatically. Stale/invalid params are silently ignored.

---

## Component Changes

### `HighlightCard` — new share button row

Below the existing timestamp/excitement-score row:

```
[ RAMPAGE badge ]
Massive 5-man teamfight wipe...
17:39 · vs Team Spirit        [🎙 9.2]
                              [🔗] [📋]   ← NEW
```

**Button 1 — Copy Link** (`Link2` icon):
- Copies the deep-link URL to clipboard
- Shows "Link copied!" toast for 2s

**Button 2 — Copy Timestamp** (`Copy` icon):
- Copies `17:39 – 17:46` formatted text
- Shows "Copied! 17:39 – 17:46" toast for 2s

**Style (each button):**
```tsx
className="w-6 h-6 flex items-center justify-center rounded
           border border-obsidian-border text-[#555568]
           hover:border-accent-ai/50 hover:text-accent-ai transition-all"
```

Always visible (not hover-only) — judges need to see the buttons during the demo.

`e.stopPropagation()` on button clicks prevents triggering the card's `onPlay` handler.

### `SearchClipCard` — same treatment

Identical button strip added to the metadata section. `accountId` + `demoMode` added as props.

### Updated prop interfaces

```ts
// HighlightCard
{ highlight: Highlight; onPlay?: () => void; accountId: string; demoMode?: boolean; onCopy: (msg: string) => void }

// SearchClipCard
{ clip: SearchClip; onPlay: () => void; accountId: string; demoMode?: boolean; onCopy: (msg: string) => void }
```

`onCopy` is a callback to `showToast` in `PlayerDetail` — keeps toast state centralized.

---

## Copy-to-Clipboard Implementation

File: `src/utils/clipboard.ts`

```ts
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Fallback for HTTP (non-HTTPS) or older browsers
    const el = document.createElement('textarea')
    el.value = text
    el.style.position = 'fixed'
    el.style.opacity = '0'
    document.body.appendChild(el)
    el.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(el)
    return ok
  }
}
```

---

## Toast Component

Lightweight local state in `PlayerDetail` — no external library.

```ts
const [toast, setToast] = useState<string | null>(null)

const showToast = (msg: string) => {
  setToast(msg)
  setTimeout(() => setToast(null), 2000)
}
```

Render at the bottom of `PlayerDetail`'s main return tree:

```tsx
{toast && (
  <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50
                  flex items-center gap-2 px-4 py-2.5 rounded-lg
                  bg-obsidian-dark border border-accent-ai/40
                  text-[13px] font-semibold text-[#E8E8F0]
                  shadow-[0_0_20px_rgba(167,139,250,0.15)]
                  animate-fade-in-up pointer-events-none">
    <Check size={14} className="text-accent-ai" />
    {toast}
  </div>
)}
```

Add `fade-in-up` animation to `tailwind.config.js`:

```js
keyframes: {
  'fade-in-up': {
    '0%':   { opacity: '0', transform: 'translate(-50%, 8px)' },
    '100%': { opacity: '1', transform: 'translate(-50%, 0)' },
  },
},
animation: {
  'fade-in-up': 'fade-in-up 0.15s ease-out',
},
```

---

## URL Construction Helper

Co-located in `PlayerDetail.tsx` (not a shared utility — only used here):

```ts
function buildClipUrl(
  accountId: string,
  videoId: string,
  start: number,
  end: number,
  demoMode: boolean
): string {
  const base = `${window.location.origin}/players/${accountId}`
  const params = new URLSearchParams({ clip: `${videoId}:${start}:${end}` })
  if (demoMode) params.set('demo', 'true')
  return `${base}?${params.toString()}`
}
```

---

## Deep-Link Auto-Open Logic

```ts
useEffect(() => {
  const clipParam = searchParams.get('clip')
  if (!clipParam || !data?.highlights?.length) return
  const parts = clipParam.split(':')
  if (parts.length < 3) return
  const [videoId, startStr, endStr] = parts
  const start = Number(startStr)
  const end = Number(endStr)
  if (isNaN(start) || isNaN(end)) return
  const match = data.highlights.find(
    hl => hl.video_id === videoId && hl.start === start && hl.end === end
  )
  if (match?.hls_url) {
    setActiveClip({ hlsUrl: match.hls_url, start: match.start, end: match.end })
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [data]) // Run once when player data loads
```

---

## What NOT to Build

- No backend endpoint changes
- No Twitter/X API integration
- No actual video export (MP4, GIF, etc.)
- No Web Share API (navigator.share) — clipboard is enough
- No persistent link storage or short-URL service
- No analytics on copy events
- No deep-link support on Leaderboard page
- No modal for "share options" — one click, done

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `dota-intel/frontend/src/utils/clipboard.ts` | Create — `copyToClipboard` utility |
| `dota-intel/frontend/src/pages/PlayerDetail.tsx` | Add helper, toast, deep-link effect, share buttons |
| `dota-intel/frontend/tailwind.config.js` | Add `fade-in-up` keyframe + animation |

Total: 3 files. No new dependencies.
