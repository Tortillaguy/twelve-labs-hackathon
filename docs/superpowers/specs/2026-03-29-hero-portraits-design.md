# Hero Portrait Images — Design Spec
**Date:** 2026-03-29
**Status:** Ready for implementation

---

## Goal

Replace plain grey placeholder circles in the UI with real Dota 2 hero portrait images from the Steam CDN. Pure frontend change — no backend work.

---

## CDN URL Format

```
https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/<slug>.png
```

Example: `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/dragon_knight.png`

---

## Hero ID → CDN Slug Mapping Strategy

Extend `dota-intel/frontend/src/utils/heroes.ts` with a second export: `HERO_SLUG_MAP: Record<number, string>`. Do NOT modify `HERO_MAP` — display names stay as-is.

Add helper functions:

```typescript
export function getHeroSlug(id: number): string | null {
  return HERO_SLUG_MAP[id] ?? null
}

export function getHeroImageUrl(id: number): string | null {
  const slug = getHeroSlug(id)
  return slug
    ? `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${slug}.png`
    : null
}
```

### Known Overrides (slugs that differ from display name)

Most heroes: lowercase display name + replace spaces with underscores + remove punctuation.

| Hero ID | Display Name | CDN Slug | Reason |
|---------|-------------|----------|--------|
| 1 | Anti-Mage | `antimage` | Compressed, no separator |
| 11 | Nevermore | `nevermore` | Old internal name for Shadow Fiend |
| 22 | Zeus | `zuus` | Old internal name |
| 21 | Windranger | `windrunner` | Old internal name |
| 39 | Queen of Pain | `queenofpain` | No underscores |
| 51 | Clockwerk | `rattletrap` | Old internal name |
| 53 | Nature's Prophet | `furion` | Old internal name |
| 54 | Lifestealer | `life_stealer` | Extra underscore |
| 69 | Doom Bringer | `doom` | Shortened |
| 76 | Outworld Destroyer | `obsidian_destroyer` | Old internal name |
| 91 | Io | `wisp` | Old internal name |
| 108 | Underlord | `abyssal_underlord` | Full internal name |

The full `HERO_SLUG_MAP` covers all IDs in `HERO_MAP`, with standard slugs generated from display names and overrides applied explicitly above them.

---

## New Component: `HeroPortrait`

File: `dota-intel/frontend/src/components/HeroPortrait.tsx`

```typescript
interface HeroPortraitProps {
  heroId: number
  size: 'sm' | 'md' | 'lg'
  className?: string
}
```

Size map:
- `sm`: 20×20px — inline in leaderboard hero row
- `md`: 28×28px — HeroBadge chips in PlayerDetail header
- `lg`: 60×60px — main player avatar in PlayerDetail profile card (matches existing placeholder size)

Render logic:
```
imageUrl exists AND no error → <img> with lazy loading
no imageUrl OR img errored → colored initial circle fallback
```

Fallback: small colored circle with first letter of hero name. Color is deterministic: `heroId % 6` mapped to `['#E84545','#60A5FA','#22C55E','#FFB800','#A78BFA','#FB923C']`.

```tsx
<img
  src={url}
  alt={heroName}
  loading="lazy"
  decoding="async"
  width={sizePixels}
  height={sizePixels}
  className="object-cover rounded-sm"
  onError={() => setImgError(true)}
/>
```

Use `useState<boolean>(false)` for `imgError`. Fixed dimensions on the container prevent layout shift (CLS = 0).

---

## Component Changes

### 1. `utils/heroes.ts`

Add `HERO_SLUG_MAP`, `getHeroSlug`, `getHeroImageUrl`. No changes to existing exports.

### 2. `components/HeroPortrait.tsx` — new file

See spec above.

### 3. `pages/Leaderboard.tsx`

Replace text-only hero list with portrait+name inline pairs:

```tsx
<div className="flex items-center gap-2 flex-wrap mt-0.5">
  {player.top_heroes.slice(0, 3).map(id => (
    <span key={id} className="flex items-center gap-1">
      <HeroPortrait heroId={id} size="sm" />
      <span className="text-[11px] text-[#555568]">{getHeroName(id)}</span>
    </span>
  ))}
</div>
```

Cap at 3 heroes — same as current behavior. Row height stays `h-[54px]`.

### 4. `pages/PlayerDetail.tsx`

**Change 1 — Profile card avatar:**

```tsx
{/* Before */}
<div className="w-[60px] h-[60px] rounded-full bg-accent-dota flex-shrink-0" />

{/* After */}
{topHeroes[0] ? (
  <HeroPortrait heroId={topHeroes[0]} size="lg" className="flex-shrink-0" />
) : (
  <div className="w-[60px] h-[60px] rounded-sm bg-accent-dota flex-shrink-0" />
)}
```

Note: use `rounded-sm` not `rounded-full` — hero portraits are square icons in Dota.

**Change 2 — `HeroBadge` component:**

```tsx
function HeroBadge({ label, heroId }: { label: string; heroId?: number }) {
  return (
    <div className="flex items-center gap-1.5 h-[22px] px-2 rounded-full bg-[#1A1520] border border-[#3D2060]">
      {heroId !== undefined && <HeroPortrait heroId={heroId} size="sm" />}
      <span className="text-[11px] font-semibold text-accent-ai">{label}</span>
    </div>
  )
}
```

Update call site to pass `heroId`:
```tsx
{topHeroes.slice(0, 3).map(id => (
  <HeroBadge key={id} heroId={id} label={getHeroName(id)} />
))}
```

**Change 3 — MatchCard hero name:**

```tsx
<span className="flex items-center gap-1">
  <HeroPortrait heroId={match.hero_id} size="sm" />
  <span className="text-[11px] text-accent-ai">{getHeroName(match.hero_id)}</span>
</span>
```

---

## Error Handling

- `onError` sets `imgError = true` → renders deterministic colored fallback circle
- If `getHeroImageUrl(id)` returns `null`: render fallback immediately, no failed network request
- No console errors — `onError` is silent

---

## Performance

- `loading="lazy"` + `decoding="async"` on every `<img>`
- Fixed width/height on every `<img>` — zero layout shift
- Leaderboard renders max ~20 rows; PlayerDetail renders ~3 badges — browser native lazy loading is sufficient
- Images served from Cloudflare CDN — fast, no CORS issues for `<img>` tags
- No preloading, no custom IntersectionObserver needed

---

## What NOT to Build

- No backend endpoint for hero images
- No custom avatar upload or player-specific portraits
- No hero portrait in the Header avatar circle (that's a user account avatar)
- No animated portrait transitions or hover zoom
- No sprite sheet or bundled assets — CDN URLs only
- No TypeScript codegen from OpenDota API

---

## File Summary

| File | Action |
|------|--------|
| `dota-intel/frontend/src/utils/heroes.ts` | Add slug map + helpers |
| `dota-intel/frontend/src/components/HeroPortrait.tsx` | Create new component |
| `dota-intel/frontend/src/pages/Leaderboard.tsx` | Replace text list with portrait+name |
| `dota-intel/frontend/src/pages/PlayerDetail.tsx` | Update avatar, HeroBadge, MatchCard |
