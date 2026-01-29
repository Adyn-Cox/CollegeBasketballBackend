"""
FastAPI application for College Basketball Backend.
Maintains the same API structure as Django REST Framework for frontend compatibility.
"""
import os
import sys
from pathlib import Path

# Add project root to path so we can import Django modules
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Setup Django before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from fastapi import FastAPI, HTTPException, Depends, Header, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import requests
from datetime import datetime, date, timedelta, timezone
import zoneinfo
from asgiref.sync import sync_to_async

from authentication.models import SupabaseUser
from authentication.utils import get_jwt_validator
from django.conf import settings
from django.db.models import Q

from basketball.models import (
    Team, Game, TeamStats, Conference, Venue, FavoriteTeam, MatchupPrediction,
    KenPomTeam, KenPomRating, KenPomRatingArchive, KenPomFourFactors,
    KenPomFanMatch, KenPomHeight, KenPomMiscStats,
    MLPrediction, MLModelVersion
)


# Pydantic models for request/response schemas
class LoginRequest(BaseModel):
    """Login request schema."""
    access_token: str = Field(..., description="Supabase access token")
    refresh_token: str = Field(..., description="Supabase refresh token")


class UserResponse(BaseModel):
    """User response schema."""
    supabase_user_id: str
    email: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response schema."""
    message: str
    user: UserResponse
    created: bool


class LogoutRequest(BaseModel):
    """Logout request schema (optional refresh_token)."""
    refresh_token: Optional[str] = None


class LogoutResponse(BaseModel):
    """Logout response schema."""
    message: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResponse(BaseModel):
    """Refresh token response schema."""
    access_token: str
    refresh_token: str


# ============== Basketball Pydantic Models ==============

class ConferenceResponse(BaseModel):
    """Conference response schema."""
    id: int
    name: str
    abbreviation: str

    class Config:
        from_attributes = True


class VenueResponse(BaseModel):
    """Venue response schema."""
    id: int
    name: str
    city: str
    state: str
    capacity: Optional[int] = None

    class Config:
        from_attributes = True


class TeamListResponse(BaseModel):
    """Team list item response schema."""
    id: int
    source_id: str
    school: str
    mascot: str
    abbreviation: str
    display_name: str
    short_display_name: str
    primary_color: str
    secondary_color: str
    conference: Optional[ConferenceResponse] = None
    has_predictions: bool = False  # True if team has KenPom data for ML predictions

    class Config:
        from_attributes = True


class TeamDetailResponse(BaseModel):
    """Team detail response schema with venue."""
    id: int
    source_id: str
    school: str
    mascot: str
    abbreviation: str
    display_name: str
    short_display_name: str
    primary_color: str
    secondary_color: str
    conference: Optional[ConferenceResponse] = None
    venue: Optional[VenueResponse] = None

    class Config:
        from_attributes = True


class TeamStatsResponse(BaseModel):
    """Team stats response schema."""
    id: int
    team_id: int
    season: int
    wins: int
    losses: int
    conference_wins: int
    conference_losses: int
    points_per_game: Optional[float] = None
    points_allowed_per_game: Optional[float] = None
    field_goal_pct: Optional[float] = None
    three_point_pct: Optional[float] = None
    free_throw_pct: Optional[float] = None
    rebounds_per_game: Optional[float] = None
    assists_per_game: Optional[float] = None
    steals_per_game: Optional[float] = None
    blocks_per_game: Optional[float] = None
    turnovers_per_game: Optional[float] = None
    record: str
    conference_record: str
    win_pct: float

    class Config:
        from_attributes = True


class GameTeamResponse(BaseModel):
    """Simplified team for game response."""
    id: int
    school: str
    abbreviation: str
    display_name: str
    primary_color: str
    secondary_color: str

    class Config:
        from_attributes = True


class GameResponse(BaseModel):
    """Game response schema."""
    id: int
    ncaa_game_id: str
    date: date
    time: Optional[str] = None
    home_team: GameTeamResponse
    away_team: GameTeamResponse
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: str
    status_detail: str
    season: int
    season_type: str
    venue: Optional[VenueResponse] = None

    class Config:
        from_attributes = True


class TeamsListResponse(BaseModel):
    """Paginated teams list response."""
    total: int
    teams: List[TeamListResponse]


class GamesListResponse(BaseModel):
    """Paginated games list response."""
    total: int
    games: List[GameResponse]


# FastAPI app
app = FastAPI(
    title="College Basketball Backend API",
    description="Backend API for college basketball predictor",
    version="1.0.0"
)

# CORS configuration (same as Django)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/refresh",
]


async def get_current_user(
    authorization: Optional[str] = Header(None)
) -> Optional[SupabaseUser]:
    """
    Dependency to get current user from Bearer token.
    Returns None for public endpoints or when no token is provided.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split(" ")[1]
    
    # Validate token (sync operation, but validator is thread-safe)
    validator = get_jwt_validator()
    token_payload = validator.validate_token(token)
    
    if not token_payload:
        return None
    
    # Extract user ID from token
    user_id = validator.extract_user_id(token_payload)
    
    if not user_id:
        return None
    
    # Get user from database (must use sync_to_async for Django ORM)
    try:
        user = await sync_to_async(SupabaseUser.objects.get)(supabase_user_id=user_id)
        return user
    except SupabaseUser.DoesNotExist:
        return None


