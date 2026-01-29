# NCAA API Injury Detection Guide

This guide helps you explore the NCAA API and build an injury detection system based on player minutes analysis.

## Quick Start

### 1. Explore Available Endpoints

```bash
# See all available commands
python manage.py explore_ncaa_api

# Test teams endpoint
python manage.py explore_ncaa_api --endpoint teams

# Test team details (replace 2246 with actual team ID)
python manage.py explore_ncaa_api --endpoint team --team-id 2246

# Test schedule endpoint
python manage.py explore_ncaa_api --endpoint schedule --team-id 2246

# Test boxscore (replace 123456 with actual game ID)
python manage.py explore_ncaa_api --endpoint boxscore --game-id 123456
```

### 2. Extract Game IDs from Scoreboard

First, get game IDs to test boxscore endpoints:

```bash
# Extract game IDs from today's scoreboard
python manage.py explore_ncaa_api --extract-game-ids
```

This will:
- Get today's games from scoreboard
- Show game IDs
- Test different boxscore endpoint patterns
- Save game IDs to `game_ids_for_testing.json`

### 3. Test Boxscore Endpoint

Once you have a game ID, test the boxscore:

```bash
# Use a real game ID from the scoreboard
python manage.py explore_ncaa_api --endpoint boxscore --game-id 6530705
```

### 4. Detect Injuries

Once boxscore endpoint works, detect injuries:

```bash
# Analyze last 5 games for a team (uses scoreboard if schedule doesn't work)
python manage.py explore_ncaa_api --detect-injuries --team-id 7 --games 5

# Customize threshold (default is 20% drop)
python manage.py explore_ncaa_api --detect-injuries --team-id 7 --games 5 --minute-drop-threshold 0.30
```

**Note:** Use your database team IDs (from `Team` model), not NCAA API team IDs. The script will look up the NCAA slug automatically.

## How Injury Detection Works

### The Concept

**Injury Detection via Minutes Change:**

```
Game 1 (Jan 20): Duke vs. UNC
- Paolo Banchero (C): 31 minutes

Game 2 (Jan 23): Duke vs. Virginia  
- Paolo Banchero (C): 8 minutes  ⚠️
- Backup C: 20 minutes (vs. 5 avg)

Signal: Paolo went from 31 → 8 minutes (74% drop)
This is a STRONG injury signal.
```

### What the Script Does

1. **Fetches Recent Games**: Gets the last N games for a team
2. **Extracts Player Minutes**: Pulls minutes played from box scores
3. **Calculates Averages**: Computes average minutes per player
4. **Detects Drops**: Flags players with significant minute drops
5. **Generates Report**: Creates JSON report with findings

### Thresholds

- **LOW Severity**: 20-30% minute drop
- **MEDIUM Severity**: 30-40% minute drop  
- **HIGH Severity**: 40%+ minute drop

## Expected API Endpoints

Based on NCAA API patterns, these endpoints likely exist:

```
GET /teams                    # List all teams
GET /teams/{teamId}           # Team details
GET /teams/{teamId}/schedule  # Team schedule
GET /games/{gameId}/boxscore  # Box score (THE GOLDMINE)
GET /teams/{teamId}/roster    # Team roster
GET /stats/players            # Player statistics
```

## Box Score Structure (What We're Looking For)

The box score should contain:

```json
{
  "gameId": "123456",
  "homeTeam": {
    "players": [
      {
        "name": "Paolo Banchero",
        "position": "C",
        "minutes": 31,
        "points": 18,
        "rebounds": 8
      }
    ]
  },
  "awayTeam": {
    "players": [...]
  }
}
```

**Key Fields We Need:**
- Player name
- Minutes played
- Position (to weight impact)
- Points/rebounds (to rule out foul trouble)

## Integration with Your Prediction Model

Once you have working endpoints, you can:

1. **Add Injury Feature to Predictions**
   ```python
   def calculate_injury_impact(team_id, game_date):
       # Get recent games
       # Analyze minutes
       # Return injury score (0-1)
       return injury_score
   ```

2. **Weight by Position**
   - Center out = -3% win probability
   - Guard out = -1% win probability
   - Bench player = -0.5% win probability

3. **Combine with KenPom**
   - KenPom efficiency drop + Minutes drop = Strong injury signal
   - Use both signals together for better accuracy

## Output Format

The script generates a JSON report:

```json
{
  "team_id": 2246,
  "analysis_date": "2026-01-20T12:00:00",
  "games_analyzed": 5,
  "potential_injuries": [
    {
      "player": "Paolo Banchero",
      "avg_minutes": 28.5,
      "recent_minutes": 8,
      "previous_minutes": 31,
      "drop_pct": 71.9,
      "severity": "HIGH"
    }
  ],
  "all_player_minutes": {
    "Paolo Banchero": [31, 30, 29, 31, 8],
    "Other Player": [25, 24, 26, 25, 24]
  }
}
```

## Next Steps

1. **Run the exploration script** to find working endpoints
2. **Test with known teams** (Duke, UNC, Kansas, etc.)
3. **Verify box score structure** matches expectations
4. **Build integration** into your prediction model
5. **Backtest** to measure accuracy improvement

## Troubleshooting

**"No working endpoint found"**
- Try different URL patterns
- Check if API requires authentication
- Verify team/game IDs are correct

**"Could not fetch schedule"**
- Try exploring endpoints first to find correct URL pattern
- Check if team ID format is correct (might be string vs int)

**"No player minutes found"**
- Box score structure might be different
- Check the JSON output to see actual structure
- Modify `extract_player_minutes()` function to match your API

## Example Workflow

```bash
# 1. Extract game IDs from today's scoreboard
python manage.py explore_ncaa_api --extract-game-ids
# This shows you game IDs and tests boxscore patterns

# 2. Test boxscore with a real game ID (from step 1)
python manage.py explore_ncaa_api --endpoint boxscore --game-id 6530705

# 3. Find your team ID from database (use Team model ID, not NCAA ID)
# Check your database or use: python manage.py shell
# >>> from basketball.models import Team
# >>> Team.objects.get(school="Duke").id

# 4. Run injury detection (uses scoreboard if schedule endpoint doesn't work)
python manage.py explore_ncaa_api --detect-injuries --team-id 7 --games 5
```

**Important:** The `--team-id` should be your **database Team ID** (from the `Team` model), not the NCAA API team ID. The script will automatically look up the NCAA slug.

## Expected Impact

If you can successfully extract box scores:

| Feature | Accuracy Gain |
|---------|---------------|
| Injury detection (minutes) | +2-4% |
| Position-weighted impact | +0.5-1% |
| Combined with KenPom | +1-2% |
| **Total Potential** | **+3.5-7%** |

This could be the missing piece to improve your prediction accuracy!
