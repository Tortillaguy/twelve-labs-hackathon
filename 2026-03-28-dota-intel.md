# Dota Intel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-screen web app that ranks ESL Pro Circuit Dota 2 players by an AI Impact Score (computed by TwelveLabs Pegasus) and surfaces auto-discovered video highlights from indexed Twitch VODs.

**Architecture:** FastAPI backend pre-computes a leaderboard by fusing OpenDota match stats with TwelveLabs highlight analysis; results are written to JSON files by a one-time seed script and served at runtime. React + Tailwind frontend renders two screens: a competition leaderboard and a per-player detail view with video clip cards.

**Tech Stack:** Python 3.11, FastAPI, httpx, twelvelabs SDK, yt-dlp, React 18, TypeScript, Tailwind CSS, Vite

---

## File Map

```
dota-intel/
├── backend/
│   ├── main.py              # FastAPI app, CORS, routes
│   ├── models.py            # Pydantic models (shared source of truth)
│   ├── opendota.py          # OpenDota REST client (async httpx)
│   ├── twelvelabs_client.py # TwelveLabs SDK wrapper
│   ├── highlights.py        # Highlight discovery + Pegasus enrichment
│   ├── scoring.py           # AI Impact Score formula + player ranking
│   └── ingestion.py         # VOD download (yt-dlp) + TwelveLabs upload
├── scripts/
│   ├── find_match_segments.py  # Scans stream URLs → maps each match_id to its time window
│   └── seed_index.py           # One-time pre-demo pipeline: fetch → download segment → index → score → write JSON
├── data/                    # Written by scripts, read by API at runtime
│   ├── match_segments.json  # Output of find_match_segments.py: match_id → {stream_url, offset, duration}
│   ├── leaderboard.json
│   └── players/
│       └── {account_id}.json
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api.ts           # Typed fetch functions
│   │   ├── types.ts         # TypeScript types mirroring Pydantic models
│   │   ├── pages/
│   │   │   ├── Leaderboard.tsx
│   │   │   └── PlayerDetail.tsx
│   │   └── components/
│   │       ├── NavBar.tsx
│   │       ├── StatCard.tsx
│   │       ├── PlayerRow.tsx
│   │       ├── MatchCard.tsx
│   │       └── ClipCard.tsx
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── tests/
│   ├── test_opendota.py
│   ├── test_scoring.py
│   └── test_highlights.py
├── .env.example
├── requirements.txt
└── README.md
```

---

### Task 1: Project Bootstrap

**Files:**
- Create: `dota-intel/` (root)
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `backend/main.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p dota-intel/{backend,scripts,data/players,tests,frontend}
cd dota-intel
```

- [ ] **Step 2: Write requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
twelvelabs==0.4.0
yt-dlp==2024.11.4
python-dotenv==1.0.1
pytest==8.3.0
pytest-asyncio==0.24.0
respx==0.21.1
```

- [ ] **Step 3: Write .env.example**

```
TWELVELABS_API_KEY=your_key_here
TWELVELABS_INDEX_ID=          # filled after seed_index.py creates the index
OPENDOTA_BASE_URL=https://api.opendota.com/api
ESL_LEAGUE_NAME=ESL Pro Circuit
```

- [ ] **Step 4: Write the failing health check test**

`tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd dota-intel
pip install -r requirements.txt
PYTHONPATH=. pytest tests/test_health.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend'`

- [ ] **Step 6: Write backend/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Dota Intel")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Run test to verify it passes**

```bash
PYTHONPATH=. pytest tests/test_health.py -v
```
Expected: `PASSED`

- [ ] **Step 8: Commit**

```bash
git init && git add .
git commit -m "feat: project bootstrap with FastAPI health endpoint"
```

---

### Task 2: Pydantic Models

**Files:**
- Create: `backend/models.py`

- [ ] **Step 1: Write backend/models.py**

```python
from pydantic import BaseModel
from typing import Optional

class KillEvent(BaseModel):
    time: int        # seconds from game start (OpenDota kills_log[].time)
    killer_id: int   # account_id
    victim_id: int

class MatchDetail(BaseModel):
    match_id: int
    duration: int    # seconds
    start_time: int  # Unix epoch
    radiant_win: bool
    kills_log: list[KillEvent]
    players: list["MatchPlayer"]

class MatchPlayer(BaseModel):
    account_id: Optional[int] = None
    player_slot: int           # 0-4 radiant, 128-132 dire
    hero_id: int
    kills: int
    deaths: int
    assists: int
    gold_per_min: int
    net_worth: int

class PlayerStats(BaseModel):
    account_id: int
    name: str
    team: str
    matches: int
    wins: int
    total_kills: int
    total_deaths: int
    total_assists: int
    avg_gpm: float
    hero_ids: list[int]        # most played hero IDs

class Highlight(BaseModel):
    video_id: str              # TwelveLabs video_id
    start: float               # seconds into VOD
    end: float
    play_type: str             # RAMPAGE | GODLIKE | TEAMFIGHT | OBJECTIVE | CLUTCH
    excitement_score: float    # 0-10, from Pegasus audio analysis
    description: str
    player_name: Optional[str] = None
    match_id: Optional[int] = None
    opponent: Optional[str] = None
    thumbnail_url: Optional[str] = None

class RankedPlayer(BaseModel):
    rank: int
    account_id: int
    name: str
    team: str
    kda: str                   # "12 / 2 / 8"
    avg_kda_ratio: float
    avg_gpm: float
    win_rate: float
    ai_impact_score: float
    highlight_count: int
    top_heroes: list[int]

class PlayerDetail(BaseModel):
    player: RankedPlayer
    recent_matches: list["MatchSummary"]
    highlights: list[Highlight]

class MatchSummary(BaseModel):
    match_id: int
    opponent: str
    won: bool
    duration_str: str          # "42:18"
    kills: int
    deaths: int
    assists: int
    gpm: int
    hero_id: int
    clip_count: int

class LeaderboardResponse(BaseModel):
    competition: str
    total_matches: int
    total_teams: int
    total_highlights: int
    avg_kda_top10: float
    players: list[RankedPlayer]

MatchDetail.model_rebuild()
PlayerDetail.model_rebuild()
```

- [ ] **Step 2: Commit**

```bash
git add backend/models.py
git commit -m "feat: pydantic models for all domain types"
```

---

### Task 3: OpenDota Client

**Files:**
- Create: `backend/opendota.py`
- Create: `tests/test_opendota.py`

- [ ] **Step 1: Write failing tests**

`tests/test_opendota.py`:
```python
import pytest
import respx
import httpx
from backend.opendota import OpenDotaClient

BASE = "https://api.opendota.com/api"

@pytest.fixture
def client():
    return OpenDotaClient(base_url=BASE)

@respx.mock
def test_find_league_by_name(client):
    respx.get(f"{BASE}/leagues").mock(return_value=httpx.Response(200, json=[
        {"leagueid": 15728, "name": "ESL Pro Circuit", "tier": "professional"},
        {"leagueid": 1234, "name": "Some Other League", "tier": "amateur"},
    ]))
    league = client.find_league("ESL Pro Circuit")
    assert league["leagueid"] == 15728

@respx.mock
def test_find_league_returns_none_when_not_found(client):
    respx.get(f"{BASE}/leagues").mock(return_value=httpx.Response(200, json=[]))
    assert client.find_league("Nonexistent") is None

@respx.mock
def test_fetch_league_matches(client):
    respx.get(f"{BASE}/leagues/15728/matches").mock(return_value=httpx.Response(200, json=[
        {"match_id": 111, "radiant_team_id": 1, "dire_team_id": 2,
         "radiant_team_name": "Tundra", "dire_team_name": "Spirit",
         "duration": 2500, "start_time": 1700000000, "radiant_win": True},
    ]))
    matches = client.fetch_league_matches(15728)
    assert len(matches) == 1
    assert matches[0]["match_id"] == 111

@respx.mock
def test_fetch_match_detail_extracts_kills_log(client):
    respx.get(f"{BASE}/matches/111").mock(return_value=httpx.Response(200, json={
        "match_id": 111, "duration": 2500, "start_time": 1700000000,
        "radiant_win": True,
        "kills_log": [{"time": 500, "key": "npc_dota_hero_invoker", "player_slot": 0}],
        "players": [
            {"account_id": 105248644, "player_slot": 0, "hero_id": 74,
             "kills": 12, "deaths": 2, "assists": 8, "gold_per_min": 742, "net_worth": 45000}
        ]
    }))
    detail = client.fetch_match_detail(111)
    assert detail["match_id"] == 111
    assert len(detail["kills_log"]) == 1
    assert detail["kills_log"][0]["time"] == 500
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_opendota.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.opendota'`

- [ ] **Step 3: Write backend/opendota.py**

