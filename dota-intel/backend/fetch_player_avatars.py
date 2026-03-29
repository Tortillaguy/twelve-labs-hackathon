import os
import json
import httpx
import re
from pathlib import Path
from backend.opendota import OpenDotaClient

# We'll update ALL data directories found in the workspace
WORKSPACE_ROOT = Path(__file__).parent.parent.parent

def fetch_and_update():
    client = OpenDotaClient()
    
    # Locations to search for leaderboard.json
    search_dirs = [
        WORKSPACE_ROOT / "data",
        WORKSPACE_ROOT / "data" / "mock",
        WORKSPACE_ROOT / "dota-intel" / "data"
    ]
    
    for data_dir in search_dirs:
        lb_path = data_dir / "leaderboard.json"
        if not lb_path.exists():
            continue
            
        print(f"\nProcessing {lb_path}...")
        lb_data = json.loads(lb_path.read_text())
        
        for player in lb_data.get("players", []):
            account_id = player.get("account_id")
            if not account_id:
                continue
            
            print(f"Updating player {player['name']} ({account_id})")
            
            # Use Steam avatar as primary because Liquipedia blocks hotlinking
            avatar_url = None
            try:
                profile = client.fetch_player_profile(account_id)
                avatar_url = profile.get("profile", {}).get("avatarfull")
                if avatar_url:
                    print(f"  Found Steam avatar: {avatar_url}")
            except Exception as e:
                print(f"  OpenDota fetch failed for {account_id}: {e}")
            
            if avatar_url:
                player["avatar_url"] = avatar_url
                
                # Update individual player file in 'players' subdir
                player_file = data_dir / "players" / f"{account_id}.json"
                if player_file.exists():
                    player_detail = json.loads(player_file.read_text())
                    player_detail["player"]["avatar_url"] = avatar_url
                    player_file.write_text(json.dumps(player_detail, indent=2))
        
        # Save updated leaderboard
        lb_path.write_text(json.dumps(lb_data, indent=2))

if __name__ == "__main__":
    fetch_and_update()
