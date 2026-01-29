# Current Models and Data Storage Summary

## ✅ Existing Django Models

### Core Models (`basketball/models.py`)

1. **Conference**
   - `name`, `abbreviation`
   - Stores conference info (SEC, Big 12, ACC, etc.)

2. **Venue**
   - `source_id`, `name`, `city`, `state`, `capacity`
   - Stores arena/venue information

3. **Team**
   - `source_id` (ESPN ID from CSV)
   - `ncaa_slug` (NCAA API slug, e.g., "kansas", "duke")
   - `school`, `mascot`, `abbreviation`, `display_name`
   - `primary_color`, `secondary_color`
   - `conference` (FK), `venue` (FK)
   - **Indexed on**: `school`, `abbreviation`, `source_id`, `ncaa_slug`

4. **Game**
   - `ncaa_game_id` (unique, indexed)
   - `date`, `time`
   - `home_team` (FK), `away_team` (FK)
   - `venue` (FK)
   - `home_score`, `away_score`
   - `status` (scheduled, in_progress, final, postponed, cancelled)
   - `status_detail` (e.g., "Final", "1st Half")
   - `season` (year, e.g., 2026)
   - `season_type` (regular, postseason, preseason)
   - **Properties**: `is_final`, `winner`

5. **TeamStats**
   - `team` (FK), `season`
   - **Record**: `wins`, `losses`, `conference_wins`, `conference_losses`
   - **Scoring**: `points_per_game`, `points_allowed_per_game`
   - **Shooting**: `field_goal_pct`, `three_point_pct`, `free_throw_pct`
   - **Rebounds**: `rebounds_per_game`, `offensive_rebounds_per_game`, `defensive_rebounds_per_game`
   - **Other**: `assists_per_game`, `steals_per_game`, `blocks_per_game`, `turnovers_per_game`
   - **Note**: Most detailed stats fields exist but are currently NULL (not populated from API yet)

6. **FavoriteTeam** (User feature)
   - `user` (FK to SupabaseUser), `team` (FK)
   - Unique constraint on `[user, team]`

7. **MatchupPrediction** (User feature)
   - `user` (FK), `game` (FK), `predicted_winner` (FK)
   - `is_correct` (null until game is final)
   - `checked_at` (timestamp when prediction was evaluated)
   - Unique constraint on `[user, game]`

---

## ❌ Missing Models (Not Yet Implemented)

1. **Player** - No player model exists
2. **GameRoster** - No roster/lineup model
3. **PlayerStats** - No individual player statistics
4. **KenPomRating** - No KenPom data model

---

## 📊 Current NCAA API Data Storage

### ✅ What IS Being Stored:

1. **Team Information**
   - Source: `public/teams.csv` + NCAA API `/schools-index`
   - Stored: School name, mascot, abbreviation, colors, conference, venue
   - **NCAA Slug**: Fetched and stored for API matching
   - Command: `python manage.py import_teams`

2. **Game Results**
   - Source: NCAA API `/scoreboard/basketball-men/d1/{YYYY}/{MM}/{DD}`
   - Stored:
     - Game ID, date, time
     - Home/away teams
     - Scores (when final)
     - Status (scheduled, in_progress, final)
   - Command: `python manage.py sync_games [--date=YYYY-MM-DD] [--days=N] [--season=YYYY]`
   - **Can backfill historical games** by specifying date ranges

3. **Team Statistics (Basic)**
   - Source: NCAA API `/standings/basketball-men/d1/{year}/all-conf`
   - Stored:
     - ✅ Wins, losses
     - ✅ Conference wins, losses
     - ❌ Detailed stats (shooting %, rebounds, etc.) - fields exist but not populated
   - Command: `python manage.py sync_stats [--season=YYYY]`

### ❌ What is NOT Being Stored:

1. **Box Scores** - Not stored at all
2. **Player Minutes** - Not stored (no Player model)
3. **Player Statistics** - Not stored (no PlayerStats model)
4. **Game Rosters** - Not stored (no GameRoster model)
5. **Detailed Team Stats** - Fields exist in `TeamStats` but not populated from API

---

## 🏀 KenPom Data

