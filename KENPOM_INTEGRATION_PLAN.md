# KenPom API Integration Plan

## 🎯 Overview

Integrate KenPom API to enhance predictions with advanced analytics including:
- Adjusted Efficiency Margins (AdjEM)
- Four Factors (eFG%, TO%, OR%, FT Rate)
- Historical point-in-time ratings
- Game predictions (FanMatch)
- Team height, experience, bench strength

---

## 📊 Database Models

### 1. KenPomTeam (Team Mapping)
**Purpose**: Map KenPom TeamID to our Team model

```python
class KenPomTeam(models.Model):
    """Maps KenPom TeamID to our Team model."""
    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name='kenpom')
    kenpom_team_id = models.IntegerField(unique=True, db_index=True)
    kenpom_team_name = models.CharField(max_length=200)  # Store KenPom's exact name
    matched_at = models.DateTimeField(auto_now_add=True)
    last_verified = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kenpom_teams'
```

### 2. KenPomRating (Current Ratings)
**Purpose**: Store current season ratings (updated daily)

```python
class KenPomRating(models.Model):
    """Current KenPom ratings for a season."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kenpom_ratings')
    season = models.IntegerField(db_index=True)  # Ending year (e.g., 2025 = 2024-25)
    
    # Data metadata
    data_through = models.CharField(max_length=100)  # "Jan 28, 2025" or similar
    seed = models.IntegerField(null=True, blank=True)  # Tournament seed
    coach = models.CharField(max_length=100, blank=True)
    wins = models.IntegerField()
    losses = models.IntegerField()
    
    # Core Ratings
    adj_em = models.FloatField()  # Adjusted Efficiency Margin
    rank_adj_em = models.IntegerField()
    pythag = models.FloatField()  # Pythagorean expectation
    rank_pythag = models.IntegerField()
    
    # Offense
    adj_oe = models.FloatField()  # Adjusted Offensive Efficiency
    rank_adj_oe = models.IntegerField()
    oe = models.FloatField()  # Raw Offensive Efficiency
    rank_oe = models.IntegerField()
    
    # Defense
    adj_de = models.FloatField()  # Adjusted Defensive Efficiency
    rank_adj_de = models.IntegerField()
    de = models.FloatField()  # Raw Defensive Efficiency
    rank_de = models.IntegerField()
    
    # Tempo
    tempo = models.FloatField()  # Possessions per 40 minutes
    rank_tempo = models.IntegerField()
    adj_tempo = models.FloatField()
    rank_adj_tempo = models.IntegerField()
    
    # Advanced
    luck = models.FloatField()
    rank_luck = models.IntegerField()
    sos = models.FloatField()  # Strength of Schedule
    rank_sos = models.IntegerField()
    sos_offense = models.FloatField()
    rank_sos_offense = models.IntegerField()
    sos_defense = models.FloatField()
    rank_sos_defense = models.IntegerField()
    ncsos = models.FloatField()  # Non-Conference SOS
    rank_ncsos = models.IntegerField()
    
    # Possession Length
    apl_offense = models.FloatField()  # Average Possession Length (Offense)
    rank_apl_offense = models.IntegerField()
    apl_defense = models.FloatField()
    rank_apl_defense = models.IntegerField()
    conf_apl_offense = models.FloatField()
    rank_conf_apl_offense = models.IntegerField()
    conf_apl_defense = models.FloatField()
    rank_conf_apl_defense = models.IntegerField()
    
    # Metadata
    event = models.CharField(max_length=100, blank=True)  # Tournament event
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kenpom_ratings'
        unique_together = ['team', 'season']
        indexes = [
            models.Index(fields=['season']),
            models.Index(fields=['rank_adj_em']),
        ]
```

### 3. KenPomRatingArchive (Historical Ratings)
**Purpose**: Store point-in-time ratings for historical analysis

