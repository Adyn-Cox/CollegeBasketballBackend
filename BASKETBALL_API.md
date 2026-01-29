# College Basketball API Documentation

Complete API reference for all basketball-related endpoints.

**Base URL:** `http://localhost:5000`

**Authentication:** Most endpoints require a valid Supabase JWT token in the `Authorization: Bearer <token>` header. Exceptions are noted.

---

## Table of Contents

1. [Teams API](#teams-api)
2. [Games API](#games-api)
3. [Conferences API](#conferences-api)
4. [User Favorites API](#user-favorites-api)
5. [User Predictions API](#user-predictions-api)
6. [KenPom Data API](#kenpom-data-api)
7. [ML Predictions API](#ml-predictions-api)

---

## Teams API

### List Teams

```
GET /api/teams
```

Get a paginated list of all teams with optional search and filtering.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | string | - | Search by school name or abbreviation |
| `conference` | string | - | Filter by conference abbreviation (e.g., "SEC", "B12") |
| `limit` | int | 100 | Results per page (1-500) |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "total": 367,
  "teams": [
    {
      "id": 37,
      "school": "Arizona",
      "mascot": "Wildcats",
      "abbreviation": "ARIZ",
      "display_name": "Arizona Wildcats",
      "primary_color": "0c234b",
      "secondary_color": "ab0520",
      "conference": "Big 12"
    }
  ]
}
```

---

### Get Team Details

```
GET /api/teams/{team_id}
```

Get detailed information about a specific team including venue.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | int | Team ID |

**Response:**
```json
{
  "id": 37,
  "school": "Arizona",
  "mascot": "Wildcats",
  "abbreviation": "ARIZ",
  "display_name": "Arizona Wildcats",
  "short_display_name": "Arizona",
  "primary_color": "0c234b",
  "secondary_color": "ab0520",
  "conference": {
    "id": 1,
    "name": "Big 12 Conference",
    "abbreviation": "B12"
  },
  "venue": {
    "id": 8,
    "name": "McKale Memorial Center",
    "city": "Tucson",
    "state": "AZ",
    "capacity": 14644
  },
  "ncaa_slug": "arizona"
}
```

---

### Get Team Games

```
GET /api/teams/{team_id}/games
```

Get games for a specific team with filtering options.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | int | Team ID |

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | current | Season year (e.g., 2026) |
| `status` | string | - | Filter: "scheduled", "in_progress", "final" |
| `past_only` | bool | false | Only show completed games |
| `upcoming_only` | bool | false | Only show future games |
| `limit` | int | 100 | Results per page (1-500) |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "total": 31,
  "games": [
    {
      "id": 12345,
      "ncaa_game_id": "6305551",
      "date": "2026-01-28",
      "time": "19:00:00",
      "home_team": {
        "id": 37,
        "school": "Arizona",
        "abbreviation": "ARIZ"
      },
      "away_team": {
        "id": 38,
        "school": "Arizona State",
        "abbreviation": "ASU"
      },
      "home_score": 85,
      "away_score": 72,
      "status": "final",
      "venue": {
        "id": 8,
        "name": "McKale Memorial Center"
      },
      "season": 2026,
      "season_type": "regular"
    }
  ]
}
```

---

### Get Team Schedule

```
GET /api/teams/{team_id}/schedule
```

Get the complete season schedule for a team (all games, chronologically ordered).

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | int | Team ID |

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | current | Season year |
| `limit` | int | 500 | Max games to return |

**Response:** Same format as Get Team Games.

---

### Get Team Stats

```
GET /api/teams/{team_id}/stats
```

Get season statistics for a team.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | int | Team ID |

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | 2026 | Season year |

**Response:**
```json
{
  "team_id": 37,
  "season": 2026,
  "wins": 21,
  "losses": 0,
  "conference_wins": 8,
  "conference_losses": 0,
  "record": "21-0",
  "conference_record": "8-0",
  "points_per_game": 84.5,
  "points_allowed_per_game": 68.2,
  "field_goal_pct": 0.485,
  "three_point_pct": 0.372,
  "free_throw_pct": 0.781,
  "rebounds_per_game": 38.4,
  "assists_per_game": 16.8,
  "steals_per_game": 7.2,
  "blocks_per_game": 4.5,
  "turnovers_per_game": 11.3
}
```

---

## Games API

### Get Today's Games

```
GET /api/games/today
```

Get all games scheduled for today (US Eastern time).

**Response:**
```json
{
  "total": 42,
  "games": [
    {
      "id": 12345,
      "date": "2026-01-28",
      "time": "19:00:00",
      "home_team": { "id": 37, "school": "Arizona", "abbreviation": "ARIZ" },
      "away_team": { "id": 38, "school": "Arizona State", "abbreviation": "ASU" },
      "status": "scheduled",
      "venue": { "name": "McKale Memorial Center" }
    }
  ]
}
```

---

### Get Week's Games

```
GET /api/games/week
```

Get all games for a 7-day period (US Eastern time).

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | date | today | Start date (YYYY-MM-DD) |

**Response:** Same format as Today's Games.

---

### Get Game Details

```
GET /api/games/{game_id}
```

Get detailed information about a specific game.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `game_id` | int | Game ID |

**Response:**
```json
{
  "id": 12345,
  "ncaa_game_id": "6305551",
  "date": "2026-01-28",
  "time": "19:00:00",
  "home_team": {
    "id": 37,
    "school": "Arizona",
    "abbreviation": "ARIZ",
    "conference": "Big 12"
  },
  "away_team": {
    "id": 38,
    "school": "Arizona State",
    "abbreviation": "ASU",
    "conference": "Big 12"
  },
  "home_score": 85,
  "away_score": 72,
  "status": "final",
  "venue": {
    "id": 8,
    "name": "McKale Memorial Center",
    "city": "Tucson",
    "state": "AZ"
  },
  "season": 2026,
  "season_type": "regular"
}
```

---

## Conferences API

### List Conferences

```
GET /api/conferences
```

Get all conferences.

**Response:**
```json
[
  {
    "id": 1,
    "name": "Big 12 Conference",
    "abbreviation": "B12"
  },
  {
    "id": 2,
    "name": "Southeastern Conference",
    "abbreviation": "SEC"
  }
]
```

---

## User Favorites API

**⚠️ All endpoints require authentication**

### Add Favorite Team

```
POST /api/users/me/favorites
```

Add a team to user's favorites.

**Request Body:**
```json
{
  "team_id": 37
}
```

**Response:**
```json
{
  "message": "Team added to favorites",
  "team": {
    "id": 37,
    "school": "Arizona",
    "abbreviation": "ARIZ"
  }
}
```

---

### Remove Favorite Team

```
DELETE /api/users/me/favorites/{team_id}
```

Remove a team from favorites.

**Response:**
```json
{
  "message": "Team removed from favorites"
}
```

---

### Get Favorite Teams

```
GET /api/users/me/favorites
```

Get all user's favorite teams.

**Response:**
```json
{
  "total": 3,
  "teams": [
    { "id": 37, "school": "Arizona", "abbreviation": "ARIZ" },
    { "id": 549, "school": "Kentucky", "abbreviation": "UK" }
  ]
}
```

---

## User Predictions API

**⚠️ All endpoints require authentication**

### Create Prediction

```
POST /api/predictions
```

Predict the winner of a game. Can only predict games that haven't finished.

**Request Body:**
```json
{
  "game_id": 12345,
  "predicted_winner_id": 37
}
```

**Response:**
```json
{
  "id": 1,
  "game": {
    "id": 12345,
    "date": "2026-01-28",
    "home_team": { "id": 37, "school": "Arizona" },
    "away_team": { "id": 38, "school": "Arizona State" },
    "status": "scheduled"
  },
  "predicted_winner": { "id": 37, "school": "Arizona" },
  "is_correct": null,
  "checked_at": null,
  "created_at": "2026-01-28T10:30:00Z",
  "updated_at": "2026-01-28T10:30:00Z"
}
```

---

### Get Prediction

```
GET /api/predictions/{prediction_id}
```

Get a specific prediction.

---

### Update Prediction (Full)

```
PUT /api/predictions/{prediction_id}
```

Completely update a prediction (game must not be final).

**Request Body:**
```json
{
  "game_id": 12345,
  "predicted_winner_id": 38
}
```

---

### Update Prediction (Partial)

```
PATCH /api/predictions/{prediction_id}
```

Partially update a prediction (only winner).

**Request Body:**
```json
{
  "predicted_winner_id": 38
}
```

---

### Delete Prediction

```
DELETE /api/predictions/{prediction_id}
```

Delete a prediction (game must not be final).

---

### Get User Predictions

```
GET /api/users/me/predictions
```

Get all user's predictions with filtering.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | - | Filter by season year |
| `status` | string | - | "correct", "incorrect", or "pending" |
| `limit` | int | 100 | Results per page |
| `offset` | int | 0 | Pagination offset |

---

### Get Prediction Stats

```
GET /api/users/me/prediction-stats
```

Get user's prediction performance statistics.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | - | Filter by season year |

**Response:**
```json
{
  "total_predictions": 50,
  "correct": 35,
  "incorrect": 10,
  "pending": 5,
  "accuracy": 0.778,
  "accuracy_percentage": "77.8%"
}
```

---

## KenPom Data API

Advanced analytics data from KenPom.

### Get KenPom Ratings

```
GET /api/kenpom/ratings
```

Get KenPom ratings for all teams in a season.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `season` | int | ✅ | Season year (e.g., 2026) |
| `limit` | int | - | Results per page (default 100) |
| `offset` | int | - | Pagination offset |

**Response:**
```json
[
  {
    "id": 1,
    "team_id": 37,
    "team_school": "Arizona",
    "season": 2026,
    "rank_adj_em": 1,
    "adj_em": 32.45,
    "adj_oe": 125.3,
    "adj_de": 92.85,
    "adj_tempo": 68.5,
    "wins": 21,
    "losses": 0,
    "sos": 8.45,
    "luck": 0.023,
    "pythag": 0.982,
    "coach": "Tommy Lloyd"
  }
]
```

**Key Fields Explained:**
- `adj_em`: Adjusted Efficiency Margin (points better than avg D1 team)
- `adj_oe`: Adjusted Offensive Efficiency (points per 100 possessions)
- `adj_de`: Adjusted Defensive Efficiency (lower is better)
- `adj_tempo`: Adjusted Tempo (possessions per 40 minutes)
- `sos`: Strength of Schedule
- `luck`: How much record differs from expected based on efficiency
- `pythag`: Expected winning percentage

---

### Get Team's KenPom Rating

```
GET /api/kenpom/ratings/{team_id}
```

Get KenPom rating for a specific team.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | latest | Season year |

---

### Get Four Factors

```
GET /api/kenpom/four-factors/{team_id}
```

Get Dean Oliver's Four Factors statistics for a team.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | latest | Season year |
| `conference_only` | bool | false | Only conference games |

**Response:**
```json
{
  "team_id": 37,
  "season": 2026,
  "efg_pct": 56.2,
  "rank_efg_pct": 5,
  "to_pct": 15.8,
  "rank_to_pct": 45,
  "or_pct": 32.4,
  "rank_or_pct": 18,
  "ft_rate": 38.5,
  "rank_ft_rate": 22,
  "defg_pct": 44.2,
  "rank_defg_pct": 8,
  "dto_pct": 21.3,
  "rank_dto_pct": 12,
  "dor_pct": 24.5,
  "rank_dor_pct": 15,
  "dft_rate": 28.9,
  "rank_dft_rate": 35
}
```

**Four Factors Explained:**
- **eFG% (Effective FG%)**: Shooting efficiency adjusted for 3-pointers
- **TO% (Turnover Rate)**: Turnovers per possession
- **OR% (Offensive Rebound %)**: % of missed shots rebounded
- **FT Rate**: Free throws attempted per field goal attempt
- **D-** prefix: Defensive versions (what opponents do against you)

---

### Get KenPom Predictions (FanMatch)

```
GET /api/kenpom/predictions
```

Get KenPom's game predictions for a specific date.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `date` | string | ✅ | Date (YYYY-MM-DD) |
| `limit` | int | - | Results limit |

**Response:**
```json
[
  {
    "id": 1,
    "kenpom_game_id": 12345,
    "date": "2026-01-28",
    "home_team": { "id": 37, "school": "Arizona" },
    "away_team": { "id": 38, "school": "Arizona State" },
    "home_rank": 1,
    "away_rank": 45,
    "home_predicted_score": 82.5,
    "away_predicted_score": 68.3,
    "home_win_probability": 0.92,
    "predicted_tempo": 68.5,
    "thrill_score": 24.5
  }
]
```

---

### Get KenPom Prediction for Game

```
GET /api/kenpom/predictions/{game_id}
```

Get KenPom's prediction for a specific game.

---

### Get KenPom Matchup Analysis

```
GET /api/kenpom/matchup/{home_team_id}/{away_team_id}
```

Get comprehensive matchup analysis between two teams.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | current | Season year |

**Response:**
```json
{
  "home_team": {
    "id": 37,
    "school": "Arizona",
    "adj_em": 32.45,
    "adj_oe": 125.3,
    "adj_de": 92.85,
    "adj_tempo": 68.5,
    "rank": 1
  },
  "away_team": {
    "id": 38,
    "school": "Arizona State",
    "adj_em": 8.23,
    "adj_oe": 108.5,
    "adj_de": 100.27,
    "adj_tempo": 66.2,
    "rank": 45
  },
  "matchup": {
    "adj_em_diff": 24.22,
    "tempo_diff": 2.3,
    "predicted_winner": "Arizona",
    "win_probability": 0.92,
    "predicted_margin": 14.5,
    "predicted_total": 145.8,
    "expected_tempo": 67.35
  },
  "four_factors_edge": {
    "efg_edge": 8.5,
    "to_edge": -2.3,
    "or_edge": 5.2,
    "ft_rate_edge": 4.1
  }
}
```

---

### Get KenPom History

```
GET /api/kenpom/history/{team_id}
```

Get historical KenPom ratings over time for a team.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | current | Season year |
| `limit` | int | 50 | Max records |

**Response:**
```json
[
  {
    "id": 1,
    "team_id": 37,
    "season": 2026,
    "archive_date": "2026-01-28",
    "is_preseason": false,
    "adj_em": 32.45,
    "rank_adj_em": 1,
    "adj_oe": 125.3,
    "adj_de": 92.85,
    "rank_change": 0,
    "adj_em_change": 0.5
  }
]
```

---

## ML Predictions API

Machine learning predictions for game outcomes.

### Get ML Prediction for Game

```
GET /api/ml/predictions/{game_id}
```

Get ML model prediction for a specific game.

**Response:**
```json
{
  "id": 1,
  "game_id": 12345,
  "home_team_id": 37,
  "home_team_school": "Arizona",
  "away_team_id": 38,
  "away_team_school": "Arizona State",
  "game_date": "2026-01-28",
  "home_win_probability": 0.89,
  "predicted_home_score": 82.5,
  "predicted_away_score": 68.3,
  "predicted_margin": 14.2,
  "confidence_score": 0.78,
  "predicted_winner": "Arizona",
  "predicted_winner_id": 37,
  "model_version": "v20260128_120000",
  "predicted_at": "2026-01-28T06:00:00Z",
  "home_adj_em": 32.45,
  "away_adj_em": 8.23,
  "home_momentum": 1.25,
  "away_momentum": 0.45,
  "venue_hca": 3.8
}
```

---

### Get ML Predictions List

```
GET /api/ml/predictions
```

Get ML predictions with filtering.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | string | - | Filter by date (YYYY-MM-DD) |
| `team_id` | int | - | Filter by team ID |
| `season` | int | - | Filter by season |
| `limit` | int | 50 | Results limit |
| `offset` | int | 0 | Pagination offset |

---

### Get ML Matchup Prediction

```
GET /api/ml/matchup/{home_team_id}/{away_team_id}
```

Get ML prediction for a hypothetical matchup (not in schedule).

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | current | Season year |

**Response:**
```json
{
  "home_team_id": 37,
  "home_team_school": "Arizona",
  "away_team_id": 38,
  "away_team_school": "Arizona State",
  "home_win_probability": 0.89,
  "predicted_home_score": 82.5,
  "predicted_away_score": 68.3,
  "predicted_margin": 14.2,
  "confidence_score": 0.78,
  "predicted_winner": "Arizona",
  "model_version": "v20260128_120000",
  "features": {
    "adj_em_diff": 24.22,
    "home_momentum": 1.25,
    "away_momentum": 0.45,
    "venue_hca": 3.5,
    "efg_mismatch": 8.5,
    "to_mismatch": -2.3
  }
}
```

---

### Get ML Model Info

```
GET /api/ml/model/info
```

Get information about the active ML model.

**Response:**
```json
{
  "version": "v20260128_120000",
  "is_active": true,
  "training_date": "2026-01-28T04:00:00Z",
  "training_games_count": 2500,
  "test_accuracy": 0.762,
  "test_log_loss": 0.523,
  "feature_count": 55,
  "top_features": [
    "adj_em_diff",
    "home_momentum",
    "venue_hca",
    "efg_mismatch",
    "rank_diff"
  ]
}
```

---

### Get ML Model Versions

```
GET /api/ml/model/versions
```

Get list of all ML model versions.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 10 | Max versions to return |

**Response:**
```json
[
  {
    "version": "v20260128_120000",
    "is_active": true,
    "training_date": "2026-01-28T04:00:00Z",
    "training_games_count": 2500,
    "test_accuracy": 0.762,
    "test_log_loss": 0.523,
    "feature_count": 55
  }
]
```

---

### Get ML Features for Game

```
GET /api/ml/features/{game_id}
```

Get all feature values used for a game's prediction (debugging).

**Response:**
```json
{
  "game_id": 12345,
  "model_version": "v20260128_120000",
  "features_hash": "a1b2c3d4e5f6g7h8",
  "features": {
    "adj_em_diff": 24.22,
    "adj_em_diff_with_hca": 27.72,
    "adj_oe_diff": 16.8,
    "adj_de_diff": -7.42,
    "tempo_diff": 2.3,
    "home_adj_em": 32.45,
    "away_adj_em": 8.23,
    "home_momentum": 1.25,
    "away_momentum": 0.45,
    "venue_hca": 3.5,
    "efg_mismatch": 8.5,
    "to_mismatch": -2.3,
    "or_mismatch": 5.2,
    "home_recent_win_pct": 1.0,
    "away_recent_win_pct": 0.6,
    "h2h_games": 3,
    "h2h_win_pct": 0.67
  },
  "predicted_at": "2026-01-28T06:00:00Z"
}
```

---

## Error Responses

All endpoints return standard error responses:

**400 Bad Request:**
```json
{
  "detail": "Invalid date format. Use YYYY-MM-DD"
}
```

**401 Unauthorized:**
```json
{
  "detail": "Invalid or expired token"
}
```

**404 Not Found:**
```json
{
  "detail": "Team not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limits

No explicit rate limits are enforced, but please be reasonable with API calls.

---

## Data Sync Commands

Data is populated using Django management commands (run separately from the API):

```bash
# Sync games from NCAA API
python manage.py sync_games --days=7

# Sync team statistics  
python manage.py sync_stats

# Sync KenPom data
python manage.py sync_kenpom_ratings --season=2026
python manage.py sync_kenpom_four_factors --season=2026
python manage.py sync_kenpom_fanmatch --date=2026-01-28

# Train ML model
python manage.py train_ml_model --season=2026 --activate

# Generate ML predictions
python manage.py generate_ml_predictions
```