### Current Status: **NOT IMPLEMENTED**

- ❌ No `KenPomRating` model
- ❌ No KenPom data storage
- ❌ No KenPom API integration
- 📝 Only mentioned in `INJURY_DETECTION_GUIDE.md` as a future feature

### What Would Be Needed:

1. **KenPomRating Model** (if implemented):
   - `team` (FK)
   - `season` (year)
   - `date` (for point-in-time ratings)
   - `rank` (overall KenPom rank)
   - `adjusted_offense` (AdjO)
   - `adjusted_defense` (AdjD)
   - `adjusted_tempo` (AdjT)
   - `luck` (Luck rating)
   - `strength_of_schedule` (SOS)
   - **Four Factors**:
     - `effective_fg_pct`
     - `turnover_pct`
     - `offensive_rebound_pct`
     - `free_throw_rate`
   - `win_pct` (predicted win percentage)

2. **Historical vs Current**:
   - Could store point-in-time ratings (historical archive)
   - Or just current ratings (simpler)

---

## 📅 Games in Database

### Current Sync Capabilities:

1. **Date Range Syncing**
   ```bash
   # Sync today's games
   python manage.py sync_games
   
   # Sync specific date
   python manage.py sync_games --date=2026-01-30
   
   # Sync date range
   python manage.py sync_games --date=2026-01-01 --days=30
   
   # Specify season
   python manage.py sync_games --season=2025 --date=2025-11-01 --days=120
   ```

2. **What Gets Synced**:
   - All games from scoreboard endpoint for specified dates
   - Both scheduled and completed games
   - Can backfill entire seasons

3. **Current Season**:
   - Default season: **2026**
   - Can sync any season by specifying `--season` parameter
   - Games are stored with `season` field for filtering

4. **Game Status Tracking**:
   - Games start as `scheduled`
   - Updated to `in_progress` when live
   - Updated to `final` when complete
   - Scores updated when available

---

## 🔍 Data Gaps for Injury Detection

To implement injury detection based on player minutes, you would need:

1. **Player Model**
   ```python
   class Player(models.Model):
       team = ForeignKey(Team)
       name = CharField
       position = CharField
       jersey_number = IntegerField
       # ... other player info
   ```

2. **GameRoster Model** (or similar)
   ```python
   class GameRoster(models.Model):
       game = ForeignKey(Game)
       player = ForeignKey(Player)
       minutes_played = DecimalField
       points = IntegerField
       rebounds = IntegerField
       # ... other box score stats
   ```

3. **Box Score Storage**
   - Currently exploring: `explore_ncaa_api` command
   - Endpoint: `/games/{gameId}/boxscore` (not yet working)
   - Would need to store player minutes per game

---

## 📋 Summary Table

| Data Type | Model Exists? | Data Stored? | Source | Command |
|-----------|--------------|--------------|--------|---------|
| **Teams** | ✅ Yes | ✅ Yes | CSV + NCAA API | `import_teams` |
| **Games** | ✅ Yes | ✅ Yes | NCAA API | `sync_games` |
| **Team Stats (Basic)** | ✅ Yes | ✅ Partial | NCAA API | `sync_stats` |
| **Team Stats (Detailed)** | ✅ Yes | ❌ No | - | - |
| **Players** | ❌ No | ❌ No | - | - |
| **Box Scores** | ❌ No | ❌ No | NCAA API | - |
| **Player Minutes** | ❌ No | ❌ No | NCAA API | - |
| **KenPom Ratings** | ❌ No | ❌ No | - | - |

---

## 🚀 Next Steps for Full Feature Set

1. **Add Player & GameRoster Models**
   - Create `Player` model
   - Create `GameRoster` or `BoxScore` model
   - Store player minutes per game

2. **Implement Box Score Syncing**
   - Fix boxscore endpoint discovery
   - Create sync command for box scores
   - Store player minutes and stats

3. **Add KenPom Integration**
   - Create `KenPomRating` model
   - Implement KenPom data fetching
   - Store historical or current ratings

4. **Enhance Team Stats**
   - Populate detailed stats fields in `TeamStats`
   - Fetch from appropriate NCAA API endpoints