```python
class KenPomRatingArchive(models.Model):
    """Historical point-in-time KenPom ratings."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kenpom_archives')
    season = models.IntegerField(db_index=True)
    archive_date = models.DateField(db_index=True)  # Date of this rating snapshot
    is_preseason = models.BooleanField(default=False)
    
    # Ratings on archive date
    adj_em = models.FloatField()
    rank_adj_em = models.IntegerField()
    adj_oe = models.FloatField()
    rank_adj_oe = models.IntegerField()
    adj_de = models.FloatField()
    rank_adj_de = models.IntegerField()
    adj_tempo = models.FloatField()
    rank_adj_tempo = models.IntegerField()
    
    # Final ratings (for comparison)
    adj_em_final = models.FloatField()
    rank_adj_em_final = models.IntegerField()
    adj_oe_final = models.FloatField()
    rank_adj_oe_final = models.IntegerField()
    adj_de_final = models.FloatField()
    rank_adj_de_final = models.IntegerField()
    adj_tempo_final = models.FloatField()
    rank_adj_tempo_final = models.IntegerField()
    
    # Changes from archive to final
    rank_change = models.IntegerField()  # Change in rank
    adj_em_change = models.FloatField()  # Change in AdjEM
    adj_tempo_change = models.FloatField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'kenpom_rating_archives'
        unique_together = ['team', 'season', 'archive_date']
        indexes = [
            models.Index(fields=['season', 'archive_date']),
            models.Index(fields=['team', 'archive_date']),
        ]
```

### 4. KenPomFourFactors (Four Factors Stats)
**Purpose**: Store Four Factors data (critical for predictions)

```python
class KenPomFourFactors(models.Model):
    """Four Factors statistics from KenPom."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kenpom_four_factors')
    season = models.IntegerField(db_index=True)
    is_conference_only = models.BooleanField(default=False)
    data_through = models.CharField(max_length=100)
    
    # Offensive Four Factors
    efg_pct = models.FloatField()  # Effective FG%
    rank_efg_pct = models.IntegerField()
    to_pct = models.FloatField()  # Turnover%
    rank_to_pct = models.IntegerField()
    or_pct = models.FloatField()  # Offensive Rebound%
    rank_or_pct = models.IntegerField()
    ft_rate = models.FloatField()  # Free Throw Rate
    rank_ft_rate = models.IntegerField()
    
    # Defensive Four Factors
    defg_pct = models.FloatField()  # Effective FG% Allowed
    rank_defg_pct = models.IntegerField()
    dto_pct = models.FloatField()  # Turnover% Forced
    rank_dto_pct = models.IntegerField()
    dor_pct = models.FloatField()  # Defensive Rebound%
    rank_dor_pct = models.IntegerField()
    dft_rate = models.FloatField()  # FT Rate Allowed
    rank_dft_rate = models.IntegerField()
    
    # Also include efficiency ratings for convenience
    oe = models.FloatField()
    rank_oe = models.IntegerField()
    de = models.FloatField()
    rank_de = models.IntegerField()
    tempo = models.FloatField()
    rank_tempo = models.IntegerField()
    adj_oe = models.FloatField()
    rank_adj_oe = models.IntegerField()
    adj_de = models.FloatField()
    rank_adj_de = models.IntegerField()
    adj_tempo = models.FloatField()
    rank_adj_tempo = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kenpom_four_factors'
        unique_together = ['team', 'season', 'is_conference_only']
        indexes = [
            models.Index(fields=['season']),
        ]
```

### 5. KenPomFanMatch (Game Predictions)
**Purpose**: Store KenPom game predictions

```python
class KenPomFanMatch(models.Model):
    """KenPom game predictions (FanMatch)."""
    season = models.IntegerField(db_index=True)
    kenpom_game_id = models.IntegerField(unique=True, db_index=True)
    date = models.DateField(db_index=True)
    
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kenpom_home_predictions')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kenpom_away_predictions')
    
    # Rankings on game date
    home_rank = models.IntegerField()
    away_rank = models.IntegerField()
    
    # Predictions
    home_predicted_score = models.FloatField()
    away_predicted_score = models.FloatField()
    home_win_probability = models.FloatField()  # 0.0 to 1.0
    predicted_tempo = models.FloatField()
    thrill_score = models.FloatField()
    
    # Link to our Game model (if available)
    game = models.ForeignKey(
        Game, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='kenpom_predictions'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'kenpom_fanmatch'
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['season', 'date']),
        ]
```

### 6. KenPomHeight (Team Height/Experience Stats)
**Purpose**: Store height, experience, bench strength