```python
import httpx
import os

class OpenDotaClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.environ.get(
            "OPENDOTA_BASE_URL", "https://api.opendota.com/api"
        )

    def _get(self, path: str) -> dict | list:
        response = httpx.get(f"{self.base_url}{path}", timeout=30)
        response.raise_for_status()
        return response.json()

    def find_league(self, name: str) -> dict | None:
        leagues = self._get("/leagues")
        name_lower = name.lower()
        for league in leagues:
            if name_lower in league.get("name", "").lower():
                return league
        return None

    def fetch_league_matches(self, league_id: int) -> list[dict]:
        return self._get(f"/leagues/{league_id}/matches")

    def fetch_match_detail(self, match_id: int) -> dict:
        return self._get(f"/matches/{match_id}")

    def fetch_player_profile(self, account_id: int) -> dict:
        return self._get(f"/players/{account_id}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest tests/test_opendota.py -v
```
Expected: all 4 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/opendota.py tests/test_opendota.py
git commit -m "feat: OpenDota client with league and match fetching"
```

---

### Task 4: TwelveLabs Client Wrapper

**Files:**
- Create: `backend/twelvelabs_client.py`

This wraps the official `twelvelabs` SDK. No HTTP mocking needed — we mock the SDK object directly in tests.

- [ ] **Step 1: Write backend/twelvelabs_client.py**

```python
import json
import os
import time
from twelvelabs import TwelveLabs

ANALYZE_SCHEMA = {
    "type": "object",
    "properties": {
        "play_type": {
            "type": "string",
            "enum": ["RAMPAGE", "GODLIKE", "TEAMFIGHT", "OBJECTIVE", "CLUTCH"]
        },
        "excitement_score": {"type": "number", "minimum": 0, "maximum": 10},
        "description": {"type": "string"},
        "player_name": {"type": ["string", "null"]}
    },
    "required": ["play_type", "excitement_score", "description"]
}

