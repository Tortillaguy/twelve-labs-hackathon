from pydantic import BaseModel
from typing import Optional, Any

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

class PlayerDetail(BaseModel):
    player: RankedPlayer
    recent_matches: list[MatchSummary]
    highlights: list[Highlight]

class LeaderboardResponse(BaseModel):
    competition: str
    total_matches: int
    total_teams: int
    total_highlights: int
    avg_kda_top10: float
    players: list[RankedPlayer]

# For circular references
MatchDetail.model_rebuild()
PlayerDetail.model_rebuild()