```python
class KenPomHeight(models.Model):
    """Team height, experience, and bench statistics."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kenpom_height')
    season = models.IntegerField(db_index=True)
    data_through = models.CharField(max_length=100)
    
    # Height stats
    avg_height = models.FloatField()  # Average height in inches
    avg_height_rank = models.IntegerField()
    effective_height = models.FloatField()
    effective_height_rank = models.IntegerField()
    
    # Position heights
    height_center = models.FloatField()
    height_center_rank = models.IntegerField()
    height_pf = models.FloatField()
    height_pf_rank = models.IntegerField()
    height_sf = models.FloatField()
    height_sf_rank = models.IntegerField()
    height_sg = models.FloatField()
    height_sg_rank = models.IntegerField()
    height_pg = models.FloatField()
    height_pg_rank = models.IntegerField()
    
    # Experience & Bench
    experience = models.FloatField()
    experience_rank = models.IntegerField()
    bench_strength = models.FloatField()
    bench_strength_rank = models.IntegerField()
    continuity = models.FloatField()
    continuity_rank = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kenpom_height'
        unique_together = ['team', 'season']
```

### 7. KenPomMiscStats (Miscellaneous Stats)
**Purpose**: Store advanced miscellaneous statistics

```python
class KenPomMiscStats(models.Model):
    """Miscellaneous advanced statistics."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kenpom_misc_stats')
    season = models.IntegerField(db_index=True)
    is_conference_only = models.BooleanField(default=False)
    data_through = models.CharField(max_length=100)
    
    # Offensive shooting
    fg3_pct = models.FloatField()
    rank_fg3_pct = models.IntegerField()
    fg2_pct = models.FloatField()
    rank_fg2_pct = models.IntegerField()
    ft_pct = models.FloatField()
    rank_ft_pct = models.IntegerField()
    
    # Offensive advanced
    block_pct = models.FloatField()
    rank_block_pct = models.IntegerField()
    steal_rate = models.FloatField()
    rank_steal_rate = models.IntegerField()
    ns_turnover_rate = models.FloatField()  # Non-steal turnover rate
    rank_ns_turnover_rate = models.IntegerField()
    assist_rate = models.FloatField()
    rank_assist_rate = models.IntegerField()
    fg3_attempt_rate = models.FloatField()
    rank_fg3_attempt_rate = models.IntegerField()
    avg_2pa_distance = models.FloatField()
    rank_avg_2pa_distance = models.IntegerField()
    
    # Defensive shooting allowed
    opp_fg3_pct = models.FloatField()
    rank_opp_fg3_pct = models.IntegerField()
    opp_fg2_pct = models.FloatField()
    rank_opp_fg2_pct = models.IntegerField()
    opp_ft_pct = models.FloatField()
    rank_opp_ft_pct = models.IntegerField()
    
    # Defensive advanced
    opp_block_pct = models.FloatField()
    rank_opp_block_pct = models.IntegerField()
    opp_steal_rate = models.FloatField()
    rank_opp_steal_rate = models.IntegerField()
    opp_ns_turnover_rate = models.FloatField()
    rank_opp_ns_turnover_rate = models.IntegerField()
    opp_assist_rate = models.FloatField()
    rank_opp_assist_rate = models.IntegerField()
    opp_fg3_attempt_rate = models.FloatField()
    rank_opp_fg3_attempt_rate = models.IntegerField()
    opp_avg_2pa_distance = models.FloatField()
    rank_opp_avg_2pa_distance = models.IntegerField()
    
    # Efficiency ratings (for convenience)
    adj_oe = models.FloatField()
    rank_adj_oe = models.IntegerField()
    adj_de = models.FloatField()
    rank_adj_de = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kenpom_misc_stats'
        unique_together = ['team', 'season', 'is_conference_only']
```

---

## 🔗 Team Matching Strategy

### Challenge
KenPom uses `TeamID` (integer) and `TeamName` (string). We need to match to our `Team` model.

### Solution: Multi-Step Matching Process

1. **Initial Sync**: Fetch KenPom teams endpoint
2. **Matching Algorithm**:
   - Try exact name match: `Team.school == KenPom.TeamName`
   - Try display name match: `Team.display_name == KenPom.TeamName`
   - Try fuzzy matching on school name
   - Try abbreviation matching
   - Manual review for unmatched teams

3. **Create KenPomTeam records** linking `Team` to `kenpom_team_id`

### Implementation
```python
# Management command: sync_kenpom_teams
# 1. Fetch /api.php?endpoint=teams&y=2025
# 2. For each KenPom team:
#    - Try to find matching Team
#    - Create KenPomTeam record
#    - Log unmatched teams for manual review
```

