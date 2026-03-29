# Dota Intel Implementation Plan

> [!IMPORTANT]
> **UX/UI Source of Truth**: All frontend design decisions, spacing, colors, and layouts must be derived from @[design.pen]. Refer to this file for any UI implementation tasks.

## Phase 1: Knowledge & Core (COMPLETED)
- [x] **Step 1: Project Bootstrap**
- [x] **Step 3: OpenDota Client Implementation**
- [x] **Step 7: Match Discovery & Correlation**
- [x] **Step 2: Pydantic Domain Models**
- [x] **Step 4: TwelveLabs Client Wrapper (v0.4.0)**
- [x] **Step 5: Scoring Engine**
- [x] **Step 6: Highlight Discovery Logic**
- [x] **Step 9: Pre-Demo Seed Script (Verified)**

## Phase 2: Scaling & Application (IN PROGRESS)
- [ ] **Task 1: Scaling Ingestion (Full Dataset)**
  - Update `dota-intel/scripts/seed_index.py` configuration to handle full 110-minute match segments (increase `MAX_MATCHES` and adjust duration filters).
  - Verify and update `dota-intel/data/match_segments.json` for all 7 verified matches.
  - Run the seed script for all 7 matches and both players in `PLAYER_ROSTER`.
  - Validate scoring outputs in `data/leaderboard.json` and `data/players/*.json`.
- [x] **Task 8: FastAPI Backend Service**
  - Implement dynamic endpoints for leaderboard and player details. (COMPLETED: `backend/main.py`)
- [x] **Task 10: React + Vite Frontend Dashboard**
  - **Single Source of Truth**: @[design.pen].
  - Implement Leaderboard with sticky headers and responsive tables.
  - Implement Detailed Player View with Highlight video embedding (pegasus evidence).
  - Advanced HLS frame-capture for thumbnails. (COMPLETED: `frontend/src/pages/`)
- [ ] **Task 11: Deployment & Final Polish**
  - Use `pencil` MCP tools (`get_screenshot`) for final pixel-perfect validation against @[design.pen].
  - Optimize HLS stream buffering for faster clip switching.
  - Verify overall layout using `pencil_get_screenshot` for comparison.


