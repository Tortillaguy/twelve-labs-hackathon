#!/usr/bin/env python3
"""
Fix player names in leaderboard.json and player/*.json files.
Replaces Steam persona names with professional names from the roster.
Also fixes team names.
"""
import json
from pathlib import Path

# Canonical pro roster: account_id → {name, team}
PLAYER_ROSTER = {
    173978074: {"name": "NothingToSay", "team": "Team Zero"},
    321580662: {"name": "Yatoro",       "team": "Team Spirit"},
    331855530: {"name": "Pure~",        "team": "Tundra Esports"},
    93618577:  {"name": "malr1ne",      "team": "Team Falcons"},
    898754153: {"name": "Lou",          "team": "Xtreme Gaming"},
}

DATA_DIR = Path(__file__).parent.parent / "data"

def fix_leaderboard():
    lb_path = DATA_DIR / "leaderboard.json"
    if not lb_path.exists():
        print("[fix] leaderboard.json not found, skipping.")
        return

    lb = json.loads(lb_path.read_text())
    fixed = 0
    for player in lb.get("players", []):
        aid = player.get("account_id")
        if aid in PLAYER_ROSTER:
            old_name = player["name"]
            new_name = PLAYER_ROSTER[aid]["name"]
            new_team = PLAYER_ROSTER[aid]["team"]
            if old_name != new_name or player.get("team") != new_team:
                print(f"[fix] Leaderboard: {old_name!r} → {new_name!r}, team → {new_team!r}")
                player["name"] = new_name
                player["team"] = new_team
                fixed += 1

    lb_path.write_text(json.dumps(lb, indent=2, ensure_ascii=False))
    print(f"[fix] Leaderboard: {fixed} player(s) updated.")


def fix_player_files():
    players_dir = DATA_DIR / "players"
    if not players_dir.exists():
        print("[fix] players/ directory not found, skipping.")
        return

    fixed = 0
    for pfile in players_dir.glob("*.json"):
        aid = int(pfile.stem)
        if aid not in PLAYER_ROSTER:
            continue

        data = json.loads(pfile.read_text())
        roster = PLAYER_ROSTER[aid]
        changed = False

        # Fix player.name and player.team
        if "player" in data:
            p = data["player"]
            if p.get("name") != roster["name"]:
                print(f"[fix] {pfile.name}: player.name {p.get('name')!r} → {roster['name']!r}")
                p["name"] = roster["name"]
                changed = True
            if p.get("team") != roster["team"]:
                print(f"[fix] {pfile.name}: player.team {p.get('team')!r} → {roster['team']!r}")
                p["team"] = roster["team"]
                changed = True

        # Fix highlights[].player_name
        for hl in data.get("highlights", []):
            if hl.get("player_name") != roster["name"]:
                print(f"[fix] {pfile.name}: highlight player_name {hl.get('player_name')!r} → {roster['name']!r}")
                hl["player_name"] = roster["name"]
                changed = True

        if changed:
            pfile.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            fixed += 1

    print(f"[fix] Player files: {fixed} file(s) updated.")


if __name__ == "__main__":
    fix_leaderboard()
    fix_player_files()
    print("[fix] Done!")
