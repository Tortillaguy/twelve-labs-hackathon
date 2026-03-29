import json
import os
from pathlib import Path
from backend.models import LeaderboardResponse, PlayerDetail

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MOCK_DIR = DATA_DIR / "mock"

def write_leaderboard(response: LeaderboardResponse) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "leaderboard.json").write_text(response.model_dump_json(indent=2))

def read_leaderboard(demo: bool = False) -> LeaderboardResponse | None:
    path = (MOCK_DIR if demo else DATA_DIR) / "leaderboard.json"
    if not path.exists():
        return None
    return LeaderboardResponse.model_validate_json(path.read_text())

def write_player(account_id: int, detail: PlayerDetail) -> None:
    (DATA_DIR / "players").mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "players" / f"{account_id}.json"
    path.write_text(detail.model_dump_json(indent=2))

def read_player(account_id: int, demo: bool = False) -> PlayerDetail | None:
    path = (MOCK_DIR if demo else DATA_DIR) / "players" / f"{account_id}.json"
    if not path.exists():
        # Fallback to non-mock if mock doesn't exist but requested (for existing players in demo)
        if demo:
            return read_player(account_id, demo=False)
        return None
    return PlayerDetail.model_validate_json(path.read_text())
