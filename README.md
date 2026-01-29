# CollegeBasketballBackend

Backend for college basketball predictor using FastAPI with Supabase authentication.

## Prerequisites

- Python 3.12+
- PostgreSQL database
- Supabase account (for authentication)

## Setup

### 1. Create Python Virtual Environment

Create and activate a virtual environment:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

**Note:** On Windows, use `.venv\Scripts\activate` instead.

You should see `(.venv)` in your terminal prompt when activated.

### 2. Install Dependencies

Install required Python packages:

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the project root with the following variables:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_ANON_KEY=your-anon-key
KENPOM_API_KEY=your-kenpom-api-key  # Optional - for KenPom features
```

**Where to find values:**
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_JWT_SECRET`: Supabase Dashboard → Settings → API → JWT Secret
- `SUPABASE_ANON_KEY`: Supabase Dashboard → Settings → API → anon/public key
- `KENPOM_API_KEY`: Your KenPom API key (from kenpom.com account)

### 4. Database Migrations

Run database migrations to create the necessary tables:

```bash
./migrate.sh
```

Or manually:

```bash
python manage.py makemigrations authentication
python manage.py migrate
```

**Note:** Make sure your PostgreSQL database is running and the `DATABASE_URL` in `.env` is correct.

### 5. Run the Application

Start the FastAPI server on port 5001:

```bash
./run.sh
```

Or manually:

```bash
uvicorn app:app --host 0.0.0.0 --port 5001 --reload
```

The server will be available at `http://127.0.0.1:5001/`

**API Documentation:**
- Interactive docs: `http://127.0.0.1:5001/docs` (Swagger UI)
- Alternative docs: `http://127.0.0.1:5001/redoc` (ReDoc)

### 6. Data Sync Scripts (Separate from App)

**IMPORTANT:** These scripts are Django management commands that update the database. 
They should be run **separately** from the FastAPI app, not while the app is running.

**Import Teams:**
```bash
# Import teams from CSV and fetch NCAA slugs
python manage.py import_teams
```

**Sync Games:**
```bash
# Sync games for today
python manage.py sync_games

# Sync games for a specific date
python manage.py sync_games --date 2026-01-15

# Sync games for multiple days
python manage.py sync_games --date 2026-01-15 --days 7
```

**Sync Team Stats:**
```bash
# Sync stats for current season (default)
python manage.py sync_stats

# Sync stats for a specific season
python manage.py sync_stats --season 2026
```

**Note:** These scripts connect to the NCAA API running on `localhost:3005`. 
Make sure the NCAA API is running before executing these commands.

### KenPom Data Sync (Requires KENPOM_API_KEY)

**Sync KenPom Teams (First time setup):**
```bash
# Map KenPom teams to our database teams
python manage.py sync_kenpom_teams --season=2026
```

**Sync KenPom Ratings (Daily):**
```bash
# Sync all ratings for the season
python manage.py sync_kenpom_ratings --season=2026

# Sync specific conference
python manage.py sync_kenpom_ratings --season=2026 --conference=B12
```

**Sync Four Factors (Daily):**
```bash
python manage.py sync_kenpom_four_factors --season=2026
```

**Sync FanMatch Predictions:**
```bash
# Sync predictions for a specific date
python manage.py sync_kenpom_fanmatch --date=2026-01-28

# Sync multiple days and link to existing games
python manage.py sync_kenpom_fanmatch --date=2026-01-28 --days=7 --link-games
```

**Sync Height/Experience Stats (Weekly):**
```bash
python manage.py sync_kenpom_height --season=2026
```

**Sync Miscellaneous Stats (Weekly):**
```bash
python manage.py sync_kenpom_misc_stats --season=2026
```

**Sync Historical Archives:**
```bash
# Sync specific date
python manage.py sync_kenpom_archive --date=2026-02-15

# Sync preseason ratings
python manage.py sync_kenpom_archive --preseason --season=2026

# Sync date range
python manage.py sync_kenpom_archive --start-date=2026-01-01 --end-date=2026-03-15
```

## API Endpoints

### Authentication Endpoints (Public - no token required)

- **POST** `/api/auth/login` - Login and save user/tokens
  - Body: `{ "access_token": "...", "refresh_token": "..." }`
  
- **POST** `/api/auth/logout` - Logout and remove refresh token
  - Body: `{ "refresh_token": "..." }`
  
- **POST** `/api/auth/refresh` - Refresh access token
  - Body: `{ "refresh_token": "..." }`

### Basketball Endpoints

- **GET** `/api/teams` - List all teams
  - Query params: `search`, `conference`, `limit`, `offset`
  
- **GET** `/api/teams/{team_id}` - Get team details
  
- **GET** `/api/teams/{team_id}/schedule` - Get complete team schedule (all games for season)
  - Query params: `season` (defaults to current year), `limit`
  
- **GET** `/api/teams/{team_id}/games` - Get team games with filters
  - Query params: `season`, `status`, `past_only`, `upcoming_only`, `limit`, `offset`
  
