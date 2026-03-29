from backend.models import KillEvent, Highlight
import time

CLIP_PADDING_SECONDS = 20  # seconds before/after event to include in clip

# Kill streak announcement tiers used in Dota 2 in-game banners
KILL_STREAK_TIERS = [
    "killing spree",
    "dominating",
    "mega kill",
    "ultra kill",
    "rampage",
    "godlike",
    "beyond godlike",
    "wicked sick",
]


def _name_matches(pegasus_name: str | None, target_name: str) -> bool:
    """Fuzzy check: does the Pegasus-extracted name refer to the target player?"""
    if not pegasus_name:
        return False
    return target_name.lower() in pegasus_name.lower() or pegasus_name.lower() in target_name.lower()


def _apply_streak_boost(excitement: float, streak_tier: str | None) -> float:
    """Boost excitement score based on kill streak tier announced in-game."""
    if not streak_tier:
        return excitement
    tier_index = next(
        (idx for idx, t in enumerate(KILL_STREAK_TIERS) if t in streak_tier.lower()),
        -1,
    )
    if tier_index >= 0:
        excitement = min(10.0, excitement + 0.25 * (tier_index + 1))
    return excitement


def discover_event_anchored(
    kills_log: list[KillEvent],
    video_id: str,
    game_start_offset: float,
    player_account_id: int,
    player_name: str,
    tl_client,
    match_id: int,
    opponent: str,
    hero_name: str = None,
) -> list[Highlight]:
    """
    For each kill where this player is the killer, ask Pegasus to classify
    the ±CLIP_PADDING_SECONDS window around the event.
    Pegasus is asked to confirm the player's name was mentioned by casters.
    """
    highlights = []
    for kill in kills_log:
        if kill.killer_id != player_account_id:
            continue
        vod_time = game_start_offset + kill.time
        start = max(0, vod_time - CLIP_PADDING_SECONDS)
        end = vod_time + CLIP_PADDING_SECONDS

        analysis_start = time.time()
        analysis = tl_client.analyze_clip(video_id, start, end, target_player=player_name, target_hero=hero_name)
        analysis_duration = int(time.time() - analysis_start)
        extracted_name = analysis.get("player_name")
        excitement = _apply_streak_boost(
            float(analysis.get("excitement_score", 5.0)),
            analysis.get("streak_tier"),
        )

        highlights.append(Highlight(
            video_id=video_id,
            start=start,
            end=end,
            play_type=analysis.get("play_type", "TEAMFIGHT"),
            excitement_score=excitement,
            description=analysis.get("description", ""),
            player_name=extracted_name or player_name,
            match_id=match_id,
            opponent=opponent,
            ai_insight=analysis.get("ai_insight"),
            surfaced_delta_seconds=analysis_duration,
        ))
    return highlights


def discover_discovery_first(
    index_id: str,
    video_id: str,
    player_name: str,
    tl_client,
    match_id: int = None,
    opponent: str = None,
    hero_name: str = None,
) -> list[Highlight]:
    """
    Run three targeted TwelveLabs searches for player-specific signal types:
      1. In-game announcement banner (e.g. "NothingToSay is on a killing spree")
      2. Excited caster mention of the player by name
      3. Kill streak visual moment (rampage screen flash, kill feed, etc.)
    Each clip is sent to Pegasus for classification, then post-filtered to
    confirm the extracted player_name matches the target.
    """
    streak_labels = " ".join(KILL_STREAK_TIERS)
    hero_context = f" {hero_name}" if hero_name else ""

    targeted_queries = [
        # Signal 1: in-game kill streak announcement banner
        (
            f'"{player_name} is on a killing spree" OR "{player_name} is dominating" '
            f'OR "{player_name} rampage" kill streak banner Dota 2 announcement{hero_context}',
            ["visual", "audio"],
            3,
        ),
        # Signal 2: excited caster positive mention
        (
            f"caster commentator shoutout {player_name} amazing incredible insane "
            f"Dota 2 broadcast excited crowd focus: {player_name}{hero_context}",
            ["audio"],
            3,
        ),
        # Signal 3: kill streak visual — player specific
        (
            f'Dota 2 {streak_labels} kill streak "{player_name}"{hero_context} red screen flash '
            f'multi kill rampage animation kill feed',
            ["visual", "audio"],
            3,
        ),
    ]

    seen: set[tuple[str, float]] = set()  # deduplicate before Pegasus calls
    candidate_clips: list[dict] = []

    for query, options, page_limit in targeted_queries:
        clips = tl_client.search_highlights(
            query=query,
            options=options,
            page_limit=page_limit,
        )
        for clip in clips:
            if clip["video_id"] != video_id:
                continue
            key = (clip["video_id"], round(clip["start"], 1))
            if key not in seen:
                seen.add(key)
                candidate_clips.append(clip)

    highlights = []
    for clip in candidate_clips:
        analysis_start = time.time()
        analysis = tl_client.analyze_clip(
            clip["video_id"], clip["start"], clip["end"], target_player=player_name, target_hero=hero_name
        )
        analysis_duration = int(time.time() - analysis_start)
        extracted_name = analysis.get("player_name")

        # Post-filter: skip clips where Pegasus names a *different* player
        # (allow through if Pegasus returned null — it may just mean quiet moment)
        if extracted_name and not _name_matches(extracted_name, player_name):
            continue

        excitement = _apply_streak_boost(
            float(analysis.get("excitement_score", 5.0)),
            analysis.get("streak_tier"),
        )

        highlights.append(Highlight(
            video_id=clip["video_id"],
            start=clip["start"],
            end=clip["end"],
            play_type=analysis.get("play_type", "TEAMFIGHT"),
            excitement_score=excitement,
            description=analysis.get("description", ""),
            player_name=extracted_name or player_name,
            thumbnail_url=clip.get("thumbnail_url"),
            match_id=match_id,
            opponent=opponent,
            ai_insight=analysis.get("ai_insight"),
            surfaced_delta_seconds=analysis_duration,
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
            if current.excitement_score > last.excitement_score:
                merged[-1] = current
        else:
            merged.append(current)

    merged.sort(key=lambda h: h.excitement_score, reverse=True)
    return merged