async def require_auth(
    current_user: Optional[SupabaseUser] = Depends(get_current_user)
) -> SupabaseUser:
    """
    Dependency that requires authentication.
    Raises 401 if user is not authenticated.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    return current_user


@app.post("/api/auth/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest):
    """
    Public endpoint to login and save user information.
    Accepts access_token and refresh_token from Supabase.
    """
    # Validate the access token
    validator = get_jwt_validator()
    token_payload = validator.validate_token(request.access_token)
    
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )
    
    # Extract user information from token
    user_id = validator.extract_user_id(token_payload)
    email = token_payload.get('email') or token_payload.get('user_metadata', {}).get('email', '')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Get or create user in database (must use sync_to_async for Django ORM)
    def _update_or_create_user():
        return SupabaseUser.objects.update_or_create(
            supabase_user_id=user_id,
            defaults={
                'email': email,
                'refresh_token': request.refresh_token,
            }
        )
    
    user, created = await sync_to_async(_update_or_create_user)()
    
    return LoginResponse(
        message="Login successful",
        user=UserResponse(
            supabase_user_id=str(user.supabase_user_id),
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at
        ),
        created=created
    )


@app.post("/api/auth/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(
    request: LogoutRequest,
    current_user: Optional[SupabaseUser] = Depends(get_current_user)
):
    """
    Public endpoint to logout and remove refresh token.
    Optionally accepts a token in the header to identify the user.
    """
    # Try to get user from Bearer token first
    if current_user and isinstance(current_user, SupabaseUser):
        # Remove refresh token (must use sync_to_async for Django ORM)
        current_user.refresh_token = None
        await sync_to_async(current_user.save)()
        return LogoutResponse(message="Logout successful")
    
    # If no user from token, check if refresh_token is in body
    if request.refresh_token:
        try:
            user = await sync_to_async(SupabaseUser.objects.get)(refresh_token=request.refresh_token)
            user.refresh_token = None
            await sync_to_async(user.save)()
            return LogoutResponse(message="Logout successful")
        except SupabaseUser.DoesNotExist:
            pass
    
    # If we can't identify the user, still return success (idempotent operation)
    return LogoutResponse(message="Logout successful")


@app.post("/api/auth/refresh", response_model=RefreshTokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(request: RefreshTokenRequest):
    """
    Public endpoint to refresh access token using refresh token.
    Exchanges refresh token with Supabase for new access token.
    """
    # Verify refresh token exists in our database (must use sync_to_async for Django ORM)
    try:
        user = await sync_to_async(SupabaseUser.objects.get)(refresh_token=request.refresh_token)
    except SupabaseUser.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Exchange refresh token with Supabase for new tokens
    supabase_url = getattr(settings, 'SUPABASE_URL', None)
    if not supabase_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration error"
        )
    
    # Call Supabase token refresh endpoint
    try:
        response = requests.post(
            f"{supabase_url}/auth/v1/token?grant_type=refresh_token",
            json={'refresh_token': request.refresh_token},
            headers={
                'Content-Type': 'application/json',
                'apikey': getattr(settings, 'SUPABASE_ANON_KEY', ''),
            },
            timeout=10
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh token with Supabase"
            )
        
        data = response.json()
        new_access_token = data.get('access_token')
        new_refresh_token = data.get('refresh_token', request.refresh_token)  # Fallback to old if not provided
        
        # Update refresh token in database (must use sync_to_async for Django ORM)
        user.refresh_token = new_refresh_token
        await sync_to_async(user.save)()
        
        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token
        )
        
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to communicate with Supabase"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# ============== Basketball Endpoints ==============

def _serialize_team_list(team: Team, kenpom_team_ids: set = None) -> dict:
    """Serialize team for list response.
    
    Args:
        team: Team model instance
        kenpom_team_ids: Optional set of team IDs that have KenPom data (for efficiency)
    """
    # Check if team has KenPom predictions available
    if kenpom_team_ids is not None:
        has_predictions = team.id in kenpom_team_ids
    else:
        has_predictions = KenPomRating.objects.filter(team=team).exists()
    
    return {
        "id": team.id,
        "source_id": team.source_id,
        "school": team.school,
        "mascot": team.mascot,
        "abbreviation": team.abbreviation,
        "display_name": team.display_name,
        "short_display_name": team.short_display_name,
        "primary_color": team.primary_color,
        "secondary_color": team.secondary_color,
        "conference": {
            "id": team.conference.id,
            "name": team.conference.name,
            "abbreviation": team.conference.abbreviation,
        } if team.conference else None,
        "has_predictions": has_predictions,
    }


def _serialize_team_detail(team: Team) -> dict:
    """Serialize team for detail response."""
    result = _serialize_team_list(team)
    result["venue"] = {
        "id": team.venue.id,
        "name": team.venue.name,
        "city": team.venue.city,
        "state": team.venue.state,
        "capacity": team.venue.capacity,
    } if team.venue else None
    return result


def _serialize_game(game: Game) -> dict:
    """Serialize game for response."""
    return {
        "id": game.id,
        "ncaa_game_id": game.ncaa_game_id,
        "date": game.date,
        "time": game.time.strftime("%H:%M") if game.time else None,
        "home_team": {
            "id": game.home_team.id,
            "school": game.home_team.school,
            "abbreviation": game.home_team.abbreviation,
            "display_name": game.home_team.display_name,
            "primary_color": game.home_team.primary_color,
            "secondary_color": game.home_team.secondary_color,
        },
        "away_team": {
            "id": game.away_team.id,
            "school": game.away_team.school,
            "abbreviation": game.away_team.abbreviation,
            "display_name": game.away_team.display_name,
            "primary_color": game.away_team.primary_color,
            "secondary_color": game.away_team.secondary_color,
        },
        "home_score": game.home_score,
        "away_score": game.away_score,
        "status": game.status,
        "status_detail": game.status_detail,
        "season": game.season,
        "season_type": game.season_type,
        "venue": {
            "id": game.venue.id,
            "name": game.venue.name,
            "city": game.venue.city,
            "state": game.venue.state,
            "capacity": game.venue.capacity,
        } if game.venue else None,
    }


def _serialize_team_stats(stats: TeamStats) -> dict:
    """Serialize team stats for response."""
    return {
        "id": stats.id,
        "team_id": stats.team_id,
        "season": stats.season,
        "wins": stats.wins,
        "losses": stats.losses,
        "conference_wins": stats.conference_wins,
        "conference_losses": stats.conference_losses,
        "points_per_game": float(stats.points_per_game) if stats.points_per_game else None,
        "points_allowed_per_game": float(stats.points_allowed_per_game) if stats.points_allowed_per_game else None,
        "field_goal_pct": float(stats.field_goal_pct) if stats.field_goal_pct else None,
        "three_point_pct": float(stats.three_point_pct) if stats.three_point_pct else None,
        "free_throw_pct": float(stats.free_throw_pct) if stats.free_throw_pct else None,
        "rebounds_per_game": float(stats.rebounds_per_game) if stats.rebounds_per_game else None,
        "assists_per_game": float(stats.assists_per_game) if stats.assists_per_game else None,
        "steals_per_game": float(stats.steals_per_game) if stats.steals_per_game else None,
        "blocks_per_game": float(stats.blocks_per_game) if stats.blocks_per_game else None,
        "turnovers_per_game": float(stats.turnovers_per_game) if stats.turnovers_per_game else None,
        "record": stats.record,
        "conference_record": stats.conference_record,
        "win_pct": stats.win_pct,
    }


@app.get("/api/teams", response_model=TeamsListResponse)
async def list_teams(
    search: Optional[str] = Query(None, description="Search by school name or abbreviation"),
    conference: Optional[str] = Query(None, description="Filter by conference abbreviation"),
    predictable: bool = Query(False, description="Only return teams with prediction data (D1 teams with KenPom)"),
    limit: int = Query(100, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List all teams with optional search and conference filter.
    
    Use `predictable=true` to only get teams that can be used in the head-to-head matchup predictor.
    """
    def _get_teams():
        # Pre-fetch team IDs that have KenPom data
        kenpom_team_ids = set(
            KenPomRating.objects.values_list('team_id', flat=True).distinct()
        )
        
        qs = Team.objects.select_related('conference')
        
        # Filter to only predictable teams (D1 with KenPom data)
        if predictable:
            qs = qs.filter(id__in=kenpom_team_ids)
        
        if search:
            qs = qs.filter(
                Q(school__icontains=search) |
                Q(abbreviation__icontains=search) |
                Q(display_name__icontains=search)
            )
        
        if conference:
            qs = qs.filter(conference__abbreviation__iexact=conference)
        
        qs = qs.order_by('school')  # Alphabetical order
        
        total = qs.count()
        teams = list(qs[offset:offset + limit])
        
        return total, teams, kenpom_team_ids
    
    total, teams, kenpom_team_ids = await sync_to_async(_get_teams)()
    
    return TeamsListResponse(
        total=total,
        teams=[_serialize_team_list(team, kenpom_team_ids) for team in teams]
    )


@app.get("/api/teams/{team_id}", response_model=TeamDetailResponse)
async def get_team(team_id: int):
    """
    Get a specific team by ID.
    """
    def _get_team():
        return Team.objects.select_related('conference', 'venue').get(id=team_id)
    
    try:
        team = await sync_to_async(_get_team)()
    except Team.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    return _serialize_team_detail(team)