- **GET** `/api/teams/{team_id}/stats` - Get team statistics
  - Query params: `season` (defaults to 2026)
  
- **GET** `/api/games/today` - Get all games scheduled for today
  
- **GET** `/api/games/week` - Get games for a 7-day period
  - Query params: `start_date` (defaults to today)
  
- **GET** `/api/games/{game_id}` - Get specific game details
  
- **GET** `/api/conferences` - List all conferences

### KenPom Endpoints

- **GET** `/api/kenpom/ratings` - Get KenPom ratings for a season
  - Query params: `season` (required), `limit`, `offset`
  
- **GET** `/api/kenpom/ratings/{team_id}` - Get KenPom rating for a team
  - Query params: `season` (optional, defaults to most recent)
  
- **GET** `/api/kenpom/four-factors/{team_id}` - Get Four Factors for a team
  - Query params: `season`, `conference_only`
  
- **GET** `/api/kenpom/predictions` - Get FanMatch predictions for a date
  - Query params: `date` (required, YYYY-MM-DD format), `limit`
  
- **GET** `/api/kenpom/predictions/{game_id}` - Get KenPom prediction for a game
  
- **GET** `/api/kenpom/matchup/{home_team_id}/{away_team_id}` - Get matchup analysis
  - Query params: `season`
  - Returns: efficiency differentials, Four Factors mismatches, win probability
  
- **GET** `/api/kenpom/history/{team_id}` - Get historical ratings for a team
  - Query params: `season`, `limit`

### ML Prediction Endpoints

- **GET** `/api/ml/predictions/{game_id}` - Get ML prediction for a specific game
  - Returns: win probability, predicted scores, confidence, key features
  
- **GET** `/api/ml/predictions` - List ML predictions with filters
  - Query params: `date`, `team_id`, `season`, `limit`, `offset`
  
- **GET** `/api/ml/matchup/{home_team_id}/{away_team_id}` - Get prediction for hypothetical matchup
  - Query params: `season`
  - Uses current KenPom ratings to predict outcome
  
- **GET** `/api/ml/model/info` - Get active model version info
  - Returns: version, accuracy, training date, features
  
- **GET** `/api/ml/model/versions` - List all model versions
  - Query params: `limit`
  
- **GET** `/api/ml/features/{game_id}` - Get feature values for a game (debugging)

## ML Model Training

### Train a New Model
```bash
# Train on current season data
python manage.py train_ml_model --season=2026

# Train with custom parameters
python manage.py train_ml_model --season=2026 --max-depth=8 --learning-rate=0.02

# Train and activate immediately
python manage.py train_ml_model --season=2026 --activate
```

### Generate Predictions
```bash
# Generate predictions for upcoming games (next 7 days)
python manage.py generate_ml_predictions

# Generate for specific date
python manage.py generate_ml_predictions --date=2026-02-01

# Update existing predictions with latest data
python manage.py generate_ml_predictions --update-existing
```

### Model Features
The ML model uses the following key features:
- **KenPom Ratings**: AdjEM, AdjOE, AdjDE, Tempo, SOS
- **Opponent-Adjusted Momentum**: Recent performance weighted by opponent strength
- **Four Factors Mismatches**: eFG%, TO%, OR%, FT Rate differentials
- **Venue HCA**: Learned home court advantage by venue
- **Recent Form**: Win/loss record over last 10 games
- **Rest Days**: Days since last game
- **Head-to-Head**: Historical matchup record

## Project Structure

```
├── app.py                  # FastAPI application (main entry point)
├── authentication/         # Authentication app
│   ├── models.py           # SupabaseUser model (Django ORM)
│   ├── views.py            # Django REST Framework views (legacy)
│   ├── middleware.py       # Token validation middleware (legacy)
│   └── utils.py            # JWT validation utilities
├── basketball/             # Basketball data and ML
│   ├── models.py           # Team, Game, KenPom, ML models
│   ├── ml_features.py      # Feature engineering
│   ├── ml_model.py         # Model loading and prediction
│   ├── kenpom/             # KenPom API client
│   │   └── client.py       # KenPom API wrapper
│   ├── ml_models/          # Saved ML models (created after training)
│   └── management/commands/
│       ├── train_ml_model.py
│       ├── generate_ml_predictions.py
│       ├── sync_kenpom_*.py
│       └── sync_games.py
├── config/                 # Django project settings (for ORM)
│   ├── settings.py         # Main configuration
│   └── urls.py             # URL routing (legacy)
├── manage.py               # Django management script (for migrations)
├── requirements.txt        # Python dependencies
├── migrate.sh              # Migration script
└── run.sh                  # Run FastAPI server script
```

## Troubleshooting

- **Virtual environment not activating:** Make sure you're in the project root directory
- **Database connection errors:** Verify `DATABASE_URL` in `.env` is correct and PostgreSQL is running
- **Module not found errors:** Make sure virtual environment is activated and dependencies are installed
- **Port 5001 already in use:** Change the port in `run.sh` or kill the process using port 5001
- **FastAPI not found:** Make sure you've installed dependencies: `pip install -r requirements.txt`
