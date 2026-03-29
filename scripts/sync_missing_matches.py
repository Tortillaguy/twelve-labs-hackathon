import sys
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv

# Add dota-intel to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "dota-intel"))
load_dotenv()

from backend.twelvelabs_client import TwelveLabsClient
from backend.opendota import OpenDotaClient
from backend.cache import read_leaderboard, write_player, write_leaderboard
from backend.highlights import discover_event_anchored, merge_and_deduplicate
from backend.models import PlayerDetail, Highlight, MatchSummary, MatchDetail, KillEvent, MatchPlayer
from backend.scoring import aggregate_player_stats, rank_players

def search_highlights_with_retry(tl, query, page_limit=4, retries=3):
    for i in range(retries):
        try:
            return tl.search_highlights(query=query, page_limit=page_limit)
        except Exception as e:
            if "429" in str(e):
                print(f"[retry] Rate limited, waiting 10s... (attempt {i+1}/{retries})")
                time.sleep(10)
            else:
                raise e
    return []

def main():
    tl = TwelveLabsClient()
    od = OpenDotaClient()
    tl.get_or_create_index("dota-intel")
    
    # 1. Get existing captured matches (from leaderboard)
    lb = read_leaderboard()
    captured_matches = set()
    if lb:
        # We need to find which matches were used. 
        # Since matches are not listed in LeaderboardResponse, we check data/players/
        player_list = lb.players
        for p in player_list:
            player_data = (Path(__file__).parent.parent / f"data/players/{p.account_id}.json")
            if player_data.exists():
                import json
                pd_json = json.loads(player_data.read_text())
                for m in pd_json.get("recent_matches", []):
                    captured_matches.add(m.get("match_id"))

    print(f"[sync] Currently captured matches: {captured_matches}")

    # 2. List all videos in Twelve Labs
    videos = tl.list_videos()
    print(f"[sync] Found {len(videos)} videos in Twelve Labs index.")

    to_process = []
    for v in videos:
        filename = v.get("filename", "")
        m = re.search(r"match_(\d+)", filename)
        if m:
            mid = int(m.group(1))
            if mid not in captured_matches:
                print(f"[sync] Identified missing match {mid} (video {v['video_id']})")
                to_process.append((mid, v['video_id']))
            else:
                print(f"[sync] Match {mid} already captured.")

    if not to_process:
        print("[sync] No missing matches found in Twelve Labs.")
        return

    # 3. Process missing matches (similar to discover_existing.py but more robust)
    all_player_highlights = {}
    match_details_agg = []
    player_match_summaries = {}

    import backend.cache as cache

    for mid, video_id in to_process:
        print(f"\n[sync] Processing match {mid}...")
        raw = od.fetch_match_detail(mid)
        if not raw:
            print(f"[sync] Failed to fetch match {mid} from OpenDota.")
            continue

        # 1. Map OpenDota data
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

        # 2. Find highlights for top 2 players
        players_sorted = sorted(
            raw.get("players", []),
            key=lambda p: (p.get("kills", 0) + p.get("assists", 0)) / max(1, p.get("deaths", 0)),
            reverse=True
        )
        top_players = [p for p in players_sorted if p.get("account_id")][:2]
        
        for p in top_players:
            aid = p.get("account_id")
            name = p.get("personaname") or p.get("name") or f"Player {p['player_slot']}"
            team_name = "Radiant" if p["player_slot"] < 128 else "Dire"
            print(f"[sync]   -> Finding highlights for {name} ({aid})...")
            
            if aid not in all_player_highlights:
                all_player_highlights[aid] = []

            query = f"Dota 2 exciting play kill teamfight"
            clips = search_highlights_with_retry(tl, query, page_limit=4)
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
            
            # Incremental Save for this player
            existing_pd = cache.read_player(aid)
            h_merged = (existing_pd.highlights if existing_pd else []) + all_player_highlights[aid]
            h_dedup = merge_and_deduplicate(h_merged)
            
            m_summaries = (existing_pd.recent_matches if existing_pd else []) + [player_match_summaries[aid][-1]]
            m_dedup = {m.match_id: m for m in m_summaries}.values()
            m_list = sorted(m_dedup, key=lambda x: x.match_id, reverse=True)
            
            # Simple stats update for now
            from backend.models import PlayerStats
            p_stats = aggregate_player_stats([m_detail], aid, name, team_name) if not existing_pd else existing_pd.player
            # (Note: this is simplified, but ensures we at least have a record)
            
            lp_temp = PlayerDetail(
                player=p_stats,
                recent_matches=m_list,
                highlights=h_dedup
            )
            cache.write_player(aid, lp_temp)

        # Update leaderboard count after each match
        lb_curr = read_leaderboard()
        if lb_curr:
            lb_curr.total_matches += 1
            # Recalculate if we have ranks, but at least we have the count
            cache.write_leaderboard(lb_curr)
            
        print(f"[sync] Match {mid} processed and saved incrementally.")

if __name__ == "__main__":
    main()
