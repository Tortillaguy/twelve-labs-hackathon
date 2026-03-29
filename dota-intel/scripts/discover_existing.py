#!/usr/bin/env python3
import sys
import os
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.twelvelabs_client import TwelveLabsClient
from backend.opendota import OpenDotaClient
from backend.models import PlayerDetail, LeaderboardResponse, Highlight, MatchSummary
from backend import cache
from backend.highlights import discover_event_anchored, merge_and_deduplicate
from backend.scoring import aggregate_player_stats, rank_players

def main():
    tl = TwelveLabsClient()
    od = OpenDotaClient()
    
    tl.get_or_create_index("dota-intel")
    
    print("[discover] Fetching existing videos in TwelveLabs...")
    videos = tl.list_videos()
    if not videos:
        print("[discover] No videos found in index. Please ingest first.")
        return

    processed_matches = []
    all_player_highlights = {}
    match_details_agg = []
    player_match_summaries = {}

    for v in videos:
        video_id = v["video_id"]
        filename = v.get("filename", "")
        m = re.search(r"match_(\d+)", filename)
        if not m:
            print(f"[discover] Skipping video {video_id} - filename '{filename}' does not contain match ID.")
            continue
            
        mid = int(m.group(1))
        print(f"\n[discover] Mapping match {mid} for video {video_id}...")
        
        # 1. Fetch OpenDota match detail
        raw = od.fetch_match_detail(mid)
        if not raw:
            print(f"[discover] Failed to fetch match {mid} from OpenDota.")
            continue

        kills_log = raw.get("kills_log") or []
        print(f"[discover] Raw match data fetched. Found {len(kills_log)} kills in log.")

        # 2. Calibrate Horn (or default 10m)
        print(f"[discover] Calibrating horn for {video_id}...")
        horn_offset = tl.calibrate_game_start(video_id, first_blood_time=raw.get("first_blood_time", 0))

        # 3. Identify Top 2 players by KDA to show a rich demo
        print(f"[discover] Identifying top performers...")
        # (kills + assists) / max(1, deaths)
        players_sorted = sorted(
            raw.get("players", []),
            key=lambda p: (p.get("kills", 0) + p.get("assists", 0)) / max(1, p.get("deaths", 0)),
            reverse=True
        )
        top_players = players_sorted[:2]
        
        # Add to rosters if not present
        from backend.models import MatchDetail, KillEvent, MatchPlayer
        kills = [KillEvent(time=k["time"], killer_id=k.get("player_slot", 0), victim_id=0) 
                 for k in raw.get("kills_log", [])]
        match_players_list = [MatchPlayer(
            account_id=p.get("account_id"),
            player_slot=p["player_slot"],
            hero_id=p["hero_id"],
            kills=p["kills"],
            deaths=p["deaths"],
            assists=p["assists"],
            gold_per_min=p["gold_per_min"],
            net_worth=p.get("net_worth", 0)
        ) for p in raw.get("players", [])]
        
        m_detail = MatchDetail(
            match_id=mid,
            duration=raw["duration"],
            start_time=raw["start_time"],
            radiant_win=raw["radiant_win"],
            kills_log=kills,
            players=match_players_list
        )
        match_details_agg.append(m_detail)

        # 4. Discover highlights for these top performers (lightweight — no Pegasus analyze)
        for p in top_players:
            aid = p.get("account_id")
            name = p.get("personaname") or p.get("name") or f"Player {p['player_slot']}"
            team_name = "Radiant" if p["player_slot"] < 128 else "Dire"
            
            print(f"[discover] >>> {name} ({aid}) ...")
            if aid not in all_player_highlights:
                all_player_highlights[aid] = []

            # Search TwelveLabs for exciting moments — skip expensive analyze_clip
            query = f"Dota 2 exciting play kill teamfight"
            clips = tl.search_highlights(query=query, page_limit=4)
            player_clips = 0
            for clip in clips:
                if clip["video_id"] != video_id:
                    continue
                player_clips += 1
                all_player_highlights[aid].append(Highlight(
                    video_id=clip["video_id"],
                    start=clip["start"],
                    end=clip["end"],
                    play_type="TEAMFIGHT",
                    excitement_score=float(clip.get("score") or 7.0),
                    description=clip.get("transcription") or "Exciting play moment",
                    player_name=name,
                    match_id=mid,
                    opponent="Enemy Team",
                    thumbnail_url=clip.get("thumbnail_url"),
                ))
            print(f"[discover]     Found {player_clips} clips for {name}")
            
            # Build match summary for this player
            is_radiant = p["player_slot"] < 128
            won = raw["radiant_win"] if is_radiant else not raw["radiant_win"]
            dur_m, dur_s = divmod(raw["duration"], 60)
            
            if aid not in player_match_summaries:
                player_match_summaries[aid] = []
            player_match_summaries[aid].append(MatchSummary(
                match_id=mid,
                opponent="Enemy Team",
                won=won,
                duration_str=f"{dur_m}:{dur_s:02d}",
                kills=p["kills"],
                deaths=p["deaths"],
                assists=p["assists"],
                gpm=p["gold_per_min"],
                hero_id=p["hero_id"],
                clip_count=player_clips,
            ))
            
            # Cache player performance stats
            stats = aggregate_player_stats(match_details_agg, aid, name, team_name)
            h_dedup = merge_and_deduplicate(all_player_highlights[aid])
            
            p_rank_mock = rank_players([{"stats": stats, "highlights": h_dedup}])[0]
            p_detail = PlayerDetail(
                player=p_rank_mock,
                recent_matches=player_match_summaries.get(aid, []),
                highlights=h_dedup
            )
            cache.write_player(aid, p_detail)

        processed_matches.append(mid)

    # 5. Build Final Leaderboard
    print("\n[discover] Finalizing Leaderboard...")
    ranked_input = []
    # Re-fetch for all top players found
    for aid, h_list in all_player_highlights.items():
        # Get name/team from any cache entry
        p_data = cache.read_player(aid)
        if p_data:
            stats = aggregate_player_stats(match_details_agg, aid, p_data.player.name, p_data.player.team)
            h_dedup = merge_and_deduplicate(h_list)
            ranked_input.append({"stats": stats, "highlights": h_dedup})

    final_ranked = rank_players(ranked_input)
    top10 = final_ranked[:10]
    avg_kda = sum(p.avg_kda_ratio for p in top10) / max(1, len(top10)) if top10 else 0.0
    lb = LeaderboardResponse(
        competition="ESL One Birmingham 2026",
        total_matches=len(processed_matches),
        total_teams=len(set(p.team for p in final_ranked)),
        total_highlights=sum(p.highlight_count for p in final_ranked),
        avg_kda_top10=round(avg_kda, 2),
        players=final_ranked
    )
    cache.write_leaderboard(lb)
    print(f"[discover] Done! Leaderboard saved to data/")

if __name__ == "__main__":
    main()
