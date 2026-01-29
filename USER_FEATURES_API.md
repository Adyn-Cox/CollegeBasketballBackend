# User Features API Documentation

Documentation for user-specific features: favorite teams and matchup predictions.

**Base URL:** `http://localhost:5001` (or your server URL)

**Authentication:** All endpoints require authentication via Bearer token in the `Authorization` header.

---

## Table of Contents

1. [Favorite Teams](#favorite-teams)
2. [Matchup Predictions](#matchup-predictions)
3. [Response Models](#response-models)

---

## Favorite Teams

### 1. Add Favorite Team

**POST** `/api/users/me/favorites`

Add a team to the current user's favorites.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "team_id": 7
}
```

**Response (201 Created):**
```json
{
  "message": "Team added to favorites",
  "team": {
    "id": 7,
    "source_id": "333",
    "school": "Alabama",
    "mascot": "Crimson Tide",
    "abbreviation": "ALA",
    "display_name": "Alabama Crimson Tide",
    "short_display_name": "Alabama",
    "primary_color": "9e1632",
    "secondary_color": "ffffff",
    "conference": {
      "id": 4,
      "name": "Southeastern Conference",
      "abbreviation": "SEC"
    }
  }
}
```

**Errors:**
- `400 Bad Request`: Team already in favorites
- `404 Not Found`: Team not found
- `401 Unauthorized`: Missing or invalid token

---

### 2. Remove Favorite Team

**DELETE** `/api/users/me/favorites/{team_id}`

Remove a team from the current user's favorites.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Path Parameters:**
- `team_id` (required, int): Team ID to remove

**Example Request:**
```bash
DELETE /api/users/me/favorites/7
```

**Response (200 OK):**
```json
{
  "message": "Team removed from favorites"
}
```

**Errors:**
- `404 Not Found`: Favorite team not found
- `401 Unauthorized`: Missing or invalid token

---

### 3. Get Favorite Teams

**GET** `/api/users/me/favorites`

Get all favorite teams for the current user.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Example Request:**
```bash
GET /api/users/me/favorites
```

**Response (200 OK):**
```json
{
  "total": 3,
  "teams": [
    {
      "id": 7,
      "source_id": "333",
      "school": "Alabama",
      "mascot": "Crimson Tide",
      "abbreviation": "ALA",
      "display_name": "Alabama Crimson Tide",
      "short_display_name": "Alabama",
      "primary_color": "9e1632",
      "secondary_color": "ffffff",
      "conference": {
        "id": 4,
        "name": "Southeastern Conference",
        "abbreviation": "SEC"
      }
    }
  ]
}
```

**Note:** Teams are ordered by when they were added (most recent first).

---

## Matchup Predictions

### 4. Create Prediction

**POST** `/api/predictions`

Create a prediction for a game matchup (predict which team will win).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "game_id": 1234,
  "predicted_winner_id": 7
}
```

**Response (201 Created):**
```json
{
  "id": 567,
  "game_id": 1234,
  "predicted_winner_id": 7,
  "predicted_winner": {
    "id": 7,
    "source_id": "333",
    "school": "Alabama",
    "mascot": "Crimson Tide",
    "abbreviation": "ALA",
    "display_name": "Alabama Crimson Tide",
    "short_display_name": "Alabama",
    "primary_color": "9e1632",
    "secondary_color": "ffffff",
    "conference": {
      "id": 4,
      "name": "Southeastern Conference",
      "abbreviation": "SEC"
    }
  },
  "game": {
    "id": 1234,
    "ncaa_game_id": "12345678",
    "date": "2026-01-20",
    "time": "19:00",
    "home_team": { ... },
    "away_team": { ... },
    "home_score": null,
    "away_score": null,
    "status": "scheduled",
    "status_detail": "Scheduled",
    "season": 2026,
    "season_type": "regular",
    "venue": { ... }
  },
  "is_correct": null,
  "checked_at": null,
  "created_at": "2026-01-19T12:00:00Z"
}
```

**Errors:**
- `400 Bad Request`: 
  - "Game not found"
  - "Predicted winner must be one of the teams in the game"
  - "Cannot predict on a game that is already final"
- `401 Unauthorized`: Missing or invalid token

**Note:** 
- You can update a prediction by creating a new one for the same game (it will replace the old prediction)
- Predictions are automatically checked when games are finalized via the `sync_games` script

---

### 5. Get User Predictions

**GET** `/api/users/me/predictions`

Get all predictions for the current user with optional filters.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `season` (optional, int): Filter by season year
- `status` (optional, string): Filter by prediction status
  - `"correct"`: Only correct predictions
  - `"incorrect"`: Only incorrect predictions
  - `"pending"`: Only unchecked predictions (games not yet final)
- `limit` (optional, int): Number of results (default: 100, max: 500)
- `offset` (optional, int): Pagination offset (default: 0)

**Example Requests:**
```bash
# Get all predictions
GET /api/users/me/predictions

# Get only correct predictions
GET /api/users/me/predictions?status=correct

# Get pending predictions for current season
GET /api/users/me/predictions?status=pending&season=2026

# Get predictions with pagination
GET /api/users/me/predictions?limit=50&offset=50
```

**Response (200 OK):**
```json
[
  {
    "id": 567,
    "game_id": 1234,
    "predicted_winner_id": 7,
    "predicted_winner": { ... },
    "game": { ... },
    "is_correct": true,
    "checked_at": "2026-01-20T22:00:00Z",
    "created_at": "2026-01-19T12:00:00Z"
  }
]
```

**Note:** Predictions are ordered by creation date (most recent first).

---

### 6. Get Prediction Statistics

**GET** `/api/users/me/prediction-stats`

Get prediction statistics for the current user.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `season` (optional, int): Filter by season year

**Example Request:**
```bash
GET /api/users/me/prediction-stats?season=2026
```

**Response (200 OK):**
```json
{
  "total_predictions": 50,
  "correct_predictions": 35,
  "incorrect_predictions": 10,
  "pending_predictions": 5,
  "win_percentage": 77.78
}
```

**Note:** 
- `win_percentage` is calculated only from checked predictions (correct + incorrect)
- `pending_predictions` are predictions for games that haven't finished yet

---

## How Predictions Are Checked

When you run the `sync_games` management command, it automatically:

1. Updates game scores and status from the NCAA API
2. When a game becomes final (status changes to "final"), it checks all predictions for that game
3. Sets `is_correct` to `true` or `false` based on the actual winner
4. Sets `checked_at` timestamp

**Example:**
```bash
# Sync games for today (will check predictions for any games that became final)
python manage.py sync_games

# Sync games for a specific date
python manage.py sync_games --date 2026-01-20
```

**Important:** The `sync_games` script should be run separately from the FastAPI app (not while the app is running).

---

## Response Models

### PredictionResponse
```json
{
  "id": 567,
  "game_id": 1234,
  "predicted_winner_id": 7,
  "predicted_winner": { ... }, // TeamListResponse
  "game": { ... }, // GameResponse
  "is_correct": true, // or false, or null if not checked yet
  "checked_at": "2026-01-20T22:00:00Z", // or null if not checked
  "created_at": "2026-01-19T12:00:00Z"
}
```

### PredictionStatsResponse
```json
{
  "total_predictions": 50,
  "correct_predictions": 35,
  "incorrect_predictions": 10,
  "pending_predictions": 5,
  "win_percentage": 77.78 // Percentage of correct predictions (only from checked)
}
```

---

## Common Use Cases

### Add favorite teams
```bash
POST /api/users/me/favorites
{
  "team_id": 7
}
```

### View favorite teams
```bash
GET /api/users/me/favorites
```

### Make a prediction
```bash
POST /api/predictions
{
  "game_id": 1234,
  "predicted_winner_id": 7
}
```

### Check prediction record
```bash
GET /api/users/me/prediction-stats
```

### View all predictions
```bash
GET /api/users/me/predictions
```

### View only correct predictions
```bash
GET /api/users/me/predictions?status=correct
```

### View pending predictions (games not yet final)
```bash
GET /api/users/me/predictions?status=pending
```

---

## Database Migration

After adding these features, run migrations:

```bash
python manage.py migrate
```

This will create the following tables:
- `favorite_teams` - Stores user's favorite teams
- `matchup_predictions` - Stores user's game predictions

---

## Notes

- All endpoints require authentication
- Users can have multiple favorite teams
- Users can only have one prediction per game (creating a new prediction replaces the old one)
- Predictions cannot be created for games that are already final
- Predictions are automatically checked when games are finalized via `sync_games`
- The `win_percentage` in stats only includes checked predictions (excludes pending)