---

## 📥 Data Sync Commands

### 1. `sync_kenpom_teams`
**Purpose**: Map KenPom teams to our Team model
```bash
python manage.py sync_kenpom_teams --season=2025
```
- Fetches teams endpoint
- Matches to existing Team records
- Creates KenPomTeam mappings
- Reports unmatched teams

### 2. `sync_kenpom_ratings`
**Purpose**: Sync current season ratings
```bash
python manage.py sync_kenpom_ratings --season=2025
python manage.py sync_kenpom_ratings --team-id=73 --season=2025
python manage.py sync_kenpom_ratings --conference=B12 --season=2025
```
- Fetches ratings endpoint
- Updates or creates KenPomRating records
- Can sync all teams, specific team, or conference

### 3. `sync_kenpom_archive`
**Purpose**: Sync historical point-in-time ratings
```bash
# Sync specific date
python manage.py sync_kenpom_archive --date=2025-02-15 --season=2025

# Sync preseason
python manage.py sync_kenpom_archive --preseason --season=2025

# Sync date range (custom script)
python manage.py sync_kenpom_archive --start-date=2025-01-01 --end-date=2025-03-15 --season=2025
```
- Fetches archive endpoint
- Creates KenPomRatingArchive records
- Useful for historical analysis

### 4. `sync_kenpom_four_factors`
**Purpose**: Sync Four Factors data
```bash
python manage.py sync_kenpom_four_factors --season=2025
python manage.py sync_kenpom_four_factors --team-id=42 --season=2025
python manage.py sync_kenpom_four_factors --conference=A10 --season=2025
python manage.py sync_kenpom_four_factors --season=2025 --conference-only
```
- Fetches four-factors endpoint
- Updates KenPomFourFactors records
- Can sync all, team, or conference
- Supports conference-only stats

### 5. `sync_kenpom_fanmatch`
**Purpose**: Sync game predictions for a date
```bash
python manage.py sync_kenpom_fanmatch --date=2025-01-30
```
- Fetches fanmatch endpoint
- Creates KenPomFanMatch records
- Can link to existing Game records if matched

### 6. `sync_kenpom_height`
**Purpose**: Sync height/experience stats
```bash
python manage.py sync_kenpom_height --season=2025
```

### 7. `sync_kenpom_misc_stats`
**Purpose**: Sync miscellaneous stats
```bash
python manage.py sync_kenpom_misc_stats --season=2025
```

---

## 🔄 Sync Strategy & Frequency

### Daily Syncs (High Priority)
1. **Ratings** - Update daily (ratings change daily)
2. **Four Factors** - Update daily (critical for predictions)
3. **FanMatch** - Sync for today's games

### Weekly Syncs (Medium Priority)
1. **Height/Experience** - Update weekly (changes less frequently)
2. **Misc Stats** - Update weekly

### On-Demand Syncs
1. **Archive** - Sync specific dates as needed
2. **Preseason** - Sync once at season start

### Recommended Schedule
```bash
# Daily cron job (runs at 2 AM)
0 2 * * * cd /path/to/project && python manage.py sync_kenpom_ratings --season=2025
0 2 * * * cd /path/to/project && python manage.py sync_kenpom_four_factors --season=2025
0 2 * * * cd /path/to/project && python manage.py sync_kenpom_fanmatch --date=$(date +\%Y-\%m-\%d)

# Weekly cron job (runs Sunday at 3 AM)
0 3 * * 0 cd /path/to/project && python manage.py sync_kenpom_height --season=2025
0 3 * * 0 cd /path/to/project && python manage.py sync_kenpom_misc_stats --season=2025
```

---

## 🎯 Integration with Predictions

### Enhanced Prediction Features

1. **Use AdjEM for Win Probability**
   - Calculate expected margin: `home_adj_em - away_adj_em`
   - Convert to win probability using Pythagorean expectation

2. **Four Factors Matchup Analysis**
   - Compare team's offensive Four Factors vs opponent's defensive Four Factors
   - Identify matchup advantages

3. **Tempo Prediction**
   - Use predicted tempo to estimate possessions
   - Adjust score predictions based on tempo

4. **Historical Trends**
   - Use archive data to see how teams performed at similar points in season
   - Track rating changes over time