class TwelveLabsClient:
    def __init__(self, api_key: str = None, index_id: str = None):
        key = api_key or os.environ["TWELVELABS_API_KEY"]
        self._client = TwelveLabs(api_key=key)
        self.index_id = index_id or os.environ.get("TWELVELABS_INDEX_ID", "")

    def get_or_create_index(self, name: str = "dota-intel") -> str:
        """Return existing index ID or create new one. Saves to self.index_id."""
        for index in self._client.indexes.list():
            if index.name == name:
                self.index_id = index.id
                return index.id
        index = self._client.indexes.create(
            index_name=name,
            models=[
                {"model_name": "marengo3.0", "model_options": ["visual", "audio"]},
                {"model_name": "pegasus1.2", "model_options": ["visual", "audio"]},
            ]
        )
        self.index_id = index.id
        return index.id

    def upload_video_url(self, url: str) -> str:
        """Upload a video by URL. Returns asset_id."""
        asset = self._client.assets.create(method="url", url=url)
        return asset.id

    def upload_video_file(self, path: str) -> str:
        """Upload a local video file. Returns asset_id."""
        with open(path, "rb") as f:
            asset = self._client.assets.create(method="direct", file=f)
        return asset.id

    def index_asset(self, asset_id: str) -> str:
        """Index an uploaded asset. Returns the indexed asset ID."""
        result = self._client.indexes.indexed_assets.create(
            index_id=self.index_id,
            asset_id=asset_id,
        )
        return result.id

    def wait_for_indexing(self, asset_id: str, timeout: int = 600) -> None:
        """Poll until the indexed asset is ready. Raises TimeoutError if exceeded."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            asset = self._client.indexes.indexed_assets.retrieve(
                index_id=self.index_id, id=asset_id
            )
            if asset.status == "ready":
                return
            if asset.status == "failed":
                raise RuntimeError(f"Indexing failed for asset {asset_id}")
            time.sleep(15)
        raise TimeoutError(f"Indexing did not complete within {timeout}s")

    def search_highlights(
        self,
        query: str,
        options: list[str] = None,
        page_limit: int = 10,
    ) -> list[dict]:
        """Search index for clips matching query. Returns list of clip dicts."""
        opts = options or ["visual", "audio", "transcription"]
        results = self._client.search.query(
            index_id=self.index_id,
            search_options=opts,
            query_text=query,
            group_by="clip",
            page_limit=page_limit,
        )
        clips = []
        for item in results:
            clips.append({
                "video_id": item.video_id,
                "start": item.start,
                "end": item.end,
                "score": getattr(item, "score", None),
                "thumbnail_url": getattr(item, "thumbnail_url", None),
            })
        return clips

    def calibrate_game_start(self, video_id: str) -> float:
        """
        Find the game horn sound to establish the offset between VOD start
        and actual game start. Returns seconds into the VOD.
        """
        results = self._client.search.query(
            index_id=self.index_id,
            search_options=["audio"],
            query_text="Dota 2 game countdown horn creep spawn sound",
            group_by="clip",
            page_limit=5,
        )
        for item in results:
            if item.video_id == video_id:
                return item.start
        # Fallback: assume 10-minute draft phase if horn not found
        return 600.0

    def analyze_clip(self, video_id: str, start: float, end: float) -> dict:
        """
        Ask Pegasus to classify and score a clip at [start, end] seconds.
        Returns parsed JSON matching ANALYZE_SCHEMA.
        """
        prompt = (
            f"Analyze the moment from {start:.0f} to {end:.0f} seconds in this "
            f"Dota 2 broadcast. Return JSON with: play_type (one of RAMPAGE, GODLIKE, "
            f"TEAMFIGHT, OBJECTIVE, CLUTCH), excitement_score (0-10 based on caster "
            f"voice intensity), description (one sentence), player_name (from caster "
            f"audio, or null)."
        )
        response = self._client.analyze(
            video_id=video_id,
            prompt=prompt,
            response_format={
                "type": "json_schema",
                "json_schema": ANALYZE_SCHEMA,
            },
        )
        return json.loads(response.data)
```

- [ ] **Step 2: Commit**

```bash
git add backend/twelvelabs_client.py
git commit -m "feat: TwelveLabs client wrapper (index, upload, search, analyze)"
```

---

### Task 5: Scoring Engine

**Files:**
- Create: `backend/scoring.py`
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Write failing tests**

`tests/test_scoring.py`:
```python
from backend.scoring import aggregate_player_stats, compute_ai_impact, rank_players
from backend.models import MatchPlayer, MatchDetail, KillEvent, Highlight, PlayerStats

def _make_match(match_id: int, account_id: int, kills: int, deaths: int,
                assists: int, gpm: int, won: bool) -> MatchDetail:
    slot = 0  # radiant
    player = MatchPlayer(
        account_id=account_id, player_slot=slot, hero_id=74,
        kills=kills, deaths=deaths, assists=assists,
        gold_per_min=gpm, net_worth=gpm * 35
    )
    return MatchDetail(
        match_id=match_id, duration=2500, start_time=1700000000,
        radiant_win=won, kills_log=[], players=[player]
    )

def test_aggregate_collects_kills_and_gpm():
    matches = [
        _make_match(1, 12345, kills=10, deaths=2, assists=5, gpm=700, won=True),
        _make_match(2, 12345, kills=8, deaths=3, assists=9, gpm=650, won=False),
    ]
    stats = aggregate_player_stats(matches, account_id=12345, name="TestPlayer", team="Team A")
    assert stats.matches == 2
    assert stats.wins == 1
    assert stats.total_kills == 18
    assert stats.total_deaths == 5
    assert stats.avg_gpm == 675.0

def test_compute_ai_impact_returns_0_to_100():
    stats = PlayerStats(
        account_id=1, name="X", team="Y",
        matches=5, wins=3, total_kills=40, total_deaths=10,
        total_assists=30, avg_gpm=700.0, hero_ids=[74]
    )
    highlights = [
        Highlight(video_id="v1", start=100, end=130, play_type="RAMPAGE",
                  excitement_score=9.5, description="Five man wipe"),
        Highlight(video_id="v1", start=200, end=230, play_type="TEAMFIGHT",
                  excitement_score=7.2, description="Clutch teamfight"),
    ]
    score = compute_ai_impact(stats, highlights)
    assert 0 <= score <= 100

def test_high_excitement_increases_score():
    stats = PlayerStats(
        account_id=1, name="X", team="Y",
        matches=5, wins=3, total_kills=40, total_deaths=10,
        total_assists=30, avg_gpm=700.0, hero_ids=[74]
    )
    low_excitement = [
        Highlight(video_id="v1", start=100, end=130, play_type="TEAMFIGHT",
                  excitement_score=2.0, description="Quiet play"),
    ]
    high_excitement = [
        Highlight(video_id="v1", start=100, end=130, play_type="RAMPAGE",
                  excitement_score=9.8, description="Explosive play"),
    ]
    low_score = compute_ai_impact(stats, low_excitement)
    high_score = compute_ai_impact(stats, high_excitement)
    assert high_score > low_score

def test_rank_players_orders_by_ai_impact_descending():
    from backend.models import RankedPlayer
    players = [
        {"account_id": 1, "name": "A", "team": "T1", "stats": PlayerStats(
            account_id=1, name="A", team="T1", matches=5, wins=4,
            total_kills=50, total_deaths=8, total_assists=20, avg_gpm=750, hero_ids=[74]
        ), "highlights": []},
        {"account_id": 2, "name": "B", "team": "T2", "stats": PlayerStats(
            account_id=2, name="B", team="T2", matches=5, wins=2,
            total_kills=20, total_deaths=15, total_assists=10, avg_gpm=500, hero_ids=[1]
        ), "highlights": []},
    ]
    ranked = rank_players(players)
    assert ranked[0].account_id == 1   # higher stats → rank 1
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_scoring.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.scoring'`

- [ ] **Step 3: Write backend/scoring.py**

```python
from statistics import mean
from backend.models import MatchDetail, PlayerStats, Highlight, RankedPlayer

def aggregate_player_stats(
    matches: list[MatchDetail],
    account_id: int,
    name: str,
    team: str,
) -> PlayerStats:
    wins = total_kills = total_deaths = total_assists = total_gpm = 0
    hero_ids: list[int] = []

    for match in matches:
        player = next(
            (p for p in match.players if p.account_id == account_id), None
        )
        if player is None:
            continue
        is_radiant = player.player_slot < 128
        if (is_radiant and match.radiant_win) or (not is_radiant and not match.radiant_win):
            wins += 1
        total_kills += player.kills
        total_deaths += player.deaths
        total_assists += player.assists
        total_gpm += player.gold_per_min
        hero_ids.append(player.hero_id)

    n = len(matches)
    return PlayerStats(
        account_id=account_id,
        name=name,
        team=team,
        matches=n,
        wins=wins,
        total_kills=total_kills,
        total_deaths=total_deaths,
        total_assists=total_assists,
        avg_gpm=round(total_gpm / n, 1) if n > 0 else 0.0,
        hero_ids=hero_ids,
    )

def compute_ai_impact(stats: PlayerStats, highlights: list[Highlight]) -> float:
    """
    Composite score 0-100. Weights:
      25% KDA ratio (kills+assists / max(deaths,1))
      20% GPM normalized to 800 ceiling
      20% win rate
      15% highlight density (highlights per match)
      20% average caster excitement score
    """
    kda = (stats.total_kills + stats.total_assists) / max(stats.total_deaths, 1)
    kda_norm = min(kda / 10.0, 1.0)            # cap at 10 KDA = 1.0

    gpm_norm = min(stats.avg_gpm / 800.0, 1.0) # cap at 800 GPM = 1.0

    win_rate = stats.wins / max(stats.matches, 1)

    density = min(len(highlights) / max(stats.matches, 1), 3.0) / 3.0  # cap 3 per match

    avg_exc = mean(h.excitement_score for h in highlights) / 10.0 if highlights else 0.0

    raw = (
        kda_norm     * 0.25 +
        gpm_norm     * 0.20 +
        win_rate     * 0.20 +
        density      * 0.15 +
        avg_exc      * 0.20
    )
    return round(raw * 100, 1)

def rank_players(player_data: list[dict]) -> list[RankedPlayer]:
    """
    player_data: list of dicts with keys:
      account_id, name, team, stats (PlayerStats), highlights (list[Highlight])
    Returns list sorted by ai_impact_score descending, with rank assigned.
    """
    scored = []
    for pd in player_data:
        stats: PlayerStats = pd["stats"]
        highlights: list[Highlight] = pd["highlights"]
        score = compute_ai_impact(stats, highlights)

        deaths = max(stats.total_deaths, 1)
        kda_ratio = (stats.total_kills + stats.total_assists) / deaths
        win_rate = stats.wins / max(stats.matches, 1)
        avg_k = stats.total_kills // max(stats.matches, 1)
        avg_d = stats.total_deaths // max(stats.matches, 1)
        avg_a = stats.total_assists // max(stats.matches, 1)

        scored.append(RankedPlayer(
            rank=0,  # assigned below
            account_id=stats.account_id,
            name=stats.name,
            team=stats.team,
            kda=f"{avg_k} / {avg_d} / {avg_a}",
            avg_kda_ratio=round(kda_ratio, 2),
            avg_gpm=stats.avg_gpm,
            win_rate=round(win_rate, 3),
            ai_impact_score=score,
            highlight_count=len(highlights),
            top_heroes=list(dict.fromkeys(stats.hero_ids))[:3],
        ))

    scored.sort(key=lambda p: p.ai_impact_score, reverse=True)
    for i, p in enumerate(scored):
        p.rank = i + 1
    return scored
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest tests/test_scoring.py -v
```
Expected: all 4 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/scoring.py tests/test_scoring.py
git commit -m "feat: AI Impact Score formula and player ranking"
```

---

### Task 6: Highlight Discovery

**Files:**
- Create: `backend/highlights.py`
- Create: `tests/test_highlights.py`

- [ ] **Step 1: Write failing tests**

`tests/test_highlights.py`:
```python
from unittest.mock import MagicMock, patch
from backend.highlights import (
    discover_event_anchored,
    discover_discovery_first,
    merge_and_deduplicate,
)
from backend.models import KillEvent, Highlight

def _mock_tl_client(search_results=None, analyze_result=None):
    client = MagicMock()
    client.search_highlights.return_value = search_results or []
    client.analyze_clip.return_value = analyze_result or {
        "play_type": "TEAMFIGHT",
        "excitement_score": 7.5,
        "description": "Three man kill in the river",
        "player_name": "Miracle-",
    }
    client.calibrate_game_start.return_value = 600.0
    return client

def test_event_anchored_returns_highlights_for_each_kill():
    kills = [KillEvent(time=2000, killer_id=12345, victim_id=99999)]
    tl = _mock_tl_client()
    results = discover_event_anchored(
        kills_log=kills,
        video_id="vid1",
        game_start_offset=600.0,
        player_account_id=12345,
        tl_client=tl,
        match_id=111,
        opponent="Team Spirit",
    )
    assert len(results) == 1
    assert results[0].play_type == "TEAMFIGHT"
    assert results[0].excitement_score == 7.5
    assert results[0].match_id == 111

def test_event_anchored_ignores_kills_where_player_is_not_killer():
    kills = [KillEvent(time=2000, killer_id=99999, victim_id=12345)]  # player died
    tl = _mock_tl_client()
    results = discover_event_anchored(
        kills_log=kills, video_id="vid1", game_start_offset=600.0,
        player_account_id=12345, tl_client=tl, match_id=111, opponent="X"
    )
    assert len(results) == 0

def test_merge_deduplicates_overlapping_clips():
    h1 = Highlight(video_id="v1", start=100, end=130, play_type="RAMPAGE",
                   excitement_score=9.0, description="A")
    h2 = Highlight(video_id="v1", start=115, end=145, play_type="RAMPAGE",
                   excitement_score=8.5, description="B")  # overlaps h1
    h3 = Highlight(video_id="v1", start=500, end=530, play_type="TEAMFIGHT",
                   excitement_score=7.0, description="C")
    merged = merge_and_deduplicate([h1, h2, h3], overlap_threshold=10.0)
    assert len(merged) == 2   # h1+h2 collapsed, h3 kept
    assert merged[0].excitement_score == 9.0  # keep higher score
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_highlights.py -v
```
Expected: `ModuleNotFoundError: No module named 'backend.highlights'`

- [ ] **Step 3: Write backend/highlights.py**

```python
from backend.models import KillEvent, Highlight

CLIP_PADDING_SECONDS = 20  # seconds before/after event to include in clip

def discover_event_anchored(
    kills_log: list[KillEvent],
    video_id: str,
    game_start_offset: float,
    player_account_id: int,
    tl_client,
    match_id: int,
    opponent: str,
) -> list[Highlight]:
    """
    For each kill where this player is the killer, ask Pegasus to classify
    the ±CLIP_PADDING_SECONDS window around the event.
    """
    highlights = []
    for kill in kills_log:
        if kill.killer_id != player_account_id:
            continue
        vod_time = game_start_offset + kill.time
        start = max(0, vod_time - CLIP_PADDING_SECONDS)
        end = vod_time + CLIP_PADDING_SECONDS

        analysis = tl_client.analyze_clip(video_id, start, end)
        highlights.append(Highlight(
            video_id=video_id,
            start=start,
            end=end,
            play_type=analysis.get("play_type", "TEAMFIGHT"),
            excitement_score=float(analysis.get("excitement_score", 5.0)),
            description=analysis.get("description", ""),
            player_name=analysis.get("player_name"),
            match_id=match_id,
            opponent=opponent,
        ))
    return highlights

def discover_discovery_first(
    index_id: str,
    video_id: str,
    player_name: str,
    tl_client,
    match_id: int = None,
    opponent: str = None,
) -> list[Highlight]:
    """
    Search the VOD for high-excitement moments mentioning the player,
    then enrich each with Pegasus classification.
    """
    query = (
        f"Dota 2 caster excited announcer {player_name} "
        f"kill streak rampage godlike crowd cheering"
    )
    clips = tl_client.search_highlights(
        query=query,
        options=["visual", "audio", "transcription"],
        page_limit=8,
    )
    highlights = []
    for clip in clips:
        if clip["video_id"] != video_id:
            continue
        analysis = tl_client.analyze_clip(clip["video_id"], clip["start"], clip["end"])
        highlights.append(Highlight(
            video_id=clip["video_id"],
            start=clip["start"],
            end=clip["end"],
            play_type=analysis.get("play_type", "TEAMFIGHT"),
            excitement_score=float(analysis.get("excitement_score", 5.0)),
            description=analysis.get("description", ""),
            player_name=analysis.get("player_name"),
            thumbnail_url=clip.get("thumbnail_url"),
            match_id=match_id,
            opponent=opponent,
        ))
    return highlights

def merge_and_deduplicate(
    highlights: list[Highlight],
    overlap_threshold: float = 10.0,
) -> list[Highlight]:
    """
    Collapse clips whose time ranges overlap within overlap_threshold seconds.
    When collapsing, keep the clip with the higher excitement_score.
    Sort final list by excitement_score descending.
    """
    if not highlights:
        return []

    sorted_h = sorted(highlights, key=lambda h: h.start)
    merged: list[Highlight] = [sorted_h[0]]

    for current in sorted_h[1:]:
        last = merged[-1]
        if (current.video_id == last.video_id and
                current.start < last.end + overlap_threshold):
            # Overlapping — keep whichever has higher excitement
            if current.excitement_score > last.excitement_score:
                merged[-1] = current
        else:
            merged.append(current)

    merged.sort(key=lambda h: h.excitement_score, reverse=True)
    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest tests/test_highlights.py -v
```
Expected: all 3 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/highlights.py tests/test_highlights.py
git commit -m "feat: highlight discovery (event-anchored + discovery-first) with deduplication"
```

---

### Task 7: Stream-to-Match Segment Correlation + Ingestion

The streams on Twitch and YouTube are 10–12 hour broadcasts that include pre-show, multiple matches, player interviews, and recaps. Indexing a full stream would consume the entire TwelveLabs free-tier budget (10 hrs) in one shot and take ~5 hours to process. Instead we extract only the ~110-minute window around each match before uploading.

**How it works:**
- `yt-dlp --dump-json <stream_url>` returns a metadata JSON that includes `timestamp` (Unix epoch when the broadcast started) and `duration` (total stream length in seconds) — no download required
- **Verified via Twitch API Research**: For Twitch VODs, the `created_at` field (ISO 8601) matches this zero-point. See [research findings](file:///Users/cacho/Documents/repos/twelve-labs-hackathon/dota-intel/research/twitch_api.md).
- OpenDota's `match.start_time` is also a Unix timestamp
- The difference `match.start_time − stream.timestamp` gives the offset of the game within the stream
- We subtract a 10-minute buffer to capture the draft phase, giving a total segment of ~110 minutes
- `yt-dlp --download-sections "*HH:MM:SS-HH:MM:SS"` downloads only that window

**Files:**
- Create: `scripts/find_match_segments.py`
- Create: `backend/ingestion.py`

No unit tests — both files are pure subprocess/filesystem I/O. Manual verification steps are included.

- [ ] **Step 1: Write scripts/find_match_segments.py**

```python
#!/usr/bin/env python3
"""
Scans a list of stream URLs to find which time window contains each OpenDota match.

