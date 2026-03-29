# Pegasus AI Commentary — Design Spec
**Date:** 2026-03-29
**Status:** Ready for implementation

---

## Goal

Replace the raw caster transcript snippet on highlight cards with a Pegasus 1.2-generated one-sentence insight explaining WHY a moment matters competitively. Generated at ingestion time, cached on disk, shown distinctly from the description text on every highlight card.

Example:
> "Yatoro turns a 1v4 high-ground defense into a full RAMPAGE, single-handedly swinging the game's momentum."

---

## Decision: When to Generate

**Chosen approach: at ingestion time inside `analyze_clip()`, stored in the JSON cache.**

Rationale:
- `analyze_clip()` already calls the Pegasus `/analyze` endpoint once per clip. Adding `ai_insight` to the same prompt costs zero extra API calls.
- The result flows naturally into `Highlight.model_dump_json()` → `cache.write_player()` → persistent JSON on disk.
- Every subsequent page load reads from cache — zero re-generation latency.
- Demo mode is handled by pre-populating `ai_insight` in the mock JSON files.

Rejected alternatives:
- **On-demand (per page load):** 5–15s latency per card — unacceptable for demo.
- **Separate `/api/insights` endpoint:** extra round-trip, more code, same result.

---

## Pegasus API Change

No new endpoint. Extend the existing `analyze_clip()` prompt in `twelvelabs_client.py`.

**Append to the return-JSON instruction:**

```
ai_insight (one sentence explaining why this moment matters strategically or emotionally
            in a Dota 2 broadcast — vivid, specific, max 20 words; null if unclear).
```

Full updated return-JSON spec in the prompt:

```
Return JSON with:
  play_type (RAMPAGE | GODLIKE | TEAMFIGHT | OBJECTIVE | CLUTCH),
  excitement_score (0-10),
  streak_tier (kill streak tier or null),
  description (one sentence on what the player did),
  player_name (name from caster or banner or null),
  ai_insight (one sentence: why this moment matters strategically or emotionally in
              a Dota 2 broadcast — vivid, specific, max 20 words; null if unclear).
```

Update the fallback dict to include `"ai_insight": None` explicitly.

---

## Data Model Changes

### `backend/models.py` — `Highlight`

```python
class Highlight(BaseModel):
    video_id: str
    start: float
    end: float
    play_type: str
    excitement_score: float
    description: str
    player_name: Optional[str] = None
    match_id: Optional[int] = None
    opponent: Optional[str] = None
    thumbnail_url: Optional[str] = None
    ai_insight: Optional[str] = None   # NEW
```

Pydantic forward-compatibility: existing JSON files without `ai_insight` deserialize without error (field defaults to `None`).

### Frontend `Highlight` interface — `PlayerDetail.tsx`

```typescript
interface Highlight {
  // ...existing fields...
  ai_insight?: string   // NEW
}
```

---

## Backend Changes

### 1. `backend/twelvelabs_client.py` — `analyze_clip()`

Extend the prompt f-string to include `ai_insight` in the return-JSON spec (see above). Add `"ai_insight": None` to the fallback dict. No other changes — existing JSON extraction already handles arbitrary keys.

### 2. `backend/highlights.py` — both discover functions

In every `Highlight(...)` constructor call:

```python
Highlight(
    ...existing fields...,
    ai_insight=analysis.get("ai_insight"),   # NEW
)
```

### 3. `backend/cache.py` — No changes required

`write_player()` uses `model_dump_json()` which includes the new field automatically. `read_player()` uses `model_validate_json()` which handles it. Fully transparent.

### 4. `backend/main.py` — No changes required

`get_player()` passes `hl.model_dump()` through to the response, which includes `ai_insight`.

---

## Frontend Changes

### `pages/PlayerDetail.tsx` — `HighlightCard`

Add the AI insight pill between the play type badge row and the description text:

```tsx
{highlight.ai_insight && (
  <div className="flex items-start gap-1.5 bg-[#1A0A33]/60 border border-[#3D2475]/50 rounded px-2 py-1.5">
    <Sparkles size={10} className="text-accent-ai mt-0.5 flex-shrink-0" />
    <span className="text-[10px] italic text-accent-ai/90 leading-tight line-clamp-2">
      {highlight.ai_insight}
    </span>
  </div>
)}
```

Visual hierarchy:
1. Play type badge (RAMPAGE / TEAMFIGHT / etc.)
2. **AI Insight pill** — purple tint, Sparkles icon, italic — clearly AI-sourced
3. Description text — white, bold
4. Timestamp + excitement score

`Sparkles` is already imported. No new imports needed.

When `ai_insight` is `null`/`undefined`, the pill does not render. No broken state.

---

## Demo Mode Strategy

Pre-populate `ai_insight` in all mock player JSON files under `data/mock/players/`. Hand-craft values for maximum demo polish:

Example for Yatoro's RAMPAGE highlight:
```json
"ai_insight": "Yatoro turns a 1v4 high-ground defense into a full RAMPAGE, single-handedly swinging the game's momentum."
```

Example for a TEAMFIGHT highlight:
```json
"ai_insight": "A precisely-timed Chronosphere traps three heroes, converting a losing skirmish into a decisive team wipe."
```

Apply to all highlights in all mock player files (~5 players × ~2–3 highlights each = ~12 hand-crafted strings).

---

## Fallback Strategy

Three layers, in order:

1. **Pegasus returns `ai_insight`:** Display it in the pill.
2. **Field is null/missing:** Pill is hidden; `description` shown as normal. No visible degradation.
3. **Pegasus call throws:** `analyze_clip()` catches all exceptions and returns fallback dict with `ai_insight: None`. Highlight is still stored and shown without the insight.

---

## Risk Notes

- Pegasus may occasionally produce `ai_insight` longer than 20 words. `line-clamp-2` handles gracefully.
- The `/analyze` endpoint uses `temperature: 0.2` — produces stable, low-variance output.
- Re-ingestion overwrites cached player files, regenerating insights automatically.

---

## What NOT to Build

- No streaming / progressive loading of insights
- No "refresh insight" button — insights are immutable once cached
- No confidence score badge next to the insight
- No insight for SearchClipCard (Global AI Discovery section) — those clips are not cached
- No separate `/api/insights` endpoint
- No localization / multi-language support
- No insight editing / admin UI

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `dota-intel/backend/models.py` | Add `ai_insight` field to `Highlight` |
| `dota-intel/backend/twelvelabs_client.py` | Extend `analyze_clip()` prompt |
| `dota-intel/backend/highlights.py` | Pass `ai_insight` in `Highlight(...)` constructor |
| `data/mock/players/*.json` | Hand-write `ai_insight` for all demo highlights |
| `dota-intel/frontend/src/pages/PlayerDetail.tsx` | Update interface + `HighlightCard` body |

Total: 5 files modified, 0 new files, 0 new dependencies.