5. **Injury Detection Enhancement**
   - Combine KenPom efficiency drops with player minutes drops
   - Bench strength changes could indicate injuries

---

## 🔧 API Client Implementation

### Base Client
```python
# basketball/kenpom/client.py
import requests
from django.conf import settings

class KenPomClient:
    BASE_URL = "https://kenpom.com"
    
    def __init__(self):
        self.api_key = settings.KENPOM_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def _get(self, endpoint, params=None):
        """Make GET request to KenPom API."""
        url = f"{self.BASE_URL}/api.php"
        params = params or {}
        params['endpoint'] = endpoint
        
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_ratings(self, season=None, team_id=None, conference=None):
        """Get ratings endpoint."""
        params = {}
        if season:
            params['y'] = season
        if team_id:
            params['team_id'] = team_id
        if conference:
            params['c'] = conference
        return self._get('ratings', params)
    
    def get_archive(self, date=None, season=None, preseason=False, team_id=None, conference=None):
        """Get archive endpoint."""
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
    
    # ... other endpoint methods
```

---

## 📋 Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create all models
- [ ] Run migrations
- [ ] Create KenPomClient
- [ ] Implement `sync_kenpom_teams` command
- [ ] Test team matching

### Phase 2: Core Ratings (Week 1)
- [ ] Implement `sync_kenpom_ratings` command
- [ ] Test ratings sync
- [ ] Create API endpoints to expose ratings

### Phase 3: Four Factors (Week 2)
- [ ] Implement `sync_kenpom_four_factors` command
- [ ] Test Four Factors sync
- [ ] Create API endpoints

### Phase 4: Predictions (Week 2)
- [ ] Implement `sync_kenpom_fanmatch` command
- [ ] Link FanMatch to Game model
- [ ] Create prediction comparison endpoints

### Phase 5: Advanced Stats (Week 3)
- [ ] Implement height, misc stats syncs
- [ ] Implement archive sync
- [ ] Create historical analysis endpoints

### Phase 6: Integration (Week 3)
- [ ] Enhance prediction algorithm with KenPom data
- [ ] Add KenPom data to game detail endpoints
- [ ] Create matchup analysis endpoints

---

## 🚨 Important Considerations

### 1. API Rate Limits
- **Unknown**: KenPom docs don't specify rate limits
- **Strategy**: Add delays between requests, batch operations
- **Recommendation**: Start with 1 request/second, adjust based on response

### 2. Data Freshness
- Ratings update daily (usually overnight)
- Sync in early morning (2-4 AM) to get latest data
- Archive data is static (no need to re-sync)

### 3. Team Matching Edge Cases
- Some teams may have name variations
- Conference changes (teams switching conferences)
- Create admin interface for manual matching

### 4. Error Handling
- Handle API failures gracefully
- Log errors for debugging
- Retry logic for transient failures

### 5. Data Validation
- Validate all numeric fields
- Check for missing required fields
- Handle null/empty values appropriately

---

## 📊 API Endpoints to Add

### FastAPI Endpoints (in `app.py`)

1. **GET /api/kenpom/teams** - List all teams with KenPom data
2. **GET /api/kenpom/ratings** - Get current ratings
3. **GET /api/kenpom/ratings/{team_id}** - Get team's ratings
4. **GET /api/kenpom/four-factors/{team_id}** - Get Four Factors
5. **GET /api/kenpom/predictions/{game_id}** - Get KenPom prediction for game
6. **GET /api/kenpom/matchup/{home_team_id}/{away_team_id}** - Matchup analysis
7. **GET /api/kenpom/history/{team_id}** - Historical ratings

---

## ✅ Next Steps

1. **Review this plan** - Make adjustments as needed
2. **Create models** - Start with KenPomTeam and KenPomRating
3. **Implement team matching** - Critical first step
4. **Test API connection** - Verify API key works
5. **Build sync commands** - Start with ratings
6. **Create API endpoints** - Expose data to frontend
7. **Integrate with predictions** - Enhance prediction algorithm

---

## 📝 Notes

- All KenPom seasons use **ending year** (2025 = 2024-25 season)
- Conference abbreviations match KenPom's format (B12, ACC, BE, etc.)
- Archive data allows point-in-time analysis (powerful for research)
- FanMatch predictions are only available for past dates (up to today)
- Four Factors are critical for understanding team strengths/weaknesses