Usage:
  python scripts/find_match_segments.py \
    --league "ESL One" \
    --streams https://www.twitch.tv/videos/2345678901 \
              https://www.twitch.tv/videos/2345678902 \
              https://www.youtube.com/watch?v=XXXXXXXXXXX

Output:
  data/match_segments.json  —  {match_id: {stream_url, offset_seconds, ...}}

Run this once per event. Then run seed_index.py to download segments and index them.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.opendota import OpenDotaClient

BUFFER_BEFORE_SECONDS  = 600   # 10 min before match start (covers draft phase)
SEGMENT_DURATION_SECONDS = 6600  # 110 min total (draft + ~45-min match + 20-min buffer)

def format_hhmmss(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_stream_metadata(stream_url: str) -> dict:
    """
    Fetch metadata for a stream URL without downloading any video.
    Returns dict containing at minimum:
      timestamp  (int)  — Unix epoch when the broadcast began
      duration   (int)  — total stream length in seconds
      title      (str)  — broadcast title
    """
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-playlist", stream_url],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp metadata failed for {stream_url}:\n{result.stderr.strip()}"
        )
    return json.loads(result.stdout)

def find_matches_in_stream(
    stream_url: str,
    league_matches: list[dict],
    match_start_times: dict[int, int],
) -> list[dict]:
    """
    Compares each match's start_time against this stream's broadcast window.
    Returns a list of segment descriptors for every match found inside the stream.
    """
    meta = get_stream_metadata(stream_url)
    stream_start  = int(meta["timestamp"])
    stream_duration = int(meta.get("duration") or 0)
    stream_end    = stream_start + stream_duration

    print(f"  Title   : {meta.get('title', 'unknown')}")
    print(f"  Started : {stream_start}  (unix)")
    print(f"  Duration: {stream_duration // 3600}h {(stream_duration % 3600) // 60}m")

    found = []
    for lm in league_matches:
        mid = lm["match_id"]
        match_start = match_start_times.get(mid)
        if match_start is None:
            continue
        if not (stream_start <= match_start <= stream_end):
            continue  # this match is not inside this stream

        # Offset from stream start, minus the draft buffer
        offset = max(0, match_start - stream_start - BUFFER_BEFORE_SECONDS)
        seg_start = format_hhmmss(offset)
        seg_end   = format_hhmmss(offset + SEGMENT_DURATION_SECONDS)

        print(f"  ✓ Match {mid}: {seg_start} → {seg_end}  "
              f"({lm.get('radiant_team_name','?')} vs {lm.get('dire_team_name','?')})")

        found.append({
            "match_id":             mid,
            "stream_url":           stream_url,
            "stream_start_unix":    stream_start,
            "match_start_unix":     match_start,
            "offset_seconds":       offset,
            "duration_seconds":     SEGMENT_DURATION_SECONDS,
            "segment_start_hhmmss": seg_start,
            "segment_end_hhmmss":   seg_end,
            "radiant_team":         lm.get("radiant_team_name", "Unknown"),
            "dire_team":            lm.get("dire_team_name",    "Unknown"),
        })
    return found