@app.get("/api/teams/{team_id}/games", response_model=GamesListResponse)
async def get_team_games(
    team_id: int,
    season: Optional[int] = Query(None, description="Filter by season year (defaults to current year)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by game status (scheduled, in_progress, final, etc.)"),
    past_only: bool = Query(False, description="Show only past games (before today)"),
    upcoming_only: bool = Query(False, description="Show only upcoming games (from today onwards)"),
    limit: int = Query(100, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get all games for a specific team (home or away).
    By default, shows all games for the current season.
    Use past_only=True to see completed games, or upcoming_only=True for future games.
    """
    from datetime import date
    
    def _get_team_games():
        # Verify team exists
        if not Team.objects.filter(id=team_id).exists():
            return None, None
        
        # Default to current year if season not specified
        current_year = date.today().year
        filter_season = season if season is not None else current_year
        
        qs = Game.objects.filter(
            Q(home_team_id=team_id) | Q(away_team_id=team_id),
            season=filter_season
        ).select_related('home_team', 'away_team', 'venue')
        
        # Filter by status if provided
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        # Filter by date if requested
        today = date.today()
        if past_only:
            qs = qs.filter(date__lt=today)
        elif upcoming_only:
            qs = qs.filter(date__gte=today)
        
        # Order by date (most recent first for past, earliest first for upcoming)
        if past_only:
            qs = qs.order_by('-date', '-time')
        else:
            qs = qs.order_by('date', 'time')
        
        total = qs.count()
        games = list(qs[offset:offset + limit])
        return total, games
    
    total, games = await sync_to_async(_get_team_games)()
    
    if total is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    return GamesListResponse(
        total=total,
        games=[_serialize_game(game) for game in games]
    )


@app.get("/api/teams/{team_id}/schedule", response_model=GamesListResponse)
async def get_team_schedule(
    team_id: int,
    season: Optional[int] = Query(None, description="Season year (defaults to current year)"),
    limit: int = Query(500, ge=1, le=1000, description="Number of results to return"),
):
    """
    Get complete schedule for a team - shows all games (past and upcoming) for the season.
    This is the main endpoint for viewing a team's full schedule.
    Games are ordered by date (past games first, then upcoming).
    """
    from datetime import date
    
    def _get_team_schedule():
        # Verify team exists
        if not Team.objects.filter(id=team_id).exists():
            return None, None
        
        # Default to current year if season not specified
        current_year = date.today().year
        filter_season = season if season is not None else current_year
        
        # Get all games for this team in this season
        qs = Game.objects.filter(
            Q(home_team_id=team_id) | Q(away_team_id=team_id),
            season=filter_season
        ).select_related('home_team', 'away_team', 'venue').order_by('date', 'time')
        
        total = qs.count()
        games = list(qs[:limit])
        return total, games
    
    total, games = await sync_to_async(_get_team_schedule)()
    
    if total is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    return GamesListResponse(
        total=total,
        games=[_serialize_game(game) for game in games]
    )


@app.get("/api/teams/{team_id}/stats", response_model=TeamStatsResponse)
async def get_team_stats(
    team_id: int,
    season: int = Query(2026, description="Season year"),
):
    """
    Get statistics for a specific team in a given season.
    Combines TeamStats (wins/losses) with KenPom data (efficiency metrics).
    """
    def _get_team_stats():
        team = Team.objects.filter(id=team_id).first()
        if not team:
            return None, None, None, "Team not found"
        
        # Get basic stats (wins/losses)
        stats = TeamStats.objects.filter(team_id=team_id, season=season).first()
        
        # Get KenPom data for efficiency metrics
        kenpom_rating = KenPomRating.objects.filter(team_id=team_id, season=season).first()
        kenpom_ff = KenPomFourFactors.objects.filter(team_id=team_id, season=season).first()
        
        # If no stats at all, check if we have KenPom data
        if not stats and not kenpom_rating:
            return None, None, None, f"No stats available for {team.school}"
        
        return team, stats, kenpom_rating, kenpom_ff
    
    team, stats, kenpom_rating, kenpom_ff = await sync_to_async(_get_team_stats)()
    
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team with ID {team_id} not found"
        )
    
    if stats is None and kenpom_rating is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=kenpom_ff or f"No stats available for team {team_id}"
        )
    
    # Build response combining all sources
    # Use TeamStats for wins/losses, KenPom for efficiency
    wins = stats.wins if stats else (kenpom_rating.wins if kenpom_rating else 0)
    losses = stats.losses if stats else (kenpom_rating.losses if kenpom_rating else 0)
    conf_wins = stats.conference_wins if stats else 0
    conf_losses = stats.conference_losses if stats else 0
    
    # Calculate PPG from KenPom efficiency
    ppg = None
    opp_ppg = None
    if kenpom_rating:
        ppg = round((kenpom_rating.adj_oe / 100) * kenpom_rating.adj_tempo, 1)
        opp_ppg = round((kenpom_rating.adj_de / 100) * kenpom_rating.adj_tempo, 1)
    
    # Get shooting percentages from Four Factors (eFG% is better than raw FG%)
    efg_pct = None
    if kenpom_ff:
        efg_pct = round(kenpom_ff.efg_pct, 1)
    
    total_games = wins + losses
    win_pct = wins / total_games if total_games > 0 else 0.0
    
    return {
        "id": stats.id if stats else 0,
        "team_id": team_id,
        "season": season,
        "wins": wins,
        "losses": losses,
        "conference_wins": conf_wins,
        "conference_losses": conf_losses,
        "points_per_game": ppg,
        "points_allowed_per_game": opp_ppg,
        "field_goal_pct": efg_pct,  # Using eFG% from KenPom (more accurate)
        "three_point_pct": None,  # Not available directly
        "free_throw_pct": kenpom_ff.ft_rate if kenpom_ff else None,  # FT Rate approximation
        "rebounds_per_game": None,
        "assists_per_game": None,
        "steals_per_game": None,
        "blocks_per_game": None,
        "turnovers_per_game": kenpom_ff.to_pct if kenpom_ff else None,  # TO%
        "record": f"{wins}-{losses}",
        "conference_record": f"{conf_wins}-{conf_losses}",
        "win_pct": round(win_pct, 3),
    }


@app.get("/api/games/today", response_model=GamesListResponse)
async def get_today_games():
    """
    Get all games scheduled for today (US Eastern time).
    """
    # Use US Eastern time since this is college basketball
    eastern = zoneinfo.ZoneInfo("America/New_York")
    today = datetime.now(eastern).date()
    
    def _get_today_games():
        qs = Game.objects.filter(date=today).select_related(
            'home_team', 'away_team', 'venue'
        ).order_by('time', 'home_team__school')
        
        games = list(qs)
        return len(games), games
    
    total, games = await sync_to_async(_get_today_games)()
    
    return GamesListResponse(
        total=total,
        games=[_serialize_game(game) for game in games]
    )


@app.get("/api/games/week", response_model=GamesListResponse)
async def get_week_games(
    start_date: Optional[date] = Query(None, description="Start date (defaults to today)"),
):
    """
    Get all games for the current week (7 days from start date, US Eastern time).
    """
    if start_date is None:
        # Use US Eastern time since this is college basketball
        eastern = zoneinfo.ZoneInfo("America/New_York")
        start_date = datetime.now(eastern).date()
    
    end_date = start_date + timedelta(days=6)
    
    def _get_week_games():
        qs = Game.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related(
            'home_team', 'away_team', 'venue'
        ).order_by('date', 'time', 'home_team__school')
        
        games = list(qs)
        return len(games), games
    
    total, games = await sync_to_async(_get_week_games)()
    
    return GamesListResponse(
        total=total,
        games=[_serialize_game(game) for game in games]
    )


@app.get("/api/games/{game_id}", response_model=GameResponse)
async def get_game(game_id: int):
    """
    Get a specific game by ID.
    """
    def _get_game():
        return Game.objects.select_related(
            'home_team', 'away_team', 'venue'
        ).get(id=game_id)
    
    try:
        game = await sync_to_async(_get_game)()
    except Game.DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )
    
    return _serialize_game(game)


@app.get("/api/conferences", response_model=List[ConferenceResponse])
async def list_conferences():
    """
    List all conferences.
    """
    def _get_conferences():
        return list(Conference.objects.all().order_by('name'))
    
    conferences = await sync_to_async(_get_conferences)()
    
    return [
        ConferenceResponse(
            id=c.id,
            name=c.name,
            abbreviation=c.abbreviation
        ) for c in conferences
    ]


# ============== User Favorites & Predictions Endpoints ==============

class FavoriteTeamRequest(BaseModel):
    """Request to add a favorite team."""
    team_id: int = Field(..., description="Team ID to add as favorite")


class PredictionRequest(BaseModel):
    """Request to create a matchup prediction."""
    game_id: int = Field(..., description="Game ID")
    predicted_winner_id: int = Field(..., description="Team ID of predicted winner")


class UpdatePredictionRequest(BaseModel):
    """Request to update a prediction (partial update)."""
    predicted_winner_id: int = Field(..., description="Team ID of predicted winner")


class PredictionResponse(BaseModel):
    """Prediction response schema."""
    id: int
    game_id: int
    predicted_winner_id: int
    predicted_winner: TeamListResponse
    game: GameResponse
    is_correct: Optional[bool] = None
    checked_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionStatsResponse(BaseModel):
    """User prediction statistics."""
    total_predictions: int
    correct_predictions: int
    incorrect_predictions: int
    pending_predictions: int
    win_percentage: float


@app.post("/api/users/me/favorites", status_code=status.HTTP_201_CREATED)
async def add_favorite_team(
    request: FavoriteTeamRequest,
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Add a team to user's favorites.
    Requires authentication.
    """
    def _add_favorite():
        # Verify team exists
        try:
            team = Team.objects.get(id=request.team_id)
        except Team.DoesNotExist:
            return None, "Team not found"
        
        # Check if already favorited
        favorite, created = FavoriteTeam.objects.get_or_create(
            user=current_user,
            team=team
        )
        
        if not created:
            return None, "Team already in favorites"
        
        return favorite, None
    
    favorite, error = await sync_to_async(_add_favorite)()
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if error == "Team already in favorites" else status.HTTP_404_NOT_FOUND,
            detail=error
        )
    
    return {
        "message": "Team added to favorites",
        "team": _serialize_team_list(favorite.team)
    }


@app.delete("/api/users/me/favorites/{team_id}", status_code=status.HTTP_200_OK)
async def remove_favorite_team(
    team_id: int,
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Remove a team from user's favorites.
    Requires authentication.
    """
    def _remove_favorite():
        try:
            favorite = FavoriteTeam.objects.get(user=current_user, team_id=team_id)
            favorite.delete()
            return True
        except FavoriteTeam.DoesNotExist:
            return False
    
    removed = await sync_to_async(_remove_favorite)()
    
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite team not found"
        )
    
    return {"message": "Team removed from favorites"}


@app.get("/api/users/me/favorites", response_model=TeamsListResponse)
async def get_favorite_teams(
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Get all favorite teams for the current user.
    Requires authentication.
    """
    def _get_favorites():
        favorites = FavoriteTeam.objects.filter(
            user=current_user
        ).select_related('team', 'team__conference').order_by('-created_at')
        teams = [fav.team for fav in favorites]
        
        # Pre-fetch team IDs that have KenPom data
        kenpom_team_ids = set(
            KenPomRating.objects.values_list('team_id', flat=True).distinct()
        )
        
        return len(teams), teams, kenpom_team_ids
    
    total, teams, kenpom_team_ids = await sync_to_async(_get_favorites)()
    
    return TeamsListResponse(
        total=total,
        teams=[_serialize_team_list(team, kenpom_team_ids) for team in teams]
    )


@app.post("/api/predictions", status_code=status.HTTP_201_CREATED, response_model=PredictionResponse)
async def create_prediction(
    request: PredictionRequest,
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Create a matchup prediction.
    Requires authentication.
    """
    def _create_prediction():
        # Verify game exists
        try:
            game = Game.objects.select_related('home_team', 'away_team', 'venue').get(id=request.game_id)
        except Game.DoesNotExist:
            return None, "Game not found"
        
        # Verify predicted winner is one of the teams in the game
        if request.predicted_winner_id not in [game.home_team_id, game.away_team_id]:
            return None, "Predicted winner must be one of the teams in the game"
        
        # Check if game is already final
        if game.is_final:
            return None, "Cannot predict on a game that is already final"
        
        # Get predicted winner team with conference loaded
        try:
            predicted_winner = Team.objects.select_related('conference').get(id=request.predicted_winner_id)
        except Team.DoesNotExist:
            return None, "Predicted winner team not found"
        
        # Create or update prediction
        prediction, created = MatchupPrediction.objects.update_or_create(
            user=current_user,
            game=game,
            defaults={'predicted_winner': predicted_winner}
        )
        
        # Fetch again with all relationships loaded
        prediction = MatchupPrediction.objects.select_related(
            'predicted_winner', 'predicted_winner__conference',
            'game', 'game__home_team', 'game__home_team__conference',
            'game__away_team', 'game__away_team__conference', 'game__venue'
        ).get(id=prediction.id)
        
        return prediction, None
    
    prediction, error = await sync_to_async(_create_prediction)()
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Serialize inside sync_to_async to avoid async context issues
    def _build_response():
        kenpom_team_ids = set(KenPomRating.objects.values_list('team_id', flat=True).distinct())
        return PredictionResponse(
            id=prediction.id,
            game_id=prediction.game_id,
            predicted_winner_id=prediction.predicted_winner_id,
            predicted_winner=_serialize_team_list(prediction.predicted_winner, kenpom_team_ids),
            game=_serialize_game(prediction.game),
            is_correct=prediction.is_correct,
            checked_at=prediction.checked_at,
            created_at=prediction.created_at
        )
    
    return await sync_to_async(_build_response)()


@app.get("/api/predictions/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(
    prediction_id: int,
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Get a specific prediction by ID.
    Users can only view their own predictions.
    Requires authentication.
    """
    def _get_prediction():
        try:
            prediction = MatchupPrediction.objects.select_related(
                'predicted_winner', 'predicted_winner__conference',
                'game', 'game__home_team', 'game__home_team__conference',
                'game__away_team', 'game__away_team__conference', 'game__venue'
            ).get(id=prediction_id, user=current_user)
            return prediction, None
        except MatchupPrediction.DoesNotExist:
            return None, "Prediction not found"
    
    prediction, error = await sync_to_async(_get_prediction)()
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error
        )
    
    def _build_response():
        kenpom_team_ids = set(KenPomRating.objects.values_list('team_id', flat=True).distinct())
        return PredictionResponse(
            id=prediction.id,
            game_id=prediction.game_id,
            predicted_winner_id=prediction.predicted_winner_id,
            predicted_winner=_serialize_team_list(prediction.predicted_winner, kenpom_team_ids),
            game=_serialize_game(prediction.game),
            is_correct=prediction.is_correct,
            checked_at=prediction.checked_at,
            created_at=prediction.created_at
        )
    
    return await sync_to_async(_build_response)()


@app.put("/api/predictions/{prediction_id}", response_model=PredictionResponse)
async def update_prediction(
    prediction_id: int,
    request: PredictionRequest,
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Update a prediction (change the predicted winner).
    Users can only update their own predictions.
    Cannot update predictions for games that are already final.
    Requires authentication.
    """
    def _update_prediction():
        # Get the prediction
        try:
            prediction = MatchupPrediction.objects.select_related('game').get(
                id=prediction_id,
                user=current_user
            )
        except MatchupPrediction.DoesNotExist:
            return None, "Prediction not found"
        
        # Check if game is already final
        if prediction.game.is_final:
            return None, "Cannot update prediction for a game that is already final"
        
        # Verify the new predicted winner is one of the teams in the game
        if request.predicted_winner_id not in [prediction.game.home_team_id, prediction.game.away_team_id]:
            return None, "Predicted winner must be one of the teams in the game"
        
        # Verify game_id matches
        if request.game_id != prediction.game_id:
            return None, "Game ID cannot be changed"
        
        # Get predicted winner team with conference loaded
        try:
            predicted_winner = Team.objects.select_related('conference').get(id=request.predicted_winner_id)
        except Team.DoesNotExist:
            return None, "Predicted winner team not found"
        
        # Update the prediction
        prediction.predicted_winner = predicted_winner
        prediction.save()
        
        # Fetch again with all relationships loaded
        prediction = MatchupPrediction.objects.select_related(
            'predicted_winner', 'predicted_winner__conference',
            'game', 'game__home_team', 'game__home_team__conference',
            'game__away_team', 'game__away_team__conference', 'game__venue'
        ).get(id=prediction.id)
        
        return prediction, None
    
    prediction, error = await sync_to_async(_update_prediction)()
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if "not found" not in error.lower() else status.HTTP_404_NOT_FOUND,
            detail=error
        )
    
    def _build_response():
        kenpom_team_ids = set(KenPomRating.objects.values_list('team_id', flat=True).distinct())
        return PredictionResponse(
            id=prediction.id,
            game_id=prediction.game_id,
            predicted_winner_id=prediction.predicted_winner_id,
            predicted_winner=_serialize_team_list(prediction.predicted_winner, kenpom_team_ids),
            game=_serialize_game(prediction.game),
            is_correct=prediction.is_correct,
            checked_at=prediction.checked_at,
            created_at=prediction.created_at
        )
    
    return await sync_to_async(_build_response)()


@app.patch("/api/predictions/{prediction_id}", response_model=PredictionResponse)
async def patch_prediction(
    prediction_id: int,
    request: UpdatePredictionRequest,
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Partially update a prediction (change only the predicted winner).
    Users can only update their own predictions.
    Cannot update predictions for games that are already final.
    Requires authentication.
    """
    def _patch_prediction():
        # Get the prediction
        try:
            prediction = MatchupPrediction.objects.select_related('game').get(
                id=prediction_id,
                user=current_user
            )
        except MatchupPrediction.DoesNotExist:
            return None, "Prediction not found"
        
        # Check if game is already final
        if prediction.game.is_final:
            return None, "Cannot update prediction for a game that is already final"
        
        # Verify the new predicted winner is one of the teams in the game
        if request.predicted_winner_id not in [prediction.game.home_team_id, prediction.game.away_team_id]:
            return None, "Predicted winner must be one of the teams in the game"
        
        # Get predicted winner team with conference loaded
        try:
            predicted_winner = Team.objects.select_related('conference').get(id=request.predicted_winner_id)
        except Team.DoesNotExist:
            return None, "Predicted winner team not found"
        
        # Update the prediction
        prediction.predicted_winner = predicted_winner
        prediction.save()
        
        # Fetch again with all relationships loaded
        prediction = MatchupPrediction.objects.select_related(
            'predicted_winner', 'predicted_winner__conference',
            'game', 'game__home_team', 'game__home_team__conference',
            'game__away_team', 'game__away_team__conference', 'game__venue'
        ).get(id=prediction.id)
        
        return prediction, None
    
    prediction, error = await sync_to_async(_patch_prediction)()
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if "not found" not in error.lower() else status.HTTP_404_NOT_FOUND,
            detail=error
        )
    
    def _build_response():
        kenpom_team_ids = set(KenPomRating.objects.values_list('team_id', flat=True).distinct())
        return PredictionResponse(
            id=prediction.id,
            game_id=prediction.game_id,
            predicted_winner_id=prediction.predicted_winner_id,
            predicted_winner=_serialize_team_list(prediction.predicted_winner, kenpom_team_ids),
            game=_serialize_game(prediction.game),
            is_correct=prediction.is_correct,
            checked_at=prediction.checked_at,
            created_at=prediction.created_at
        )
    
    return await sync_to_async(_build_response)()


@app.delete("/api/predictions/{prediction_id}", status_code=status.HTTP_200_OK)
async def delete_prediction(
    prediction_id: int,
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Delete a prediction.
    Users can only delete their own predictions.
    Requires authentication.
    """
    def _delete_prediction():
        try:
            prediction = MatchupPrediction.objects.get(id=prediction_id, user=current_user)
            prediction.delete()
            return True
        except MatchupPrediction.DoesNotExist:
            return False
    
    deleted = await sync_to_async(_delete_prediction)()
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    
    return {"message": "Prediction deleted successfully"}


@app.get("/api/users/me/predictions", response_model=List[PredictionResponse])
async def get_user_predictions(
    season: Optional[int] = Query(None, description="Filter by season year"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by prediction status: correct, incorrect, pending"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Get all predictions for the current user.
    Requires authentication.
    """
    def _get_predictions():
        qs = MatchupPrediction.objects.filter(
            user=current_user
        ).select_related(
            'game', 'game__home_team', 'game__away_team', 'game__venue',
            'predicted_winner', 'predicted_winner__conference'
        ).order_by('-created_at')
        
        if season:
            qs = qs.filter(game__season=season)
        
        if status_filter == "correct":
            qs = qs.filter(is_correct=True)
        elif status_filter == "incorrect":
            qs = qs.filter(is_correct=False)
        elif status_filter == "pending":
            qs = qs.filter(is_correct__isnull=True)
        
        total = qs.count()
        predictions = list(qs[offset:offset + limit])
        return total, predictions
    
    total, predictions = await sync_to_async(_get_predictions)()
    
    def _build_response_list():
        kenpom_team_ids = set(KenPomRating.objects.values_list('team_id', flat=True).distinct())
        return [
            PredictionResponse(
                id=p.id,
                game_id=p.game_id,
                predicted_winner_id=p.predicted_winner_id,
                predicted_winner=_serialize_team_list(p.predicted_winner, kenpom_team_ids),
                game=_serialize_game(p.game),
                is_correct=p.is_correct,
                checked_at=p.checked_at,
                created_at=p.created_at
            ) for p in predictions
        ]
    
    return await sync_to_async(_build_response_list)()


@app.get("/api/users/me/prediction-stats", response_model=PredictionStatsResponse)
async def get_prediction_stats(
    season: Optional[int] = Query(None, description="Filter by season year"),
    current_user: SupabaseUser = Depends(require_auth)
):
    """
    Get prediction statistics for the current user.
    Requires authentication.
    """
    def _get_stats():
        qs = MatchupPrediction.objects.filter(user=current_user)
        
        if season:
            qs = qs.filter(game__season=season)
        
        total = qs.count()
        correct = qs.filter(is_correct=True).count()
        incorrect = qs.filter(is_correct=False).count()
        pending = qs.filter(is_correct__isnull=True).count()
        
        # Calculate win percentage (only for checked predictions)
        checked = correct + incorrect
        win_pct = (correct / checked * 100) if checked > 0 else 0.0
        
        return {
            "total_predictions": total,
            "correct_predictions": correct,
            "incorrect_predictions": incorrect,
            "pending_predictions": pending,
            "win_percentage": round(win_pct, 2)
        }
    
    stats = await sync_to_async(_get_stats)()
    
    return PredictionStatsResponse(**stats)


# ============== KenPom Pydantic Models ==============

class KenPomTeamResponse(BaseModel):
    """KenPom team mapping response."""
    id: int
    team_id: int
    team_school: str
    kenpom_team_id: int
    kenpom_team_name: str
    matched_at: datetime
    last_verified: datetime

    class Config:
        from_attributes = True


class KenPomRatingResponse(BaseModel):
    """KenPom rating response."""
    id: int
    team_id: int
    team_school: str
    season: int
    data_through: str
    wins: int
    losses: int
    
    # Core ratings
    adj_em: float
    rank_adj_em: int
    pythag: float
    rank_pythag: int
    
    # Offense
    adj_oe: float
    rank_adj_oe: int
    oe: float
    rank_oe: int
    
    # Defense
    adj_de: float
    rank_adj_de: int
    de: float
    rank_de: int
    
    # Tempo
    tempo: float
    rank_tempo: int
    adj_tempo: float
    rank_adj_tempo: int
    
    # Advanced
    luck: float
    rank_luck: int
    sos: float
    rank_sos: int
    
    # Optional fields
    seed: Optional[int] = None
    coach: Optional[str] = None
    event: Optional[str] = None

    class Config:
        from_attributes = True


class KenPomFourFactorsResponse(BaseModel):
    """KenPom Four Factors response."""
    id: int
    team_id: int
    team_school: str
    season: int
    is_conference_only: bool
    data_through: str
    
    # Offensive Four Factors
    efg_pct: float
    rank_efg_pct: int
    to_pct: float
    rank_to_pct: int
    or_pct: float
    rank_or_pct: int
    ft_rate: float
    rank_ft_rate: int
    
    # Defensive Four Factors
    defg_pct: float
    rank_defg_pct: int
    dto_pct: float
    rank_dto_pct: int
    dor_pct: float
    rank_dor_pct: int
    dft_rate: float
    rank_dft_rate: int

    class Config:
        from_attributes = True


class KenPomFanMatchResponse(BaseModel):
    """KenPom FanMatch prediction response."""
    id: int
    kenpom_game_id: int
    season: int
    date: date
    
    home_team_id: int
    home_team_school: str
    away_team_id: int
    away_team_school: str
    
    home_rank: int
    away_rank: int
    home_predicted_score: float
    away_predicted_score: float
    home_win_probability: float
    predicted_tempo: float
    thrill_score: float
    
    # Computed fields
    predicted_winner: str
    predicted_margin: float
    
    # Link to our game (if available)
    game_id: Optional[int] = None

    class Config:
        from_attributes = True


class KenPomMatchupAnalysis(BaseModel):
    """Matchup analysis combining KenPom data for two teams."""
    home_team: dict
    away_team: dict
    
    # Efficiency differential
    adj_em_diff: float  # Positive = home favored
    
    # Four Factors matchups (offense vs defense)
    efg_mismatch: float  # Home eFG% vs Away Def eFG%
    to_mismatch: float   # Away TO forced vs Home TO%
    or_mismatch: float   # Home OR% vs Away DOR%
    ftr_mismatch: float  # Home FT Rate vs Away DFT Rate
    
    # Predicted outcome
    predicted_winner: str
    win_probability: float
    predicted_margin: float
    predicted_tempo: float


# ============== KenPom API Endpoints ==============

@app.get("/api/kenpom/ratings", response_model=List[KenPomRatingResponse])
async def get_kenpom_ratings(
    season: int = Query(..., description="Season year (e.g., 2025)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get KenPom ratings for a season.
    Returns teams sorted by rank.
    """
    def _get_ratings():
        qs = KenPomRating.objects.filter(season=season).select_related('team').order_by('rank_adj_em')
        total = qs.count()
        ratings = list(qs[offset:offset + limit])
        
        result = []
        for r in ratings:
            result.append({
                "id": r.id,
                "team_id": r.team.id,
                "team_school": r.team.school,
                "season": r.season,
                "data_through": r.data_through,
                "wins": r.wins,
                "losses": r.losses,
                "adj_em": r.adj_em,
                "rank_adj_em": r.rank_adj_em,
                "pythag": r.pythag,
                "rank_pythag": r.rank_pythag,
                "adj_oe": r.adj_oe,
                "rank_adj_oe": r.rank_adj_oe,
                "oe": r.oe,
                "rank_oe": r.rank_oe,
                "adj_de": r.adj_de,
                "rank_adj_de": r.rank_adj_de,
                "de": r.de,
                "rank_de": r.rank_de,
                "tempo": r.tempo,
                "rank_tempo": r.rank_tempo,
                "adj_tempo": r.adj_tempo,
                "rank_adj_tempo": r.rank_adj_tempo,
                "luck": r.luck,
                "rank_luck": r.rank_luck,
                "sos": r.sos,
                "rank_sos": r.rank_sos,
                "seed": r.seed,
                "coach": r.coach,
                "event": r.event,
            })
        return result
    
    return await sync_to_async(_get_ratings)()


@app.get("/api/kenpom/ratings/{team_id}", response_model=KenPomRatingResponse)
async def get_kenpom_rating_for_team(
    team_id: int,
    season: Optional[int] = Query(None, description="Season year (defaults to most recent)")
):
    """
    Get KenPom rating for a specific team.
    """
    def _get_rating():
        qs = KenPomRating.objects.filter(team_id=team_id).select_related('team')
        if season:
            qs = qs.filter(season=season)
        else:
            qs = qs.order_by('-season')
        
        rating = qs.first()
        if not rating:
            return None
        
        return {
            "id": rating.id,
            "team_id": rating.team.id,
            "team_school": rating.team.school,
            "season": rating.season,
            "data_through": rating.data_through,
            "wins": rating.wins,
            "losses": rating.losses,
            "adj_em": rating.adj_em,
            "rank_adj_em": rating.rank_adj_em,
            "pythag": rating.pythag,
            "rank_pythag": rating.rank_pythag,
            "adj_oe": rating.adj_oe,
            "rank_adj_oe": rating.rank_adj_oe,
            "oe": rating.oe,
            "rank_oe": rating.rank_oe,
            "adj_de": rating.adj_de,
            "rank_adj_de": rating.rank_adj_de,
            "de": rating.de,
            "rank_de": rating.rank_de,
            "tempo": rating.tempo,
            "rank_tempo": rating.rank_tempo,
            "adj_tempo": rating.adj_tempo,
            "rank_adj_tempo": rating.rank_adj_tempo,
            "luck": rating.luck,
            "rank_luck": rating.rank_luck,
            "sos": rating.sos,
            "rank_sos": rating.rank_sos,
            "seed": rating.seed,
            "coach": rating.coach,
            "event": rating.event,
        }
    
    result = await sync_to_async(_get_rating)()
    if not result:
        raise HTTPException(status_code=404, detail="KenPom rating not found for this team")
    
    return result


@app.get("/api/kenpom/four-factors/{team_id}", response_model=KenPomFourFactorsResponse)
async def get_kenpom_four_factors(
    team_id: int,
    season: Optional[int] = Query(None, description="Season year"),
    conference_only: bool = Query(False, description="Get conference-only stats")
):
    """
    Get KenPom Four Factors for a specific team.
    """
    def _get_ff():
        qs = KenPomFourFactors.objects.filter(
            team_id=team_id,
            is_conference_only=conference_only
        ).select_related('team')
        
        if season:
            qs = qs.filter(season=season)
        else:
            qs = qs.order_by('-season')
        
        ff = qs.first()
        if not ff:
            return None
        
        return {
            "id": ff.id,
            "team_id": ff.team.id,
            "team_school": ff.team.school,
            "season": ff.season,
            "is_conference_only": ff.is_conference_only,
            "data_through": ff.data_through,
            "efg_pct": ff.efg_pct,
            "rank_efg_pct": ff.rank_efg_pct,
            "to_pct": ff.to_pct,
            "rank_to_pct": ff.rank_to_pct,
            "or_pct": ff.or_pct,
            "rank_or_pct": ff.rank_or_pct,
            "ft_rate": ff.ft_rate,
            "rank_ft_rate": ff.rank_ft_rate,
            "defg_pct": ff.defg_pct,
            "rank_defg_pct": ff.rank_defg_pct,
            "dto_pct": ff.dto_pct,
            "rank_dto_pct": ff.rank_dto_pct,
            "dor_pct": ff.dor_pct,
            "rank_dor_pct": ff.rank_dor_pct,
            "dft_rate": ff.dft_rate,
            "rank_dft_rate": ff.rank_dft_rate,
        }
    
    result = await sync_to_async(_get_ff)()
    if not result:
        raise HTTPException(status_code=404, detail="KenPom Four Factors not found for this team")
    
    return result


@app.get("/api/kenpom/predictions", response_model=List[KenPomFanMatchResponse])
async def get_kenpom_predictions(
    date_str: str = Query(..., alias="date", description="Date in YYYY-MM-DD format"),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get KenPom FanMatch predictions for a specific date.
    """
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    def _get_predictions():
        qs = KenPomFanMatch.objects.filter(date=target_date).select_related(
            'home_team', 'away_team', 'game'
        ).order_by('-thrill_score')[:limit]
        
        result = []
        for p in qs:
            result.append({
                "id": p.id,
                "kenpom_game_id": p.kenpom_game_id,
                "season": p.season,
                "date": p.date,
                "home_team_id": p.home_team.id,
                "home_team_school": p.home_team.school,
                "away_team_id": p.away_team.id,
                "away_team_school": p.away_team.school,
                "home_rank": p.home_rank,
                "away_rank": p.away_rank,
                "home_predicted_score": p.home_predicted_score,
                "away_predicted_score": p.away_predicted_score,
                "home_win_probability": p.home_win_probability,
                "predicted_tempo": p.predicted_tempo,
                "thrill_score": p.thrill_score,
                "predicted_winner": p.home_team.school if p.home_win_probability > 0.5 else p.away_team.school,
                "predicted_margin": round(p.home_predicted_score - p.away_predicted_score, 1),
                "game_id": p.game.id if p.game else None,
            })
        return result
    
    return await sync_to_async(_get_predictions)()


@app.get("/api/kenpom/predictions/{game_id}", response_model=KenPomFanMatchResponse)
async def get_kenpom_prediction_for_game(game_id: int):
    """
    Get KenPom FanMatch prediction for a specific game.
    """
    def _get_prediction():
        # Try to find by linked game first
        p = KenPomFanMatch.objects.filter(game_id=game_id).select_related(
            'home_team', 'away_team', 'game'
        ).first()
        
        if not p:
            # Try to find by matching teams and date
            game = Game.objects.filter(id=game_id).first()
            if game:
                p = KenPomFanMatch.objects.filter(
                    home_team=game.home_team,
                    away_team=game.away_team,
                    date=game.date
                ).select_related('home_team', 'away_team', 'game').first()
                
                if not p:
                    # Try reverse
                    p = KenPomFanMatch.objects.filter(
                        home_team=game.away_team,
                        away_team=game.home_team,
                        date=game.date
                    ).select_related('home_team', 'away_team', 'game').first()
        
        if not p:
            return None
        
        return {
            "id": p.id,
            "kenpom_game_id": p.kenpom_game_id,
            "season": p.season,
            "date": p.date,
            "home_team_id": p.home_team.id,
            "home_team_school": p.home_team.school,
            "away_team_id": p.away_team.id,
            "away_team_school": p.away_team.school,
            "home_rank": p.home_rank,
            "away_rank": p.away_rank,
            "home_predicted_score": p.home_predicted_score,
            "away_predicted_score": p.away_predicted_score,
            "home_win_probability": p.home_win_probability,
            "predicted_tempo": p.predicted_tempo,
            "thrill_score": p.thrill_score,
            "predicted_winner": p.home_team.school if p.home_win_probability > 0.5 else p.away_team.school,
            "predicted_margin": round(p.home_predicted_score - p.away_predicted_score, 1),
            "game_id": p.game.id if p.game else None,
        }
    
    result = await sync_to_async(_get_prediction)()
    if not result:
        raise HTTPException(status_code=404, detail="KenPom prediction not found for this game")
    
    return result


@app.get("/api/kenpom/matchup/{home_team_id}/{away_team_id}", response_model=KenPomMatchupAnalysis)
async def get_kenpom_matchup_analysis(
    home_team_id: int,
    away_team_id: int,
    season: Optional[int] = Query(None, description="Season year")
):
    """
    Get matchup analysis combining KenPom data for two teams.
    Calculates efficiency differentials and Four Factors mismatches.
    """
    def _get_matchup():
        # Get ratings for both teams
        home_rating = KenPomRating.objects.filter(team_id=home_team_id)
        away_rating = KenPomRating.objects.filter(team_id=away_team_id)
        
        if season:
            home_rating = home_rating.filter(season=season)
            away_rating = away_rating.filter(season=season)
        else:
            home_rating = home_rating.order_by('-season')
            away_rating = away_rating.order_by('-season')
        
        home_rating = home_rating.select_related('team').first()
        away_rating = away_rating.select_related('team').first()
        
        if not home_rating or not away_rating:
            return None
        
        # Get Four Factors for both teams
        ff_season = season or home_rating.season
        home_ff = KenPomFourFactors.objects.filter(
            team_id=home_team_id, season=ff_season, is_conference_only=False
        ).first()
        away_ff = KenPomFourFactors.objects.filter(
            team_id=away_team_id, season=ff_season, is_conference_only=False
        ).first()
        
        # Calculate efficiency differential (positive = home favored)
        adj_em_diff = home_rating.adj_em - away_rating.adj_em
        
        # Add home court advantage (~3.5 points)
        hca = 3.5
        adj_em_with_hca = adj_em_diff + hca
        
        # Calculate win probability using log5 formula
        # P(home wins) = 1 / (1 + 10^(-adj_em_with_hca / 11))
        import math
        win_prob = 1 / (1 + math.pow(10, -adj_em_with_hca / 11))
        
        # Predicted tempo (average of both teams' tempos)
        predicted_tempo = (home_rating.adj_tempo + away_rating.adj_tempo) / 2
        
        # Predicted margin
        predicted_margin = adj_em_with_hca * (predicted_tempo / 100)
        
        # Four Factors mismatches (if available)
        efg_mismatch = 0.0
        to_mismatch = 0.0
        or_mismatch = 0.0
        ftr_mismatch = 0.0
        
        if home_ff and away_ff:
            # Home offense vs Away defense
            efg_mismatch = home_ff.efg_pct - away_ff.defg_pct
            to_mismatch = away_ff.dto_pct - home_ff.to_pct  # Higher = home advantage
            or_mismatch = home_ff.or_pct - (100 - away_ff.dor_pct)
            ftr_mismatch = home_ff.ft_rate - away_ff.dft_rate
        
        return {
            "home_team": {
                "id": home_rating.team.id,
                "school": home_rating.team.school,
                "adj_em": home_rating.adj_em,
                "rank": home_rating.rank_adj_em,
                "adj_oe": home_rating.adj_oe,
                "adj_de": home_rating.adj_de,
                "adj_tempo": home_rating.adj_tempo,
            },
            "away_team": {
                "id": away_rating.team.id,
                "school": away_rating.team.school,
                "adj_em": away_rating.adj_em,
                "rank": away_rating.rank_adj_em,
                "adj_oe": away_rating.adj_oe,
                "adj_de": away_rating.adj_de,
                "adj_tempo": away_rating.adj_tempo,
            },
            "adj_em_diff": round(adj_em_with_hca, 2),
            "efg_mismatch": round(efg_mismatch, 2),
            "to_mismatch": round(to_mismatch, 2),
            "or_mismatch": round(or_mismatch, 2),
            "ftr_mismatch": round(ftr_mismatch, 2),
            "predicted_winner": home_rating.team.school if win_prob > 0.5 else away_rating.team.school,
            "win_probability": round(win_prob, 4),
            "predicted_margin": round(predicted_margin, 1),
            "predicted_tempo": round(predicted_tempo, 1),
        }
    
    result = await sync_to_async(_get_matchup)()
    if not result:
        raise HTTPException(status_code=404, detail="KenPom data not found for one or both teams")
    
    return result


@app.get("/api/kenpom/history/{team_id}")
async def get_kenpom_history(
    team_id: int,
    season: Optional[int] = Query(None, description="Season year"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get historical KenPom ratings for a team.
    Returns archived point-in-time ratings.
    """
    def _get_history():
        qs = KenPomRatingArchive.objects.filter(team_id=team_id).select_related('team')
        
        if season:
            qs = qs.filter(season=season)
        
        qs = qs.order_by('-archive_date')[:limit]
        
        result = []
        for a in qs:
            result.append({
                "id": a.id,
                "team_id": a.team.id,
                "team_school": a.team.school,
                "season": a.season,
                "archive_date": a.archive_date,
                "is_preseason": a.is_preseason,
                "adj_em": a.adj_em,
                "rank_adj_em": a.rank_adj_em,
                "adj_oe": a.adj_oe,
                "rank_adj_oe": a.rank_adj_oe,
                "adj_de": a.adj_de,
                "rank_adj_de": a.rank_adj_de,
                "adj_tempo": a.adj_tempo,
                "rank_adj_tempo": a.rank_adj_tempo,
                "adj_em_final": a.adj_em_final,
                "rank_change": a.rank_change,
                "adj_em_change": a.adj_em_change,
            })
        return result
    
    return await sync_to_async(_get_history)()


# ============== ML Prediction Pydantic Models ==============

class MLPredictionResponse(BaseModel):
    """ML prediction response."""
    id: int
    game_id: int
    home_team_id: int
    home_team_school: str
    away_team_id: int
    away_team_school: str
    game_date: date
    
    # Predictions
    home_win_probability: float
    predicted_home_score: float
    predicted_away_score: float
    predicted_margin: float
    confidence_score: float
    
    # Predicted winner
    predicted_winner: str
    predicted_winner_id: int
    
    # Model info
    model_version: str
    predicted_at: datetime
    
    # Key features (optional)
    home_adj_em: Optional[float] = None
    away_adj_em: Optional[float] = None
    home_momentum: Optional[float] = None
    away_momentum: Optional[float] = None
    venue_hca: Optional[float] = None

    class Config:
        from_attributes = True


class MLModelInfoResponse(BaseModel):
    """ML model info response."""
    version: str
    is_active: bool
    training_date: datetime
    training_games_count: int
    test_accuracy: float
    test_log_loss: float
    feature_count: int
    top_features: List[str]


class MLMatchupPredictionResponse(BaseModel):
    """ML matchup prediction response (for hypothetical matchups)."""
    home_team_id: int
    home_team_school: str
    away_team_id: int
    away_team_school: str
    
    home_win_probability: float
    predicted_home_score: float
    predicted_away_score: float
    predicted_margin: float
    confidence_score: float
    
    predicted_winner: str
    model_version: str
    
    # Key features
    features: Dict[str, Any]


# ============== ML Prediction API Endpoints ==============

@app.get("/api/ml/predictions/{game_id}", response_model=MLPredictionResponse)
async def get_ml_prediction(game_id: int):
    """
    Get ML prediction for a specific game.
    """
    def _get_prediction():
        pred = MLPrediction.objects.filter(game_id=game_id).select_related(
            'game', 'game__home_team', 'game__away_team'
        ).first()
        
        if not pred:
            return None
        
        # Determine predicted winner
        if pred.home_win_probability > 0.5:
            winner = pred.game.home_team
        else:
            winner = pred.game.away_team
        
        return {
            "id": pred.id,
            "game_id": pred.game.id,
            "home_team_id": pred.game.home_team.id,
            "home_team_school": pred.game.home_team.school,
            "away_team_id": pred.game.away_team.id,
            "away_team_school": pred.game.away_team.school,
            "game_date": pred.game.date,
            "home_win_probability": pred.home_win_probability,
            "predicted_home_score": pred.predicted_home_score,
            "predicted_away_score": pred.predicted_away_score,
            "predicted_margin": pred.predicted_margin,
            "confidence_score": pred.confidence_score,
            "predicted_winner": winner.school,
            "predicted_winner_id": winner.id,
            "model_version": pred.model_version,
            "predicted_at": pred.predicted_at,
            "home_adj_em": pred.home_adj_em,
            "away_adj_em": pred.away_adj_em,
            "home_momentum": pred.home_momentum,
            "away_momentum": pred.away_momentum,
            "venue_hca": pred.venue_hca,
        }
    
    result = await sync_to_async(_get_prediction)()
    if not result:
        raise HTTPException(status_code=404, detail="ML prediction not found for this game")
    
    return result


@app.get("/api/ml/predictions", response_model=List[MLPredictionResponse])
async def get_ml_predictions(
    date_str: Optional[str] = Query(None, alias="date", description="Filter by date (YYYY-MM-DD)"),
    team_id: Optional[int] = Query(None, description="Filter by team ID"),
    season: Optional[int] = Query(None, description="Filter by season"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get ML predictions with optional filters.
    """
    def _get_predictions():
        qs = MLPrediction.objects.select_related(
            'game', 'game__home_team', 'game__away_team'
        )
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                qs = qs.filter(game__date=target_date)
            except ValueError:
                pass
        
        if team_id:
            qs = qs.filter(
                Q(game__home_team_id=team_id) | Q(game__away_team_id=team_id)
            )
        
        if season:
            qs = qs.filter(game__season=season)
        
        qs = qs.order_by('-game__date', '-predicted_at')[offset:offset + limit]
        
        result = []
        for pred in qs:
            if pred.home_win_probability > 0.5:
                winner = pred.game.home_team
            else:
                winner = pred.game.away_team
            
            result.append({
                "id": pred.id,
                "game_id": pred.game.id,
                "home_team_id": pred.game.home_team.id,
                "home_team_school": pred.game.home_team.school,
                "away_team_id": pred.game.away_team.id,
                "away_team_school": pred.game.away_team.school,
                "game_date": pred.game.date,
                "home_win_probability": pred.home_win_probability,
                "predicted_home_score": pred.predicted_home_score,
                "predicted_away_score": pred.predicted_away_score,
                "predicted_margin": pred.predicted_margin,
                "confidence_score": pred.confidence_score,
                "predicted_winner": winner.school,
                "predicted_winner_id": winner.id,
                "model_version": pred.model_version,
                "predicted_at": pred.predicted_at,
                "home_adj_em": pred.home_adj_em,
                "away_adj_em": pred.away_adj_em,
                "home_momentum": pred.home_momentum,
                "away_momentum": pred.away_momentum,
                "venue_hca": pred.venue_hca,
            })
        
        return result
    
    return await sync_to_async(_get_predictions)()


@app.get("/api/ml/matchup/{home_team_id}/{away_team_id}", response_model=MLMatchupPredictionResponse)
async def get_ml_matchup_prediction(
    home_team_id: int,
    away_team_id: int,
    season: Optional[int] = Query(None, description="Season year")
):
    """
    Get ML prediction for a hypothetical matchup.
    Uses current KenPom ratings to predict outcome.
    Falls back to KenPom-only prediction if no ML model is trained.
    """
    def _get_matchup():
        home_team = Team.objects.filter(id=home_team_id).first()
        away_team = Team.objects.filter(id=away_team_id).first()
        
        if not home_team:
            return None, f"Home team with ID {home_team_id} not found"
        if not away_team:
            return None, f"Away team with ID {away_team_id} not found"
        
        # Check if ML model exists
        active_model = MLModelVersion.objects.filter(is_active=True).first()
        
        if active_model:
            # Use ML model
            try:
                from basketball.ml_model import get_predictor
                predictor = get_predictor()
                predictor.load_model()
                
                prediction = predictor.predict_matchup(home_team, away_team, season)
                
                if prediction['home_win_probability'] > 0.5:
                    winner = home_team.school
                else:
                    winner = away_team.school
                
                return {
                    "home_team_id": home_team.id,
                    "home_team_school": home_team.school,
                    "away_team_id": away_team.id,
                    "away_team_school": away_team.school,
                    "home_win_probability": prediction['home_win_probability'],
                    "predicted_home_score": prediction['predicted_home_score'],
                    "predicted_away_score": prediction['predicted_away_score'],
                    "predicted_margin": prediction['predicted_margin'],
                    "confidence_score": prediction['confidence_score'],
                    "predicted_winner": winner,
                    "model_version": prediction['model_version'],
                    "features": prediction['features'],
                }, None
                
            except Exception as e:
                return None, f"ML model error: {str(e)}"
        else:
            # Fallback: Use KenPom data for simple prediction
            from basketball.ml_features import get_feature_extractor
            import math
            
            current_season = season or 2026
            
            home_rating = KenPomRating.objects.filter(team=home_team, season=current_season).first()
            away_rating = KenPomRating.objects.filter(team=away_team, season=current_season).first()
            
            if not home_rating or not away_rating:
                missing_teams = []
                if not home_rating:
                    missing_teams.append(f"{home_team.school} (ID: {home_team.id})")
                if not away_rating:
                    missing_teams.append(f"{away_team.school} (ID: {away_team.id})")
                return None, f"Prediction unavailable - no KenPom data for: {', '.join(missing_teams)}. These may be non-D1 teams (NAIA/D2/D3)."
            
            # KenPom-style prediction
            hca = 3.5  # Home court advantage in points
            
            # Step 1: Expected game tempo (possessions per team)
            avg_tempo = (home_rating.adj_tempo + away_rating.adj_tempo) / 2
            
            # Step 2: Expected offensive efficiency for each team IN THIS MATCHUP
            # Formula: (Team_AdjOE × Opponent_AdjDE) / 100
            # This properly combines how good an offense is vs how bad a defense is
            home_exp_oe = (home_rating.adj_oe * away_rating.adj_de) / 100
            away_exp_oe = (away_rating.adj_oe * home_rating.adj_de) / 100
            
            # Step 3: Projected scores = Expected OE × Tempo / 100
            home_score_raw = home_exp_oe * avg_tempo / 100
            away_score_raw = away_exp_oe * avg_tempo / 100
            
            # Step 4: Apply home court advantage (split between teams)
            home_score = home_score_raw + (hca / 2)
            away_score = away_score_raw - (hca / 2)
            
            # Step 5: Win probability using Log5 formula on AdjEM difference
            adj_em_diff = home_rating.adj_em - away_rating.adj_em + hca
            home_win_prob = 1 / (1 + math.pow(10, -adj_em_diff / 11))
            
            if home_win_prob > 0.5:
                winner = home_team.school
            else:
                winner = away_team.school
            
            return {
                "home_team_id": home_team.id,
                "home_team_school": home_team.school,
                "away_team_id": away_team.id,
                "away_team_school": away_team.school,
                "home_win_probability": round(home_win_prob, 4),
                "predicted_home_score": round(home_score, 1),
                "predicted_away_score": round(away_score, 1),
                "predicted_margin": round(home_score - away_score, 1),
                "confidence_score": round(abs(home_win_prob - 0.5) * 2, 4),
                "predicted_winner": winner,
                "model_version": "kenpom_fallback",
                "features": {
                    "home_adj_em": home_rating.adj_em,
                    "away_adj_em": away_rating.adj_em,
                    "adj_em_diff": round(adj_em_diff, 2),
                    "home_adj_oe": home_rating.adj_oe,
                    "away_adj_oe": away_rating.adj_oe,
                    "home_adj_de": home_rating.adj_de,
                    "away_adj_de": away_rating.adj_de,
                    "home_rank": home_rating.rank_adj_em,
                    "away_rank": away_rating.rank_adj_em,
                    "home_court_advantage": hca,
                    "note": "Using KenPom fallback - no ML model trained yet"
                },
            }, None
    
    result, error = await sync_to_async(_get_matchup)()
    
    if error:
        if "not found" in error:
            raise HTTPException(status_code=404, detail=error)
        if "KenPom ratings not available" in error:
            raise HTTPException(status_code=400, detail=error)
        raise HTTPException(status_code=500, detail=f"Prediction error: {error}")
    
    return result


@app.get("/api/ml/model/info", response_model=MLModelInfoResponse)
async def get_ml_model_info():
    """
    Get information about the active ML model.
    """
    def _get_info():
        model = MLModelVersion.objects.filter(is_active=True).first()
        
        if not model:
            return None
        
        # Get top features (first 10)
        feature_list = model.feature_list or []
        top_features = feature_list[:10] if len(feature_list) > 10 else feature_list
        
        return {
            "version": model.version,
            "is_active": model.is_active,
            "training_date": model.training_date,
            "training_games_count": model.training_games_count,
            "test_accuracy": model.test_accuracy,
            "test_log_loss": model.test_log_loss,
            "feature_count": len(feature_list),
            "top_features": top_features,
        }
    
    result = await sync_to_async(_get_info)()
    
    if not result:
        raise HTTPException(status_code=404, detail="No active ML model found")
    
    return result


@app.get("/api/ml/features/{game_id}")
async def get_ml_features(game_id: int):
    """
    Get feature values used for a game's prediction.
    Useful for debugging and analysis.
    """
    def _get_features():
        pred = MLPrediction.objects.filter(game_id=game_id).first()
        
        if not pred:
            return None
        
        return {
            "game_id": game_id,
            "model_version": pred.model_version,
            "features_hash": pred.model_features_hash,
            "features": pred.features_json or {},
            "predicted_at": pred.predicted_at,
        }
    
    result = await sync_to_async(_get_features)()
    
    if not result:
        raise HTTPException(status_code=404, detail="ML prediction not found for this game")
    
    return result


@app.get("/api/ml/model/versions")
async def get_ml_model_versions(
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get list of all ML model versions.
    """
    def _get_versions():
        versions = MLModelVersion.objects.order_by('-training_date')[:limit]
        
        result = []
        for v in versions:
            result.append({
                "version": v.version,
                "is_active": v.is_active,
                "training_date": v.training_date,
                "training_games_count": v.training_games_count,
                "test_accuracy": v.test_accuracy,
                "test_log_loss": v.test_log_loss,
                "feature_count": len(v.feature_list or []),
            })
        
        return result
    
    return await sync_to_async(_get_versions)()


# ============== Injury & Player Endpoints ==============

@app.get("/api/teams/{team_id}/injuries")
async def get_team_injuries(
    team_id: int,
    active_only: bool = Query(True, description="Only return active injuries"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get injuries for a specific team.
    """
    from basketball.models import InjuryReport, Player
    
    def _get_injuries():
        team = Team.objects.filter(id=team_id).first()
        if not team:
            return None, []
        
        qs = InjuryReport.objects.filter(
            player__team=team
        ).select_related('player', 'detected_game')
        
        if active_only:
            qs = qs.filter(is_active=True)
        
        qs = qs.order_by('-impact_score', '-reported_date')[:limit]
        
        result = []
        for injury in qs:
            result.append({
                "id": injury.id,
                "player": {
                    "id": injury.player.id,
                    "name": injury.player.full_name,
                    "position": injury.player.position,
                    "jersey": injury.player.jersey_number,
                    "avg_minutes": injury.player.avg_minutes,
                    "avg_points": injury.player.avg_points,
                    "is_starter": injury.player.is_starter,
                    "is_key_player": injury.player.is_key_player,
                },
                "status": injury.status,
                "injury_type": injury.injury_type,
                "detection_method": injury.detection_method,
                "reported_date": str(injury.reported_date),
                "expected_return": str(injury.expected_return) if injury.expected_return else None,
                "is_active": injury.is_active,
                "impact_score": injury.impact_score,
                "minutes_before": injury.minutes_before_injury,
            })
        
        return team, result
    
    team, injuries = await sync_to_async(_get_injuries)()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return {
        "team_id": team_id,
        "team_name": team.school,
        "total_injuries": len(injuries),
        "injuries": injuries
    }


@app.get("/api/teams/{team_id}/roster")
async def get_team_roster(
    team_id: int,
    season: int = Query(2026, description="Season year"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get roster/players for a specific team.
    """
    from basketball.models import Player
    
    def _get_roster():
        team = Team.objects.filter(id=team_id).first()
        if not team:
            return None, []
        
        players = Player.objects.filter(
            team=team,
            season=season,
            is_active=True
        ).order_by('-avg_minutes', 'last_name')[:limit]
        
        result = []
        for p in players:
            result.append({
                "id": p.id,
                "name": p.full_name,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "jersey": p.jersey_number,
                "position": p.position,
                "year": p.year,
                "height": p.height,
                "is_starter": p.is_starter,
                "is_key_player": p.is_key_player,
                "avg_minutes": p.avg_minutes,
                "avg_points": p.avg_points,
            })
        
        return team, result
    
    team, roster = await sync_to_async(_get_roster)()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return {
        "team_id": team_id,
        "team_name": team.school,
        "season": season,
        "players": roster
    }


@app.get("/api/teams/{team_id}/raw-stats")
async def get_team_raw_stats(
    team_id: int,
    season: int = Query(2026, description="Season year"),
):
    """
    Get raw aggregated stats for a team (FG%, 3P%, RPG, etc.).
    """
    from basketball.models import TeamSeasonStats
    
    def _get_stats():
        team = Team.objects.filter(id=team_id).first()
        if not team:
            return None, None
        
        stats = TeamSeasonStats.objects.filter(
            team=team,
            season=season
        ).first()
        
        return team, stats
    
    team, stats = await sync_to_async(_get_stats)()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    if not stats:
        raise HTTPException(
            status_code=404, 
            detail=f"No raw stats for {team.school}. Run 'python manage.py sync_box_scores' first."
        )
    
    return {
        "team_id": team_id,
        "team_name": team.school,
        "season": season,
        "games_played": stats.games_played,
        "record": f"{stats.wins}-{stats.losses}",
        "ppg": stats.ppg,
        "opp_ppg": stats.opp_ppg,
        "fg_pct": stats.fg_pct,
        "three_pct": stats.three_pct,
        "ft_pct": stats.ft_pct,
        "rpg": stats.rpg,
        "apg": stats.apg,
        "spg": stats.spg,
        "bpg": stats.bpg,
        "topg": stats.topg,
        # Raw totals
        "total_points": stats.total_points,
        "total_rebounds": stats.total_rebounds,
        "total_assists": stats.assists,
        "field_goals_made": stats.field_goals_made,
        "field_goals_attempted": stats.field_goals_attempted,
        "three_pointers_made": stats.three_pointers_made,
        "three_pointers_attempted": stats.three_pointers_attempted,
    }


@app.get("/api/injuries")
async def get_all_injuries(
    active_only: bool = Query(True, description="Only return active injuries"),
    min_impact: float = Query(0, description="Minimum impact score"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get all injuries across all teams, sorted by impact.
    Useful for seeing which teams are most affected.
    """
    from basketball.models import InjuryReport
    
    def _get_injuries():
        qs = InjuryReport.objects.select_related(
            'player', 'player__team'
        )
        
        if active_only:
            qs = qs.filter(is_active=True)
        
        if min_impact > 0:
            qs = qs.filter(impact_score__gte=min_impact)
        
        qs = qs.order_by('-impact_score', '-reported_date')[:limit]
        
        result = []
        for injury in qs:
            result.append({
                "id": injury.id,
                "team_id": injury.player.team.id,
                "team_name": injury.player.team.school,
                "player": {
                    "id": injury.player.id,
                    "name": injury.player.full_name,
                    "position": injury.player.position,
                    "avg_minutes": injury.player.avg_minutes,
                    "avg_points": injury.player.avg_points,
                },
                "status": injury.status,
                "injury_type": injury.injury_type,
                "reported_date": str(injury.reported_date),
                "impact_score": injury.impact_score,
            })
        
        return result
    
    injuries = await sync_to_async(_get_injuries)()
    
    return {
        "total": len(injuries),
        "injuries": injuries
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
