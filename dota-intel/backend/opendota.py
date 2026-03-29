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
        # First try exact match
        for league in leagues:
            if name_lower == league.get("name", "").lower():
                return league
        # Fallback to substring match
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

    def get_player_name(self, account_id: int) -> str:
        """
        Fetches the player's name with fallback logic:
        A: Professional name (registered pro tag).
        B: Persona name (Steam nickname) as fallback.
        """
        try:
            profile = self.fetch_player_profile(account_id)
            p_obj = profile.get("profile", {})
            # A: Try the 'name' (official pro tag)
            pro_name = p_obj.get("name")
            if pro_name:
                return pro_name
            # B: Fallback to 'personaname' (display name)
            return p_obj.get("personaname", f"Player {account_id}")
        except Exception:
            return f"Player {account_id}"
