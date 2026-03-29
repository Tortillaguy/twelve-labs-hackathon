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

        from backend.opendota import OpenDotaClient
        client = OpenDotaClient()
        avatar_url = None
        try:
            profile = client.fetch_player_profile(stats.account_id)
            avatar_url = profile.get("profile", {}).get("avatarfull")
        except Exception:
            pass

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
            avatar_url=avatar_url,
        ))


    scored.sort(key=lambda p: p.ai_impact_score, reverse=True)
    for i, p in enumerate(scored):
        p.rank = i + 1
    return scored
