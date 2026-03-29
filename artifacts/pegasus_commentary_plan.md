# Implementation Plan: Pegasus Commentary

Implement AI-generated insights for highlights using TwelveLabs Pegasus 1.2, as specified in `docs/superpowers/specs/2026-03-29-pegasus-commentary-design.md`.

## Tasks

### 1. Backend: Update Highlight Model
- **File:** `dota-intel/backend/models.py`
- **Action:** Add `ai_insight: Optional[str] = None` to the `Highlight` Pydantic model.
- **Verification:** Run `pytest dota-intel/backend/tests/test_models.py` (if it exists) or verify deserialization of old/new JSON.

### 2. Backend: Update TwelveLabs Client Prompt
- **File:** `dota-intel/backend/twelvelabs_client.py`
- **Action:** 
    - Update the prompt f-string in `analyze_clip()` to request `ai_insight`.
    - Update the fallback dictionary to include `"ai_insight": None`.
- **Verification:** Mock the API response and verify `analyze_clip` returns the new field.

### 3. Backend: Update Highlight Discovery
- **File:** `dota-intel/backend/highlights.py`
- **Action:** 
    - Update `discover_highlights` and `discover_player_highlights` to pass `ai_insight=analysis.get("ai_insight")` when creating `Highlight` instances.
- **Verification:** Unit tests for highlight discovery.

### 4. Data: Hand-craft Demo Insights
- **Files:** `/Users/cacho/Documents/repos/twelve-labs-hackathon/data/mock/players/*.json`
- **Action:** Manually add `"ai_insight": "..."` to each highlight in the mock JSON files (e.g., `yatoro.json`, `ame.json`, etc.).
- **Verification:** Verify JSON is still valid and has the new fields.

### 5. Frontend: Implement AI Insight UI
- **File:** `dota-intel/frontend/src/pages/PlayerDetail.tsx` (and potentially other files using `Highlight` interface)
- **Action:** 
    - Update `Highlight` interface to include `ai_insight?: string`.
    - Modify `HighlightCard` component to render the AI insight pill with Sparkles icon as designed.
- **Verification:** Manual visual check in browser with mock data.

## Overall Verification
- Re-run `seed_index.py` or similar if possible (or mock its behavior) to ensure the flow works from ingestion to UI.
- Verify that old highlights still load without errors (graceful degradation).
