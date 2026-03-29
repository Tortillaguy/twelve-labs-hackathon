# Dota Intel Pilot Demo: Task List

- [ ] **Step 1: Identify Match IDs from Filenames**
  - Create `dota-intel/scripts/discover_existing.py` to list TwelveLabs videos and map them to OpenDota match IDs via `filename`.
  - Status: ⏳ Pending
- [ ] **Step 2: Calibrate Match Start (The "Horn")**
  - Update `TwelveLabsClient` to search for the 0:00 horn sound in the two existing videos.
  - Status: ⏳ Pending
- [ ] **Step 3: AI Highlight Discovery Execution**
  - Update `discover_existing.py` to pick top 2 impact players per match and run `discover_event_anchored` logic.
  - Status: ⏳ Pending
- [ ] **Step 4: Leaderboard Population**
  - Aggregate all stats and highlights into `data/leaderboard.json` and `data/players/*.json`.
  - Status: ⏳ Pending
- [ ] **Step 5: "Premium Obsidian" Final Visual Polish**
  - Update `dota-intel/frontend/src/index.css` and `Leaderboard.tsx` to match the `#0C0C0F` aesthetic.
  - Status: ⏳ Pending