def main():
    parser = argparse.ArgumentParser(
        description="Map OpenDota match IDs to their time windows inside broadcast streams"
    )
    parser.add_argument("--league",  required=True, help="League name to search on OpenDota")
    parser.add_argument("--streams", nargs="+", required=True, help="Stream URLs to scan")
    args = parser.parse_args()

    od = OpenDotaClient()

    print(f"[find] Looking up league: {args.league}")
    league = od.find_league(args.league)
    if not league:
        raise SystemExit(f"League '{args.league}' not found on OpenDota.")
    league_id = league["leagueid"]
    print(f"[find] Found: {league['name']} (id={league_id})")

    print(f"[find] Fetching match list...")
    league_matches = od.fetch_league_matches(league_id)
    print(f"[find] {len(league_matches)} matches in league")

    # Fetch start_time for each match (needed for offset calculation)
    print(f"[find] Fetching start_time for each match from OpenDota...")
    match_start_times: dict[int, int] = {}
    for lm in league_matches:
        mid = lm["match_id"]
        try:
            detail = od.fetch_match_detail(mid)
            match_start_times[mid] = detail["start_time"]
        except Exception as e:
            print(f"  Warning: could not fetch match {mid}: {e}")

    all_segments: dict[str, dict] = {}  # keyed by str(match_id)

    for stream_url in args.streams:
        print(f"\n[find] Scanning: {stream_url}")
        try:
            segs = find_matches_in_stream(stream_url, league_matches, match_start_times)
            for seg in segs:
                all_segments[str(seg["match_id"])] = seg
        except Exception as e:
            print(f"  Error: {e}")

    out = Path("data/match_segments.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(all_segments, indent=2))

    print(f"\n[find] Mapped {len(all_segments)}/{len(league_matches)} matches → {out}")
    if len(all_segments) < len(league_matches):
        unmapped = [
            str(lm["match_id"]) for lm in league_matches
            if str(lm["match_id"]) not in all_segments
        ]
        print(f"[find] Unmapped match IDs (add their stream URLs and re-run):")
        for mid in unmapped:
            print(f"  {mid}")
    print("[find] Next step: python scripts/seed_index.py")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write backend/ingestion.py**

```python
import json
import subprocess
from pathlib import Path

BUFFER_BEFORE_SECONDS    = 600
SEGMENT_DURATION_SECONDS = 6600

def format_hhmmss(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def download_match_segment(
    stream_url: str,
    offset_seconds: int,
    duration_seconds: int,
    output_path: str,
) -> Path:
    """
    Download a specific time window from a 10-12hr stream using yt-dlp.
    Uses --download-sections to avoid pulling the entire broadcast.
    output_path must end in .mp4.

    Example: a match starting 3h15m into a stream with a 10-min draft buffer
      offset_seconds  = 11700  (3h15m = 11700s, minus 600s buffer = 11100)
      duration_seconds = 6600  (110 min)
      → downloads 11100s–17700s only
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    start_ts = format_hhmmss(offset_seconds)
    end_ts   = format_hhmmss(offset_seconds + duration_seconds)

    result = subprocess.run(
        [
            "yt-dlp",
            "--download-sections", f"*{start_ts}-{end_ts}",
            "--format", "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "--merge-output-format", "mp4",
            "--output", str(path),
            stream_url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp segment download failed:\n{result.stderr.strip()}"
        )
    return path

def ingest_vod(vod_path: str, tl_client, match_id: int) -> dict:
    """
    Upload a local video segment to TwelveLabs and index it.
    Blocks until the index task completes (~30-40% of video duration).
    Returns {"asset_id": str, "indexed_asset_id": str, "match_id": int}.
    """
    print(f"[ingest] Uploading {vod_path} (match {match_id})...")
    asset_id = tl_client.upload_video_file(vod_path)
    print(f"[ingest] Uploaded → asset_id={asset_id}")

    indexed_id = tl_client.index_asset(asset_id)
    print(f"[ingest] Indexing started → indexed_id={indexed_id}. Waiting...")
    tl_client.wait_for_indexing(indexed_id)
    print(f"[ingest] Match {match_id} ready in TwelveLabs ✓")

    return {
        "asset_id":        asset_id,
        "indexed_asset_id": indexed_id,
        "match_id":        match_id,
    }

def load_match_segments(segments_path: str = "data/match_segments.json") -> dict:
    """
    Load the mapping produced by find_match_segments.py.
    Keys are str(match_id). Values contain stream_url, offset_seconds, duration_seconds.
    Raises FileNotFoundError with instructions if the file doesn't exist.
    """
    path = Path(segments_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{segments_path} not found.\n"
            f"Run: python scripts/find_match_segments.py --league '<name>' --streams <urls>"
        )
    return json.loads(path.read_text())
```

- [ ] **Step 3: Manually verify stream metadata fetch (no download)**

```bash
# Replace with any real Twitch VOD or YouTube URL
PYTHONPATH=. python -c "
from backend.ingestion import format_hhmmss
from scripts.find_match_segments import get_stream_metadata
meta = get_stream_metadata('https://www.twitch.tv/videos/YOUR_VOD_ID')
print('Title    :', meta.get('title'))
print('Start    :', meta.get('timestamp'), '(unix)')
print('Duration :', format_hhmmss(int(meta.get('duration', 0))))
"
```
Expected: title, a unix timestamp, and a duration string like `11:32:44`.

- [ ] **Step 4: Verify segment download with a known offset**

```bash
# Use the segment start/end from data/match_segments.json after running find_match_segments.py
PYTHONPATH=. python -c "
from backend.ingestion import download_match_segment
path = download_match_segment(
    stream_url='https://www.twitch.tv/videos/YOUR_VOD_ID',
    offset_seconds=11100,    # replace with real offset
    duration_seconds=300,    # download only 5 min to verify quickly
    output_path='/tmp/test_segment.mp4',
)
import os
size_mb = os.path.getsize(path) // 1024 // 1024
print(f'Downloaded {size_mb} MB → {path}')
"
```
Expected: file at `/tmp/test_segment.mp4`, size in the range of 50–300 MB for 5 minutes of 720p.

- [ ] **Step 5: Run find_match_segments.py end-to-end**

```bash
# Point at real ESL stream URLs from twitch.tv/esl_dota2/videos
python scripts/find_match_segments.py \
  --league "ESL One" \
  --streams \
    https://www.twitch.tv/videos/VOD_ID_1 \
    https://www.twitch.tv/videos/VOD_ID_2
```
Expected: `data/match_segments.json` created, matches printed with their time windows. Any unmapped matches are listed — add more stream URLs and re-run.

- [ ] **Step 6: Commit**

```bash
git add scripts/find_match_segments.py backend/ingestion.py
git commit -m "feat: stream-to-match segment correlation and targeted VOD download"
```

---

### Task 8: FastAPI Routes + Data Cache

**Files:**
- Create: `backend/cache.py`
- Modify: `backend/main.py`
- Test: extend `tests/test_health.py`

The seed script writes JSON to `data/`. The API reads from it. This keeps the demo snappy — no live API calls during the presentation.

- [ ] **Step 1: Write backend/cache.py**

```python
import json
import os
from pathlib import Path
from backend.models import LeaderboardResponse, PlayerDetail

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

def write_leaderboard(response: LeaderboardResponse) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "leaderboard.json").write_text(response.model_dump_json(indent=2))

def read_leaderboard() -> LeaderboardResponse | None:
    path = DATA_DIR / "leaderboard.json"
    if not path.exists():
        return None
    return LeaderboardResponse.model_validate_json(path.read_text())

def write_player(account_id: int, detail: PlayerDetail) -> None:
    (DATA_DIR / "players").mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "players" / f"{account_id}.json"
    path.write_text(detail.model_dump_json(indent=2))

def read_player(account_id: int) -> PlayerDetail | None:
    path = DATA_DIR / "players" / f"{account_id}.json"
    if not path.exists():
        return None
    return PlayerDetail.model_validate_json(path.read_text())
```

- [ ] **Step 2: Write failing route tests**

Add to `tests/test_health.py`:
```python
import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import LeaderboardResponse, RankedPlayer

client = TestClient(app)

# (existing test_health kept as-is)

def test_leaderboard_returns_404_when_no_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    response = client.get("/leaderboard")
    assert response.status_code == 404

def test_leaderboard_returns_data_when_seeded(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Write fixture data
    player = RankedPlayer(
        rank=1, account_id=105248644, name="Miracle-", team="Tundra Esports",
        kda="12 / 2 / 8", avg_kda_ratio=6.67, avg_gpm=742.0,
        win_rate=0.78, ai_impact_score=97.4, highlight_count=14, top_heroes=[74]
    )
    lb = LeaderboardResponse(
        competition="ESL Pro Circuit 2025", total_matches=247,
        total_teams=16, total_highlights=1842, avg_kda_top10=4.82,
        players=[player]
    )
    (tmp_path / "leaderboard.json").write_text(lb.model_dump_json())

    response = client.get("/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert data["players"][0]["name"] == "Miracle-"
    assert data["players"][0]["ai_impact_score"] == 97.4

def test_player_detail_returns_404_when_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    response = client.get("/player/999999")
    assert response.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_health.py -v
```
Expected: `404 test fails — /leaderboard route not defined yet`

- [ ] **Step 4: Add routes to backend/main.py**

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend import cache
from backend.models import LeaderboardResponse, PlayerDetail

app = FastAPI(title="Dota Intel")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard():
    data = cache.read_leaderboard()
    if data is None:
        raise HTTPException(status_code=404, detail="Leaderboard not yet seeded. Run seed_index.py first.")
    return data

@app.get("/player/{account_id}", response_model=PlayerDetail)
def get_player(account_id: int):
    data = cache.read_player(account_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Player {account_id} not found.")
    return data
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest tests/ -v
```
Expected: all tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/cache.py backend/main.py tests/test_health.py
git commit -m "feat: leaderboard and player detail API routes with file-based cache"
```

---

### Task 9: Pre-Demo Seed Script

**Files:**
- Create: `scripts/seed_index.py`

This is the most important script for the demo. Run it once the night before and leave it running — indexing takes time.

- [ ] **Step 1: Write scripts/seed_index.py**

```python
#!/usr/bin/env python3
"""
Pre-demo pipeline. Run once before the hackathon demo.

Usage:
  export TWELVELABS_API_KEY=your_key
  export ESL_LEAGUE_NAME="ESL One"  # adjust to match actual league name
  python scripts/seed_index.py

What it does:
  1. Find the ESL league on OpenDota
  2. Fetch all match IDs
  3. For each match: download Twitch VOD, upload + index in TwelveLabs
  4. For each player: discover highlights, compute AI Impact Score
  5. Write data/leaderboard.json and data/players/{id}.json
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.opendota import OpenDotaClient
from backend.twelvelabs_client import TwelveLabsClient
from backend.ingestion import download_match_segment, ingest_vod, load_match_segments
from backend.highlights import discover_event_anchored, discover_discovery_first, merge_and_deduplicate
from backend.scoring import aggregate_player_stats, rank_players
from backend.models import (
    MatchDetail, KillEvent, MatchPlayer, MatchSummary,
    PlayerDetail, LeaderboardResponse, Highlight
)
from backend import cache

# ── CONFIG ────────────────────────────────────────────────────────────────────
LEAGUE_NAME = os.environ.get("ESL_LEAGUE_NAME", "ESL Pro Circuit")

# Pro player account IDs to track. Get from liquipedia or opendota.com player pages.
PLAYER_ROSTER: dict[int, dict] = {
    # account_id: {"name": "Miracle-", "team": "Tundra Esports"}
    105248644: {"name": "Miracle-",   "team": "Tundra Esports"},
    321580662: {"name": "Yatoro",     "team": "Team Spirit"},
    # Add more players here
}

SEGMENT_CACHE_DIR = Path("data/segments")  # downloaded .mp4 segments cached here
# ──────────────────────────────────────────────────────────────────────────────

def seconds_to_mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"

def main():
    od = OpenDotaClient()
    tl = TwelveLabsClient()

    # 1. Find league
    print(f"[seed] Looking up league: {LEAGUE_NAME}")
    league = od.find_league(LEAGUE_NAME)
    if not league:
        raise SystemExit(f"League '{LEAGUE_NAME}' not found on OpenDota. Check ESL_LEAGUE_NAME env var.")
    league_id = league["leagueid"]
    print(f"[seed] Found league {league_id}: {league['name']}")

    # 2. Create / find TwelveLabs index
    index_id = tl.get_or_create_index("dota-intel")
    print(f"[seed] TwelveLabs index: {index_id}")
    print(f"[seed] Set TWELVELABS_INDEX_ID={index_id} in your .env for the API server")

    # 3. Load match → stream segment mapping (produced by find_match_segments.py)
    match_segments = load_match_segments()  # raises FileNotFoundError with instructions if missing
    print(f"[seed] Loaded segment map: {len(match_segments)} matches")

    # 4. Fetch all match IDs from OpenDota
    league_matches = od.fetch_league_matches(league_id)
    print(f"[seed] Found {len(league_matches)} matches in league")

    # 5. Download segments + ingest into TwelveLabs
    match_details: dict[int, MatchDetail] = {}
    video_map: dict[int, str] = {}  # match_id → TwelveLabs indexed_asset_id

    for lm in league_matches:
        mid = lm["match_id"]
        seg = match_segments.get(str(mid))
        if seg is None:
            print(f"[seed] Skipping match {mid} — not in match_segments.json")
            continue

        # Download the segment (~110 min window) if not already cached
        seg_path = SEGMENT_CACHE_DIR / f"match_{mid}.mp4"
        if not seg_path.exists():
            print(f"[seed] Downloading segment for match {mid} "
                  f"({seg['segment_start_hhmmss']} → {seg['segment_end_hhmmss']}) ...")
            download_match_segment(
                stream_url=seg["stream_url"],
                offset_seconds=seg["offset_seconds"],
                duration_seconds=seg["duration_seconds"],
                output_path=str(seg_path),
            )
        else:
            print(f"[seed] Using cached segment: {seg_path}")

        # Upload + index
        record = ingest_vod(str(vod_path), tl, mid)
        video_map[mid] = record["indexed_asset_id"]

        # Fetch match detail from OpenDota
        raw = od.fetch_match_detail(mid)
        kills_log = [
            KillEvent(
                time=k["time"],
                killer_id=k.get("player_slot", 0),   # OpenDota uses player_slot in kills_log
                victim_id=0,
            )
            for k in raw.get("kills_log", [])
        ]
        players = [
            MatchPlayer(
                account_id=p.get("account_id"),
                player_slot=p["player_slot"],
                hero_id=p["hero_id"],
                kills=p["kills"],
                deaths=p["deaths"],
                assists=p["assists"],
                gold_per_min=p["gold_per_min"],
                net_worth=p.get("net_worth", 0),
            )
            for p in raw.get("players", [])
        ]
        # Resolve killer account_ids from player_slot in kills_log
        slot_to_account = {p.player_slot: p.account_id for p in players}
        for k in kills_log:
            k.killer_id = slot_to_account.get(k.killer_id, 0) or 0

        match_details[mid] = MatchDetail(
            match_id=mid,
            duration=raw["duration"],
            start_time=raw["start_time"],
            radiant_win=raw["radiant_win"],
            kills_log=kills_log,
            players=players,
        )

    # 5. Discover highlights and compute scores per player
    all_player_data = []

    for account_id, info in PLAYER_ROSTER.items():
        print(f"\n[seed] Processing player: {info['name']} ({account_id})")

        # Get all matches where this player participated
        player_matches = [
            md for md in match_details.values()
            if any(p.account_id == account_id for p in md.players)
        ]

        if not player_matches:
            print(f"[seed] No matches found for {info['name']} — skipping")
            continue

        stats = aggregate_player_stats(player_matches, account_id, info["name"], info["team"])

        # Discover highlights across all their match VODs
        all_highlights: list[Highlight] = []
        match_summaries: list[MatchSummary] = []

        for md in sorted(player_matches, key=lambda m: m.start_time, reverse=True):
            mid = md.match_id
            video_id = video_map.get(mid)

            # Find opponent name
            player = next(p for p in md.players if p.account_id == account_id)
            is_radiant = player.player_slot < 128
            opponent = "Unknown"
            for lm in league_matches:
                if lm["match_id"] == mid:
                    opponent = lm["dire_team_name"] if is_radiant else lm["radiant_team_name"]
                    break
            won = (is_radiant and md.radiant_win) or (not is_radiant and not md.radiant_win)

            match_highlights: list[Highlight] = []
            if video_id:
                offset = tl.calibrate_game_start(video_id)
                event_clips = discover_event_anchored(
                    md.kills_log, video_id, offset, account_id, tl, mid, opponent
                )
                discovery_clips = discover_discovery_first(
                    index_id, video_id, info["name"], tl, mid, opponent
                )
                match_highlights = merge_and_deduplicate(event_clips + discovery_clips)

            all_highlights.extend(match_highlights)

            match_summaries.append(MatchSummary(
                match_id=mid,
                opponent=opponent,
                won=won,
                duration_str=seconds_to_mmss(md.duration),
                kills=player.kills,
                deaths=player.deaths,
                assists=player.assists,
                gpm=player.gold_per_min,
                hero_id=player.hero_id,
                clip_count=len(match_highlights),
            ))

        all_highlights = merge_and_deduplicate(all_highlights)[:14]  # cap per player

        # Build RankedPlayer (rank filled in by rank_players later)
        all_player_data.append({
            "account_id": account_id,
            "name": info["name"],
            "team": info["team"],
            "stats": stats,
            "highlights": all_highlights,
            "match_summaries": match_summaries,
        })

    # 6. Rank and write leaderboard
    ranked = rank_players(all_player_data)
    lb = LeaderboardResponse(
        competition=LEAGUE_NAME,
        total_matches=len(match_details),
        total_teams=len({lm.get("radiant_team_id") for lm in league_matches}
                       | {lm.get("dire_team_id") for lm in league_matches}),
        total_highlights=sum(len(pd["highlights"]) for pd in all_player_data),
        avg_kda_top10=round(
            sum(p.avg_kda_ratio for p in ranked[:10]) / min(len(ranked), 10), 2
        ) if ranked else 0.0,
        players=ranked,
    )
    cache.write_leaderboard(lb)
    print(f"\n[seed] Wrote leaderboard with {len(ranked)} players")

    # 7. Write per-player detail files
    ranked_by_id = {p.account_id: p for p in ranked}
    for pd in all_player_data:
        aid = pd["account_id"]
        detail = PlayerDetail(
            player=ranked_by_id[aid],
            recent_matches=pd["match_summaries"][:8],
            highlights=pd["highlights"],
        )
        cache.write_player(aid, detail)
        print(f"[seed] Wrote player data: {pd['name']} ({aid})")

    print("\n[seed] Done! Start the API with: uvicorn backend.main:app --reload")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/seed_index.py
git commit -m "feat: pre-demo seed script (fetch → ingest → highlight → score → write)"
```

---

### Task 10: Frontend Setup

**Files:**
- Create: `frontend/` (Vite project)
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Create: `frontend/tailwind.config.js`

- [ ] **Step 1: Scaffold Vite + React + TypeScript project**

```bash
cd dota-intel/frontend
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install react-router-dom
```

- [ ] **Step 2: Write frontend/tailwind.config.js**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:      "#0C0C0F",
        surface: "#13131A",
        surface2:"#1A1A26",
        border:  "#252535",
        primary: "#E8E8F0",
        muted:   "#6B6B88",
        dim:     "#555568",
        orange:  "#FF6B00",
        purple:  "#A78BFA",
        green:   "#22C55E",
        gold:    "#FFB800",
        silver:  "#A0A8C0",
        bronze:  "#CD8050",
        red:     "#FF4444",
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 3: Update frontend/src/index.css**

```css
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  background-color: #0C0C0F;
  color: #E8E8F0;
  font-family: 'JetBrains Mono', monospace;
}
```

- [ ] **Step 4: Write frontend/src/types.ts**

```typescript
export interface RankedPlayer {
  rank: number;
  account_id: number;
  name: string;
  team: string;
  kda: string;
  avg_kda_ratio: number;
  avg_gpm: number;
  win_rate: number;
  ai_impact_score: number;
  highlight_count: number;
  top_heroes: number[];
}

export interface LeaderboardResponse {
  competition: string;
  total_matches: number;
  total_teams: number;
  total_highlights: number;
  avg_kda_top10: number;
  players: RankedPlayer[];
}

export interface Highlight {
  video_id: string;
  start: number;
  end: number;
  play_type: string;
  excitement_score: number;
  description: string;
  player_name: string | null;
  match_id: number | null;
  opponent: string | null;
  thumbnail_url: string | null;
}

export interface MatchSummary {
  match_id: number;
  opponent: string;
  won: boolean;
  duration_str: string;
  kills: number;
  deaths: number;
  assists: number;
  gpm: number;
  hero_id: number;
  clip_count: number;
}

export interface PlayerDetail {
  player: RankedPlayer;
  recent_matches: MatchSummary[];
  highlights: Highlight[];
}
```

- [ ] **Step 5: Write frontend/src/api.ts**

```typescript
const BASE = "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  leaderboard: () => get<import("./types").LeaderboardResponse>("/leaderboard"),
  player: (accountId: number) => get<import("./types").PlayerDetail>(`/player/${accountId}`),
};
```

- [ ] **Step 6: Write frontend/src/App.tsx**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Leaderboard } from "./pages/Leaderboard";
import { PlayerDetail } from "./pages/PlayerDetail";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Leaderboard />} />
        <Route path="/player/:accountId" element={<PlayerDetail />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 7: Run dev server to verify setup**

```bash
cd frontend && npm run dev
```
Expected: Vite server at `http://localhost:5173`, blank dark page, no errors in console.

- [ ] **Step 8: Commit**

```bash
cd .. && git add frontend/
git commit -m "feat: React + Tailwind frontend scaffold with types and api client"
```

---

### Task 11: Leaderboard Screen

**Files:**
- Create: `frontend/src/components/NavBar.tsx`
- Create: `frontend/src/components/StatCard.tsx`
- Create: `frontend/src/components/PlayerRow.tsx`
- Create: `frontend/src/pages/Leaderboard.tsx`

- [ ] **Step 1: Write NavBar.tsx**

```tsx
interface NavBarProps {
  competition: string;
  backLabel?: string;
  onBack?: () => void;
}

export function NavBar({ competition, backLabel, onBack }: NavBarProps) {
  return (
    <nav className="flex items-center justify-between px-10 h-16 bg-surface2 border-b border-border">
      <div className="flex items-center gap-4">
        <div className="w-7 h-7 rounded-lg bg-orange" />
        <span className="text-sm font-bold tracking-widest text-primary">DOTA INTEL</span>
        <div className="w-px h-5 bg-dim" />
        <span className="text-sm text-muted">{competition}</span>
      </div>
      {onBack && (
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 h-9 rounded-lg bg-surface border border-border text-muted text-sm hover:text-primary transition-colors"
        >
          ← {backLabel}
        </button>
      )}
    </nav>
  );
}
```

- [ ] **Step 2: Write StatCard.tsx**

```tsx
interface StatCardProps {
  label: string;
  value: string;
  accent?: "orange" | "blue" | "purple" | "gold";
}

const accentColors = {
  orange: "text-orange",
  blue:   "text-blue-400",
  purple: "text-purple",
  gold:   "text-gold",
};

export function StatCard({ label, value, accent = "orange" }: StatCardProps) {
  return (
    <div className="flex-1 bg-surface border border-border rounded-xl p-5 flex flex-col gap-2">
      <span className={`text-xs font-semibold ${accentColors[accent]}`}>{label}</span>
      <span className="text-2xl font-bold text-primary">{value}</span>
    </div>
  );
}
```

- [ ] **Step 3: Write PlayerRow.tsx**

```tsx
import { useNavigate } from "react-router-dom";
import type { RankedPlayer } from "../types";

const rankColor = (rank: number) =>
  rank === 1 ? "text-gold" : rank === 2 ? "text-silver" : rank === 3 ? "text-bronze" : "text-dim";

interface Props { player: RankedPlayer; }

export function PlayerRow({ player }: Props) {
  const nav = useNavigate();
  return (
    <div
      className="flex items-center h-14 px-5 border-b border-[#1D1D28] hover:bg-surface2 cursor-pointer transition-colors"
      onClick={() => nav(`/player/${player.account_id}`)}
    >
      {/* Rank */}
      <div className="w-12 flex justify-center">
        <span className={`text-sm font-bold ${rankColor(player.rank)}`}>{player.rank}</span>
      </div>

      {/* Player */}
      <div className="flex-1 flex flex-col gap-0.5 px-3">
        <span className="text-sm font-semibold text-primary">{player.name}</span>
        <span className="text-xs text-dim">{player.team}</span>
      </div>

      {/* K/D/A */}
      <div className="w-28 text-center text-xs text-primary">{player.kda}</div>

      {/* GPM */}
      <div className="w-20 text-center text-xs text-green font-semibold">
        {player.avg_gpm.toFixed(0)}
      </div>

      {/* Win % */}
      <div className="w-20 text-center text-xs text-primary">
        {(player.win_rate * 100).toFixed(0)}%
      </div>

      {/* AI Impact */}
      <div className="w-32 flex justify-center bg-[#1A0A33]">
        <span className="text-sm font-bold text-purple">{player.ai_impact_score.toFixed(1)}</span>
      </div>

      {/* Highlights button */}
      <div className="w-36 flex justify-center">
        <span className="px-3 py-1 rounded text-xs font-semibold text-purple bg-[#160D28] border border-[#3D2475]">
          ▶ {player.highlight_count} clips
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write Leaderboard.tsx**

```tsx
import { useEffect, useState } from "react";
import { NavBar } from "../components/NavBar";
import { StatCard } from "../components/StatCard";
import { PlayerRow } from "../components/PlayerRow";
import { api } from "../api";
import type { LeaderboardResponse } from "../types";

export function Leaderboard() {
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.leaderboard()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return (
    <div className="min-h-screen bg-bg flex items-center justify-center text-muted">
      {error} — run seed_index.py first
    </div>
  );
  if (!data) return (
    <div className="min-h-screen bg-bg flex items-center justify-center text-muted">
      Loading…
    </div>
  );

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <NavBar competition={data.competition} />

      <div className="flex-1 px-10 py-7 flex flex-col gap-5">
        {/* Page header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary">Competition Leaderboard</h1>
            <p className="text-xs text-muted mt-1">
              Player rankings across all matches · OpenDota stats × TwelveLabs AI
            </p>
          </div>
          <div className="flex gap-2">
            <button className="px-4 h-9 rounded-lg text-xs bg-surface border border-border text-muted">All Teams</button>
            <button className="px-4 h-9 rounded-lg text-xs bg-surface border border-border text-muted">All Heroes</button>
            <button className="px-4 h-9 rounded-lg text-xs bg-[#200D44] border border-purple text-purple font-semibold">▼ AI Impact</button>
          </div>
        </div>

        {/* Stat cards */}
        <div className="flex gap-4">
          <StatCard label="Total Matches"          value={data.total_matches.toString()}    accent="orange" />
          <StatCard label="Teams"                  value={data.total_teams.toString()}      accent="blue" />
          <StatCard label="AI Highlights Indexed"  value={data.total_highlights.toLocaleString()} accent="purple" />
          <StatCard label="Avg KDA · Top 10"       value={data.avg_kda_top10.toFixed(2)}   accent="gold" />
        </div>

        {/* Table */}
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center h-10 px-5 bg-[#17172A] border-b border-border text-[11px] font-semibold text-dim">
            <div className="w-12 text-center">#</div>
            <div className="flex-1 px-3">PLAYER</div>
            <div className="w-28 text-center">K / D / A</div>
            <div className="w-20 text-center">GPM</div>
            <div className="w-20 text-center">WIN %</div>
            <div className="w-32 text-center text-purple">AI IMPACT ✦</div>
            <div className="w-36 text-center">HIGHLIGHTS</div>
          </div>

          {data.players.map((p) => <PlayerRow key={p.account_id} player={p} />)}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Start backend + verify leaderboard renders**

```bash
# Terminal 1 — backend
PYTHONPATH=. uvicorn backend.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open `http://localhost:5173`. If seed hasn't run, you'll see the error state. That's correct — seed with fixture data to verify:

```bash
PYTHONPATH=. python -c "
from backend.models import LeaderboardResponse, RankedPlayer
from backend import cache
p = RankedPlayer(rank=1, account_id=105248644, name='Miracle-', team='Tundra',
    kda='12 / 2 / 8', avg_kda_ratio=6.67, avg_gpm=742.0,
    win_rate=0.78, ai_impact_score=97.4, highlight_count=14, top_heroes=[74])
lb = LeaderboardResponse(competition='ESL Pro Circuit 2025', total_matches=247,
    total_teams=16, total_highlights=1842, avg_kda_top10=4.82, players=[p])
cache.write_leaderboard(lb)
print('Written')
"
```

Reload browser. Expected: leaderboard table with Miracle- at rank 1, purple AI Impact score.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: leaderboard screen with stat cards and player table"
```

---

### Task 12: Player Detail Screen

**Files:**
- Create: `frontend/src/components/MatchCard.tsx`
- Create: `frontend/src/components/ClipCard.tsx`
- Create: `frontend/src/pages/PlayerDetail.tsx`

- [ ] **Step 1: Write MatchCard.tsx**

```tsx
import type { MatchSummary } from "../types";

interface Props { match: MatchSummary; }

export function MatchCard({ match }: Props) {
  const winColor = match.won ? "bg-green" : "bg-red";
  return (
    <div className="flex items-center gap-4 px-4 py-3 bg-surface border border-border rounded-lg">
      <div className={`w-1 h-9 rounded-full ${winColor}`} />
      <div className="flex-1">
        <div className="flex justify-between text-xs">
          <span className="font-semibold text-primary">vs {match.opponent}</span>
          <span className="text-dim">{match.duration_str}</span>
        </div>
        <div className="flex gap-3 mt-1 text-[11px]">
          <span className={match.won ? "text-green" : "text-primary"}>
            {match.kills} / {match.deaths} / {match.assists}
          </span>
          <span className="text-muted">{match.gpm} GPM</span>
          {match.clip_count > 0 && (
            <span className="text-purple">{match.clip_count} clips</span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write ClipCard.tsx**

```tsx
import type { Highlight } from "../types";

const TAG_STYLES: Record<string, string> = {
  RAMPAGE:   "bg-[#2A0A0A] text-red",
  GODLIKE:   "bg-[#0D2E0D] text-green",
  TEAMFIGHT: "bg-[#0D1020] text-blue-400",
  OBJECTIVE: "bg-[#1A1510] text-gold",
  CLUTCH:    "bg-[#200D44] text-purple",
};

const THUMB_COLORS: Record<string, string> = {
  RAMPAGE:   "#26100A",
  GODLIKE:   "#0A261A",
  TEAMFIGHT: "#0A1026",
  OBJECTIVE: "#26200A",
  CLUTCH:    "#1A0A33",
};

interface Props { clip: Highlight; }

export function ClipCard({ clip }: Props) {
  const tagStyle = TAG_STYLES[clip.play_type] ?? "bg-surface text-muted";
  const thumbBg  = THUMB_COLORS[clip.play_type] ?? "#13131A";

  return (
    <div className="flex-1 bg-surface border border-border rounded-xl overflow-hidden">
      {/* Thumbnail */}
      <div
        className="h-32 w-full flex items-center justify-center"
        style={{ backgroundColor: thumbBg }}
      >
        {clip.thumbnail_url
          ? <img src={clip.thumbnail_url} alt="" className="w-full h-full object-cover" />
          : <span className="text-3xl opacity-30">▶</span>
        }
      </div>

      {/* Info */}
      <div className="p-3 flex flex-col gap-2">
        {/* Tags */}
        <div className="flex gap-2">
          <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${tagStyle}`}>
            {clip.play_type}
          </span>
        </div>

        {/* Title */}
        <p className="text-xs font-semibold text-primary leading-tight line-clamp-1">
          {clip.description}
        </p>

        {/* Meta row */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-dim">
            {Math.floor(clip.start / 60)}:{String(Math.floor(clip.start % 60)).padStart(2,"0")}
            {clip.opponent ? ` · vs ${clip.opponent}` : ""}
          </span>
          <span className="text-[10px] font-bold text-gold flex items-center gap-1">
            🎙 {clip.excitement_score.toFixed(1)}
          </span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write PlayerDetail.tsx**

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { StatCard } from "../components/StatCard";
import { MatchCard } from "../components/MatchCard";
import { ClipCard } from "../components/ClipCard";
import { api } from "../api";
import type { PlayerDetail as PlayerDetailType } from "../types";

export function PlayerDetail() {
  const { accountId } = useParams<{ accountId: string }>();
  const nav = useNavigate();
  const [data, setData] = useState<PlayerDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accountId) return;
    api.player(Number(accountId))
      .then(setData)
      .catch((e) => setError(e.message));
  }, [accountId]);

  if (error) return <div className="min-h-screen bg-bg flex items-center justify-center text-muted">{error}</div>;
  if (!data)  return <div className="min-h-screen bg-bg flex items-center justify-center text-muted">Loading…</div>;

  const { player, recent_matches, highlights } = data;
  const winRate = (player.win_rate * 100).toFixed(0);
  const wins = Math.round(player.win_rate * recent_matches.length);

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <NavBar
        competition="ESL Pro Circuit 2025"
        backLabel="Leaderboard"
        onBack={() => nav("/")}
      />

      <div className="flex-1 px-10 py-7 flex flex-col gap-5">
        {/* Player card */}
        <div className="flex items-center gap-7 bg-surface border border-border rounded-xl px-7 py-5">
          <div className="w-16 h-16 rounded-full bg-orange flex-shrink-0" />
          <div className="flex flex-col gap-1.5">
            <span className="text-2xl font-bold text-primary">{player.name}</span>
            <div className="flex items-center gap-2.5 text-sm text-muted">
              <span>{player.team}</span>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold border border-[#1A5C1A] bg-[#0D2E0D] text-green">
                Carry
              </span>
            </div>
          </div>
          <div className="flex-1" />
          <div className="flex flex-col items-end gap-2">
            <span className="px-3 py-1 rounded text-xs font-semibold border border-[#1E4080] bg-[#0D1620] text-blue-400">
              Rank #{player.rank} · ESL Pro Circuit 2025
            </span>
            <span className="text-xs text-dim">
              {recent_matches.length} matches · {wins}W {recent_matches.length - wins}L
            </span>
          </div>
        </div>

        {/* Stat cards */}
        <div className="flex gap-4">
          <StatCard label="KDA RATIO"        value={player.avg_kda_ratio.toFixed(2)} accent="orange" />
          <StatCard label="GOLD PER MIN"     value={player.avg_gpm.toFixed(0)}      accent="blue" />
          <StatCard label="WIN RATE"         value={`${winRate}%`}                  accent="orange" />
          <div className="flex-1 bg-surface border border-purple rounded-xl p-4 flex flex-col gap-2">
            <span className="text-[10px] font-semibold text-purple">AI IMPACT SCORE ✦</span>
            <span className="text-2xl font-bold text-purple">{player.ai_impact_score.toFixed(1)}</span>
            <span className="text-xs text-muted">Ranked #{player.rank} in competition</span>
          </div>
        </div>

        {/* Two column */}
        <div className="flex gap-5 flex-1">
          {/* Match history */}
          <div className="w-96 flex flex-col gap-3 flex-shrink-0">
            <div className="flex justify-between items-center">
              <span className="text-sm font-bold text-primary">Match History</span>
              <span className="text-xs text-dim">{recent_matches.length} matches</span>
            </div>
            {recent_matches.map((m) => <MatchCard key={m.match_id} match={m} />)}
          </div>

          {/* AI Highlights */}
          <div className="flex-1 flex flex-col gap-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="text-purple text-sm">✦</span>
                <span className="text-sm font-bold text-primary">AI Highlights</span>
              </div>
              <span className="text-[9px] font-semibold px-2.5 py-1 rounded-full border border-[#3D2475] bg-[#1A0A33] text-purple">
                Powered by TwelveLabs
              </span>
            </div>

            {highlights.length === 0 ? (
              <div className="text-muted text-sm">No highlights indexed yet.</div>
            ) : (
              <>
                <div className="flex gap-3">
                  {highlights.slice(0, 2).map((h, i) => <ClipCard key={i} clip={h} />)}
                </div>
                <div className="flex gap-3">
                  {highlights.slice(2, 4).map((h, i) => <ClipCard key={i + 2} clip={h} />)}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify player detail renders with fixture data**

```bash
PYTHONPATH=. python -c "
from backend.models import PlayerDetail, RankedPlayer, MatchSummary, Highlight
from backend import cache

player = RankedPlayer(rank=1, account_id=105248644, name='Miracle-', team='Tundra Esports',
    kda='12 / 2 / 8', avg_kda_ratio=6.67, avg_gpm=742.0,
    win_rate=0.78, ai_impact_score=97.4, highlight_count=14, top_heroes=[74])

matches = [
    MatchSummary(match_id=1, opponent='Team Spirit', won=True, duration_str='42:18',
                 kills=15, deaths=1, assists=6, gpm=812, hero_id=74, clip_count=3),
    MatchSummary(match_id=2, opponent='OG Esports', won=True, duration_str='38:44',
                 kills=11, deaths=2, assists=9, gpm=758, hero_id=23, clip_count=2),
]

clips = [
    Highlight(video_id='v1', start=2052, end=2092, play_type='RAMPAGE',
              excitement_score=9.8, description='5-man wipe at Roshan pit',
              match_id=1, opponent='Team Spirit'),
    Highlight(video_id='v1', start=1800, end=1840, play_type='GODLIKE',
              excitement_score=9.4, description='Comeback teamfight win',
              match_id=2, opponent='OG Esports'),
    Highlight(video_id='v2', start=900, end=940, play_type='OBJECTIVE',
              excitement_score=8.7, description='Ancient solo takedown',
              match_id=1, opponent='Team Spirit'),
    Highlight(video_id='v2', start=600, end=640, play_type='TEAMFIGHT',
              excitement_score=8.2, description='Sunstrike triple kill',
              match_id=2, opponent='OG Esports'),
]

detail = PlayerDetail(player=player, recent_matches=matches, highlights=clips)
cache.write_player(105248644, detail)
print('Written')
"
```

Navigate to `http://localhost:5173/player/105248644`. Expected: player card, 4 stat tiles, 2 match cards, 4 highlight clips with colored tags and excitement scores.

- [ ] **Step 5: Final test run**

```bash
PYTHONPATH=. pytest tests/ -v
```
Expected: all tests `PASSED`

- [ ] **Step 6: Final commit**

```bash
git add frontend/src/
git commit -m "feat: player detail screen with match history and AI highlight clips"
```

---

## Demo Prep Checklist

Run these steps the evening before the hackathon demo. Steps 1–3 are the slow ones — start them early.

```bash
# ── Step 1: Fill in PLAYER_ROSTER in scripts/seed_index.py ───────────────────
# Find player account IDs at opendota.com/players/{name} or via liquipedia.

# ── Step 2: Map matches to stream segments ────────────────────────────────────
# Go to twitch.tv/esl_dota2/videos and collect the VOD URLs for the event days.
# Each URL is a 10-12 hour broadcast. Pass them all here:
python scripts/find_match_segments.py \
  --league "ESL One" \
  --streams \
    https://www.twitch.tv/videos/VOD_ID_DAY1 \
    https://www.twitch.tv/videos/VOD_ID_DAY2 \
    https://www.twitch.tv/videos/VOD_ID_DAY3

# Check the output — any unmapped matches need additional stream URLs:
cat data/match_segments.json | python -m json.tool | head -40

# ── Step 3: Run the seed script ───────────────────────────────────────────────
# This downloads each ~110-min segment, indexes it in TwelveLabs,
# discovers highlights, and computes scores. Takes 1-3 hrs total.
export TWELVELABS_API_KEY=your_key
export ESL_LEAGUE_NAME="ESL One"
PYTHONPATH=. python scripts/seed_index.py
# Copy the printed TWELVELABS_INDEX_ID into your .env

# ── Step 4: Verify data ───────────────────────────────────────────────────────
ls data/segments/     # downloaded video segments (~500MB each)
ls data/players/      # one JSON per player
cat data/leaderboard.json | python -m json.tool | head -20

# ── Step 5: Smoke test the API ────────────────────────────────────────────────
PYTHONPATH=. uvicorn backend.main:app &
curl http://localhost:8000/leaderboard | python -m json.tool | head -30
curl http://localhost:8000/player/105248644 | python -m json.tool | head -30

# ── Step 6: Dry run the demo in the browser ───────────────────────────────────
cd frontend && npm run dev
# Open http://localhost:5173 and walk both screens end-to-end
```
