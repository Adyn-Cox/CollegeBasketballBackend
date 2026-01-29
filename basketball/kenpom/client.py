"""
KenPom API Client for fetching basketball analytics data.

Usage:
    from basketball.kenpom.client import KenPomClient
    
    client = KenPomClient()
    ratings = client.get_ratings(season=2025)
    four_factors = client.get_four_factors(season=2025)
"""
import requests
import time
from typing import Optional, List, Dict, Any
from django.conf import settings


class KenPomAPIError(Exception):
    """Exception raised for KenPom API errors."""
    pass


class KenPomClient:
    """Client for interacting with the KenPom API."""
    
    BASE_URL = "https://kenpom.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the KenPom client.
        
        Args:
            api_key: Optional API key. If not provided, uses settings.KENPOM_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'KENPOM_API_KEY', None)
        if not self.api_key:
            raise ValueError(
                "KENPOM_API_KEY is required. Set it in your .env file or pass it to the client."
            )
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        self._last_request_time = 0
        self._min_request_interval = 1.0  # Minimum seconds between requests
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Make a GET request to the KenPom API.
        
        Args:
            endpoint: The API endpoint name (e.g., 'ratings', 'four-factors')
            params: Optional query parameters
            
        Returns:
            List of dictionaries containing the response data
            
        Raises:
            KenPomAPIError: If the API request fails
        """
        self._rate_limit()
        
        url = f"{self.BASE_URL}/api.php"
        request_params = params.copy() if params else {}
        request_params['endpoint'] = endpoint
        
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                params=request_params, 
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise KenPomAPIError("Invalid API key or unauthorized access")
            elif response.status_code == 429:
                raise KenPomAPIError("Rate limit exceeded. Please wait before making more requests.")
            else:
                raise KenPomAPIError(f"HTTP error {response.status_code}: {e}")
        except requests.exceptions.RequestException as e:
            raise KenPomAPIError(f"Request failed: {e}")
        except ValueError as e:
            raise KenPomAPIError(f"Invalid JSON response: {e}")
    
    # ============== Ratings Endpoints ==============
    
    def get_ratings(
        self, 
        season: Optional[int] = None, 
        team_id: Optional[int] = None, 
        conference: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get team ratings, strength of schedule, tempo, and possession length data.
        
        Args:
            season: Year/Season (e.g., 2025) - ending year of the season
            team_id: KenPom Team ID
            conference: Conference short name (e.g., 'B12', 'ACC')
            
        Returns:
            List of rating records
            
        Note:
            At least one of season or team_id is required.
            If using conference, season must also be provided.
        """
        if not season and not team_id:
            raise ValueError("At least one of season or team_id is required")
        
        params = {}
        if season:
            params['y'] = season
        if team_id:
            params['team_id'] = team_id
        if conference:
            params['c'] = conference
        
        return self._get('ratings', params)
    
    def get_archive(
        self,
        date: Optional[str] = None,
        season: Optional[int] = None,
        preseason: bool = False,
        team_id: Optional[int] = None,
        conference: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical team ratings from a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
            season: Ending year of season (required if preseason=True)
            preseason: If True, retrieves preseason ratings
            team_id: KenPom Team ID
            conference: Conference short name
            
        Returns:
            List of archived rating records
            
        Note:
            Either date is required, or both preseason=True and season are required.
        """
        if not date and not (preseason and season):
            raise ValueError("Either date is required, or both preseason=True and season")
        
        params = {}
        if date:
            params['d'] = date
        if season:
            params['y'] = season
        if preseason:
            params['preseason'] = 'true'
        if team_id:
            params['team_id'] = team_id
        if conference:
            params['c'] = conference
        
        return self._get('archive', params)
    
    # ============== Four Factors Endpoint ==============
    
    def get_four_factors(
        self,
        season: Optional[int] = None,
        team_id: Optional[int] = None,
        conference: Optional[str] = None,
        conf_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get Four Factors statistics for offense and defense.
        
        Args:
            season: Ending year of season (e.g., 2025)
            team_id: KenPom Team ID
            conference: Conference short name
            conf_only: If True, returns conference-only statistics
            
        Returns:
            List of Four Factors records
            
        Note:
            At least one of season or team_id is required.
        """
        if not season and not team_id:
            raise ValueError("At least one of season or team_id is required")
        
        params = {}
        if season:
            params['y'] = season
        if team_id:
            params['team_id'] = team_id
        if conference:
            params['c'] = conference
        if conf_only:
            params['conf_only'] = 'true'
        
        return self._get('four-factors', params)
    
    # ============== Point Distribution Endpoint ==============
    
    def get_point_distribution(
        self,
        season: Optional[int] = None,
        team_id: Optional[int] = None,
        conference: Optional[str] = None,
        conf_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get point distribution statistics (FT, 2PT, 3PT percentages).
        
        Args:
            season: Ending year of season
            team_id: KenPom Team ID
            conference: Conference short name
            conf_only: If True, returns conference-only statistics
            
        Returns:
            List of point distribution records
        """
        if not season and not team_id:
            raise ValueError("At least one of season or team_id is required")
        
        params = {}
        if season:
            params['y'] = season
        if team_id:
            params['team_id'] = team_id
        if conference:
            params['c'] = conference
        if conf_only:
            params['conf_only'] = 'true'
        
        return self._get('pointdist', params)
    
    # ============== Height Endpoint ==============
    
    def get_height(
        self,
        season: Optional[int] = None,
        team_id: Optional[int] = None,
        conference: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get team height, experience, bench strength, and continuity stats.
        
        Args:
            season: Ending year of season
            team_id: KenPom Team ID
            conference: Conference short name
            
        Returns:
            List of height/experience records
        """
        if not season and not team_id:
            raise ValueError("At least one of season or team_id is required")
        
        params = {}
        if season:
            params['y'] = season
        if team_id:
            params['team_id'] = team_id
        if conference:
            params['c'] = conference
        
        return self._get('height', params)
    
    # ============== Miscellaneous Stats Endpoint ==============
    
    def get_misc_stats(
        self,
        season: Optional[int] = None,
        team_id: Optional[int] = None,
        conference: Optional[str] = None,
        conf_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get miscellaneous advanced statistics.
        
        Args:
            season: Ending year of season
            team_id: KenPom Team ID
            conference: Conference short name
            conf_only: If True, returns conference-only statistics
            
        Returns:
            List of miscellaneous stats records
        """
        if not season and not team_id:
            raise ValueError("At least one of season or team_id is required")
        
        params = {}
        if season:
            params['y'] = season
        if team_id:
            params['team_id'] = team_id
        if conference:
            params['c'] = conference
        if conf_only:
            params['conf_only'] = 'true'
        
        return self._get('misc-stats', params)
    
    # ============== FanMatch Endpoint ==============
    
    def get_fanmatch(self, date: str) -> List[Dict[str, Any]]:
        """
        Get game predictions for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of game prediction records
            
        Note:
            Only dates up to and including the current date are available.
        """
        if not date:
            raise ValueError("date is required")
        
        return self._get('fanmatch', {'d': date})
    
    # ============== Conference Ratings Endpoint ==============
    
    def get_conference_ratings(
        self,
        season: Optional[int] = None,
        conference: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conference ratings for a season.
        
        Args:
            season: Ending year of season
            conference: Conference short name
            
        Returns:
            List of conference rating records
            
        Note:
            At least one parameter (season or conference) is required.
        """
        if not season and not conference:
            raise ValueError("At least one of season or conference is required")
        
        params = {}
        if season:
            params['y'] = season
        if conference:
            params['c'] = conference
        
        return self._get('conf-ratings', params)
    
    # ============== Teams Endpoint ==============
    
    def get_teams(
        self,
        season: int,
        conference: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of teams for a season.
        
        Args:
            season: Ending year of season (required)
            conference: Conference short name
            
        Returns:
            List of team records with TeamID, TeamName, Coach, Arena, etc.
        """
        params = {'y': season}
        if conference:
            params['c'] = conference
        
        return self._get('teams', params)
    
    # ============== Conferences Endpoint ==============
    
    def get_conferences(self, season: int) -> List[Dict[str, Any]]:
        """
        Get list of conferences for a season.
        
        Args:
            season: Ending year of season (required)
            
        Returns:
            List of conference records with ConfID, ConfShort, ConfLong
        """
        return self._get('conferences', {'y': season})
