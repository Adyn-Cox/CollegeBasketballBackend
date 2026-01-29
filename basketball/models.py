"""Models for college basketball data."""
from django.db import models
from authentication.models import SupabaseUser


class Conference(models.Model):
    """Conference model (SEC, Big 12, ACC, etc.)."""
    
    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=20, unique=True, db_index=True)
    
    class Meta:
        db_table = 'conferences'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Venue(models.Model):
    """Venue/Arena model."""
    
    source_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    capacity = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'venues'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.city}, {self.state})" if self.city else self.name


class Team(models.Model):
    """College basketball team model."""
    
    # IDs
    source_id = models.CharField(max_length=50, unique=True, db_index=True)  # ESPN ID from CSV
    ncaa_slug = models.CharField(max_length=100, blank=True, db_index=True)  # NCAA API slug (e.g., "kansas", "duke")
    
    # Basic info
    school = models.CharField(max_length=200, db_index=True)
    mascot = models.CharField(max_length=100, blank=True)
    abbreviation = models.CharField(max_length=20, blank=True, db_index=True)
    display_name = models.CharField(max_length=200)
    short_display_name = models.CharField(max_length=100, blank=True)
    
    # Colors
    primary_color = models.CharField(max_length=10, blank=True)  # Hex color
    secondary_color = models.CharField(max_length=10, blank=True)  # Hex color
    
    # Relationships
    conference = models.ForeignKey(
        Conference, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='teams'
    )
    venue = models.ForeignKey(
        Venue, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='teams'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teams'
        ordering = ['school']
        indexes = [
            models.Index(fields=['school']),
            models.Index(fields=['abbreviation']),
            models.Index(fields=['source_id']),
            models.Index(fields=['ncaa_slug']),
        ]
    
    def __str__(self):
        return self.display_name


class Game(models.Model):
    """Game/Matchup model."""
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('final', 'Final'),
        ('postponed', 'Postponed'),
        ('cancelled', 'Cancelled'),
    ]
    
    SEASON_TYPE_CHOICES = [
        ('regular', 'Regular Season'),
        ('postseason', 'Postseason'),
        ('preseason', 'Preseason'),
    ]
    
    # IDs
    ncaa_game_id = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Date/Time
    date = models.DateField(db_index=True)
    time = models.TimeField(null=True, blank=True)
    
    # Teams
    home_team = models.ForeignKey(
        Team, 
        on_delete=models.CASCADE, 
        related_name='home_games'
    )
    away_team = models.ForeignKey(
        Team, 
        on_delete=models.CASCADE, 
        related_name='away_games'
    )
    
    # Venue
    venue = models.ForeignKey(
        Venue, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='games'
    )
    
    # Scores
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', db_index=True)
    status_detail = models.CharField(max_length=100, blank=True)  # e.g., "Final", "1st Half", "8:00 PM ET"
    
    # Season info
    season = models.IntegerField(db_index=True)  # e.g., 2026
    season_type = models.CharField(max_length=20, choices=SEASON_TYPE_CHOICES, default='regular')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'games'
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['season']),
            models.Index(fields=['status']),
            models.Index(fields=['ncaa_game_id']),
        ]
    
    def __str__(self):
        return f"{self.away_team.abbreviation} @ {self.home_team.abbreviation} ({self.date})"
    
    @property
    def is_final(self):
        return self.status == 'final'
    
    @property
    def winner(self):
        if not self.is_final or self.home_score is None or self.away_score is None:
            return None
        return self.home_team if self.home_score > self.away_score else self.away_team


class TeamStats(models.Model):
    """Team statistics for a season."""
    
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='stats')
    season = models.IntegerField(db_index=True)
    
    # Record
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    conference_wins = models.IntegerField(default=0)
    conference_losses = models.IntegerField(default=0)
    
    # Scoring
    points_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    points_allowed_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Shooting percentages
    field_goal_pct = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    three_point_pct = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    free_throw_pct = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    
    # Rebounds
    rebounds_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    offensive_rebounds_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    defensive_rebounds_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Other stats
    assists_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    steals_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    blocks_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    turnovers_per_game = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'team_stats'
        unique_together = ['team', 'season']
        ordering = ['-season', 'team__school']
        indexes = [
            models.Index(fields=['season']),
        ]
    
    def __str__(self):
        return f"{self.team.school} ({self.season}) - {self.wins}-{self.losses}"
    
    @property
    def win_pct(self):
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0
    
    @property
    def record(self):
        return f"{self.wins}-{self.losses}"
    
    @property
    def conference_record(self):
        return f"{self.conference_wins}-{self.conference_losses}"


class FavoriteTeam(models.Model):
    """User's favorite teams."""
    
    user = models.ForeignKey(
        SupabaseUser,
        on_delete=models.CASCADE,
        related_name='favorite_teams'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'favorite_teams'
        unique_together = ['user', 'team']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['team']),
        ]
    
    def __str__(self):
        return f"{self.user.email} -> {self.team.school}"


class MatchupPrediction(models.Model):
    """User's predictions for game matchups."""
    
    user = models.ForeignKey(
        SupabaseUser,
        on_delete=models.CASCADE,
        related_name='predictions'
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='predictions'
    )
    predicted_winner = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='predicted_wins'
    )
    
    # Prediction result (set when game is final)
    is_correct = models.BooleanField(null=True, blank=True, db_index=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'matchup_predictions'
        unique_together = ['user', 'game']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['game']),
            models.Index(fields=['is_correct']),
            models.Index(fields=['user', 'is_correct']),
        ]
    
    def __str__(self):
        return f"{self.user.email} predicted {self.predicted_winner.school} to win {self.game}"
    
    def check_prediction(self):
        """Check if prediction is correct based on game result."""
        if not self.game.is_final:
            return False
        
        actual_winner = self.game.winner
        if actual_winner is None:
            return False
        
        self.is_correct = (self.predicted_winner == actual_winner)
        from django.utils import timezone
        self.checked_at = timezone.now()
        self.save()
        return True


# ============== KenPom Models ==============

class KenPomTeam(models.Model):
    """Maps KenPom TeamID to our Team model."""
    
    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name='kenpom')
    kenpom_team_id = models.IntegerField(unique=True, db_index=True)
    kenpom_team_name = models.CharField(max_length=200)  # Store KenPom's exact name
    matched_at = models.DateTimeField(auto_now_add=True)
    last_verified = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kenpom_teams'
        verbose_name = 'KenPom Team Mapping'
        verbose_name_plural = 'KenPom Team Mappings'
    
    def __str__(self):
        return f"{self.team.school} -> KenPom ID: {self.kenpom_team_id}"


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
    apl_offense = models.FloatField(null=True, blank=True)  # Average Possession Length (Offense)
    rank_apl_offense = models.IntegerField(null=True, blank=True)
    apl_defense = models.FloatField(null=True, blank=True)
    rank_apl_defense = models.IntegerField(null=True, blank=True)
    conf_apl_offense = models.FloatField(null=True, blank=True)
    rank_conf_apl_offense = models.IntegerField(null=True, blank=True)
    conf_apl_defense = models.FloatField(null=True, blank=True)
    rank_conf_apl_defense = models.IntegerField(null=True, blank=True)
    
    # Metadata
    event = models.CharField(max_length=100, blank=True, null=True, default='')  # Tournament event
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kenpom_ratings'
        unique_together = ['team', 'season']
        ordering = ['rank_adj_em']
        indexes = [
            models.Index(fields=['season']),
            models.Index(fields=['rank_adj_em']),
        ]
    
    def __str__(self):
        return f"{self.team.school} ({self.season}) - Rank #{self.rank_adj_em}"


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
    
    # Final ratings (for comparison) - nullable since season may not be over
    adj_em_final = models.FloatField(null=True, blank=True)
    rank_adj_em_final = models.IntegerField(null=True, blank=True)
    adj_oe_final = models.FloatField(null=True, blank=True)
    rank_adj_oe_final = models.IntegerField(null=True, blank=True)
    adj_de_final = models.FloatField(null=True, blank=True)
    rank_adj_de_final = models.IntegerField(null=True, blank=True)
    adj_tempo_final = models.FloatField(null=True, blank=True)
    rank_adj_tempo_final = models.IntegerField(null=True, blank=True)
    
    # Changes from archive to final
    rank_change = models.IntegerField(null=True, blank=True)  # Change in rank
    adj_em_change = models.FloatField(null=True, blank=True)  # Change in AdjEM
    adj_tempo_change = models.FloatField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'kenpom_rating_archives'
        unique_together = ['team', 'season', 'archive_date']
        ordering = ['-archive_date', 'rank_adj_em']
        indexes = [
            models.Index(fields=['season', 'archive_date']),
            models.Index(fields=['team', 'archive_date']),
        ]
    
    def __str__(self):
        return f"{self.team.school} ({self.archive_date}) - Rank #{self.rank_adj_em}"


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
        ordering = ['-season', 'team__school']
        indexes = [
            models.Index(fields=['season']),
        ]
    
    def __str__(self):
        conf_str = " (Conf)" if self.is_conference_only else ""
        return f"{self.team.school} ({self.season}){conf_str} Four Factors"


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
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['season', 'date']),
        ]
    
    def __str__(self):
        return f"{self.away_team.abbreviation} @ {self.home_team.abbreviation} ({self.date})"
    
    @property
    def predicted_winner(self):
        """Return the predicted winner based on win probability."""
        return self.home_team if self.home_win_probability > 0.5 else self.away_team
    
    @property
    def predicted_margin(self):
        """Return the predicted point margin (positive = home favored)."""
        return self.home_predicted_score - self.away_predicted_score


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
        ordering = ['-season', 'team__school']
    
    def __str__(self):
        return f"{self.team.school} ({self.season}) Height/Exp"


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
        ordering = ['-season', 'team__school']
    
    def __str__(self):
        conf_str = " (Conf)" if self.is_conference_only else ""
        return f"{self.team.school} ({self.season}){conf_str} Misc Stats"


# ============== ML Prediction Models ==============

class MLModelVersion(models.Model):
    """Track trained ML model versions."""
    
    version = models.CharField(max_length=50, unique=True)
    model_file_path = models.CharField(max_length=500)  # Path to .pkl file
    training_date = models.DateTimeField()
    training_games_count = models.IntegerField()
    test_accuracy = models.FloatField()
    test_log_loss = models.FloatField()
    feature_list = models.JSONField()  # List of feature names used
    hyperparameters = models.JSONField()  # XGBoost params
    is_active = models.BooleanField(default=False)  # Only one active at a time
    notes = models.TextField(blank=True)  # Optional notes about this version
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ml_model_versions'
        ordering = ['-training_date']
    
    def __str__(self):
        active_str = " (ACTIVE)" if self.is_active else ""
        return f"ML Model {self.version}{active_str} - {self.test_accuracy:.2%} accuracy"
    
    def activate(self):
        """Activate this model and deactivate all others."""
        MLModelVersion.objects.exclude(pk=self.pk).update(is_active=False)
        self.is_active = True
        self.save()


class MLPrediction(models.Model):
    """ML model predictions for games."""
    
    game = models.OneToOneField(
        Game,
        on_delete=models.CASCADE,
        related_name='ml_prediction'
    )
    
    # Predictions
    home_win_probability = models.FloatField()  # 0.0 to 1.0
    predicted_home_score = models.FloatField()
    predicted_away_score = models.FloatField()
    predicted_margin = models.FloatField()  # home_score - away_score
    
    # Confidence metrics
    confidence_score = models.FloatField()  # Model confidence (0-1)
    
    # Model metadata
    model_version = models.CharField(max_length=50)  # e.g., "v1.0.0"
    model_features_hash = models.CharField(max_length=64, blank=True)  # Hash of feature set used
    
    # Key feature values (for debugging/analysis)
    home_adj_em = models.FloatField(null=True, blank=True)
    away_adj_em = models.FloatField(null=True, blank=True)
    home_momentum = models.FloatField(null=True, blank=True)
    away_momentum = models.FloatField(null=True, blank=True)
    venue_hca = models.FloatField(null=True, blank=True)
    efg_mismatch = models.FloatField(null=True, blank=True)
    to_mismatch = models.FloatField(null=True, blank=True)
    
    # Full feature set (for detailed analysis)
    features_json = models.JSONField(null=True, blank=True)  # All features used
    
    # Timestamps
    predicted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ml_predictions'
        ordering = ['-predicted_at']
        indexes = [
            models.Index(fields=['game', 'predicted_at']),
            models.Index(fields=['model_version']),
            models.Index(fields=['home_win_probability']),
        ]
    
    def __str__(self):
        prob_str = f"{self.home_win_probability:.1%}"
        return f"{self.game} - Home win: {prob_str}"
    
    @property
    def predicted_winner(self):
        """Return the predicted winner team."""
        return self.game.home_team if self.home_win_probability > 0.5 else self.game.away_team
    
    @property
    def prediction_correct(self):
        """Check if prediction was correct (only for final games)."""
        if not self.game.is_final:
            return None
        actual_winner = self.game.winner
        return self.predicted_winner == actual_winner


# ============== Player & Injury Models ==============

class Player(models.Model):
    """Individual player on a team roster."""
    
    POSITION_CHOICES = [
        ('G', 'Guard'),
        ('PG', 'Point Guard'),
        ('SG', 'Shooting Guard'),
        ('F', 'Forward'),
        ('SF', 'Small Forward'),
        ('PF', 'Power Forward'),
        ('C', 'Center'),
        ('G/F', 'Guard/Forward'),
        ('F/C', 'Forward/Center'),
    ]
    
    CLASS_CHOICES = [
        ('FR', 'Freshman'),
        ('SO', 'Sophomore'),
        ('JR', 'Junior'),
        ('SR', 'Senior'),
        ('GR', 'Graduate'),
    ]
    
    # IDs
    ncaa_player_id = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Basic info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    jersey_number = models.CharField(max_length=5, blank=True)
    position = models.CharField(max_length=10, choices=POSITION_CHOICES, blank=True)
    height = models.CharField(max_length=10, blank=True)  # e.g., "6-5"
    weight = models.IntegerField(null=True, blank=True)  # lbs
    year = models.CharField(max_length=5, choices=CLASS_CHOICES, blank=True)
    
    # Team relationship
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='players'
    )
    season = models.IntegerField(default=2026)  # Current season
    is_active = models.BooleanField(default=True)
    
    # Role tracking
    is_starter = models.BooleanField(default=False)
    is_key_player = models.BooleanField(default=False)  # Top 5 minutes player
    avg_minutes = models.FloatField(null=True, blank=True)  # Season avg
    avg_points = models.FloatField(null=True, blank=True)  # Season avg
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'players'
        ordering = ['team', '-avg_minutes']
        indexes = [
            models.Index(fields=['team', 'season']),
            models.Index(fields=['ncaa_player_id']),
            models.Index(fields=['last_name', 'first_name']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.team.abbreviation})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class PlayerGameStats(models.Model):
    """Box score stats for a player in a specific game."""
    
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='game_stats'
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='player_stats'
    )
    
    # Playing time
    minutes = models.IntegerField(default=0)
    started = models.BooleanField(default=False)
    dnp = models.BooleanField(default=False)  # Did Not Play
    dnp_reason = models.CharField(max_length=100, blank=True)  # "INJURY", "COACH'S DECISION", etc.
    
    # Scoring
    points = models.IntegerField(default=0)
    field_goals_made = models.IntegerField(default=0)
    field_goals_attempted = models.IntegerField(default=0)
    three_pointers_made = models.IntegerField(default=0)
    three_pointers_attempted = models.IntegerField(default=0)
    free_throws_made = models.IntegerField(default=0)
    free_throws_attempted = models.IntegerField(default=0)
    
    # Rebounding
    offensive_rebounds = models.IntegerField(default=0)
    defensive_rebounds = models.IntegerField(default=0)
    total_rebounds = models.IntegerField(default=0)
    
    # Other stats
    assists = models.IntegerField(default=0)
    steals = models.IntegerField(default=0)
    blocks = models.IntegerField(default=0)
    turnovers = models.IntegerField(default=0)
    fouls = models.IntegerField(default=0)
    plus_minus = models.IntegerField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'player_game_stats'
        unique_together = ['player', 'game']
        ordering = ['-game__date', '-minutes']
        indexes = [
            models.Index(fields=['player', 'game']),
            models.Index(fields=['game', '-minutes']),
        ]
    
    def __str__(self):
        return f"{self.player.full_name} - {self.game} ({self.points}pts, {self.minutes}min)"
    
    @property
    def field_goal_pct(self):
        if self.field_goals_attempted == 0:
            return 0.0
        return self.field_goals_made / self.field_goals_attempted
    
    @property
    def three_point_pct(self):
        if self.three_pointers_attempted == 0:
            return 0.0
        return self.three_pointers_made / self.three_pointers_attempted


class InjuryReport(models.Model):
    """Track player injuries and availability."""
    
    STATUS_CHOICES = [
        ('OUT', 'Out'),
        ('DOUBTFUL', 'Doubtful'),
        ('QUESTIONABLE', 'Questionable'),
        ('PROBABLE', 'Probable'),
        ('AVAILABLE', 'Available'),
        ('DAY_TO_DAY', 'Day-to-Day'),
    ]
    
    DETECTION_CHOICES = [
        ('OFFICIAL', 'Official Report'),
        ('MINUTES_DROP', 'Minutes Drop Detection'),
        ('DNP', 'Did Not Play'),
        ('MANUAL', 'Manual Entry'),
    ]
    
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='injuries'
    )
    
    # Injury details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    injury_type = models.CharField(max_length=100, blank=True)  # "Ankle", "Knee", etc.
    description = models.TextField(blank=True)
    
    # Detection
    detection_method = models.CharField(max_length=20, choices=DETECTION_CHOICES, default='MANUAL')
    detected_game = models.ForeignKey(
        Game,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detected_injuries'
    )
    
    # Timeline
    reported_date = models.DateField()
    expected_return = models.DateField(null=True, blank=True)
    actual_return = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)  # Currently injured
    
    # Impact assessment
    impact_score = models.FloatField(null=True, blank=True)  # 0-10, how much this hurts team
    minutes_before_injury = models.FloatField(null=True, blank=True)  # Avg minutes before injury
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'injury_reports'
        ordering = ['-reported_date', '-impact_score']
        indexes = [
            models.Index(fields=['player', 'is_active']),
            models.Index(fields=['reported_date']),
            models.Index(fields=['status', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.player.full_name} - {self.status} ({self.injury_type or 'Unknown'})"
    
    def calculate_impact(self):
        """Calculate impact score based on player importance."""
        if not self.player.avg_minutes:
            return 0.0
        
        # Base impact on minutes (more minutes = more impact)
        minutes_factor = min(self.player.avg_minutes / 30, 1.0)  # Cap at 30 min
        
        # Bonus for starters and key players
        starter_bonus = 1.5 if self.player.is_starter else 1.0
        key_player_bonus = 1.3 if self.player.is_key_player else 1.0
        
        # Points factor (scorers are more impactful)
        points_factor = 1.0
        if self.player.avg_points:
            points_factor = min(self.player.avg_points / 15, 1.5)  # Cap at 15 ppg
        
        impact = minutes_factor * starter_bonus * key_player_bonus * points_factor * 10
        return round(min(impact, 10.0), 2)  # Cap at 10


class TeamSeasonStats(models.Model):
    """Aggregated raw team statistics for a season (separate from KenPom)."""
    
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='raw_season_stats'
    )
    season = models.IntegerField()
    
    # Record
    games_played = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    
    # Scoring (totals)
    total_points = models.IntegerField(default=0)
    total_points_allowed = models.IntegerField(default=0)
    
    # Shooting (totals)
    field_goals_made = models.IntegerField(default=0)
    field_goals_attempted = models.IntegerField(default=0)
    three_pointers_made = models.IntegerField(default=0)
    three_pointers_attempted = models.IntegerField(default=0)
    free_throws_made = models.IntegerField(default=0)
    free_throws_attempted = models.IntegerField(default=0)
    
    # Rebounding (totals)
    offensive_rebounds = models.IntegerField(default=0)
    defensive_rebounds = models.IntegerField(default=0)
    total_rebounds = models.IntegerField(default=0)
    
    # Other stats (totals)
    assists = models.IntegerField(default=0)
    steals = models.IntegerField(default=0)
    blocks = models.IntegerField(default=0)
    turnovers = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'team_season_stats'
        unique_together = ['team', 'season']
        ordering = ['-season', 'team__school']
    
    def __str__(self):
        return f"{self.team.school} ({self.season}) Raw Stats"
    
    # Calculated per-game properties
    @property
    def ppg(self):
        return round(self.total_points / self.games_played, 1) if self.games_played else 0
    
    @property
    def opp_ppg(self):
        return round(self.total_points_allowed / self.games_played, 1) if self.games_played else 0
    
    @property
    def fg_pct(self):
        if self.field_goals_attempted == 0:
            return 0.0
        return round(self.field_goals_made / self.field_goals_attempted * 100, 1)
    
    @property
    def three_pct(self):
        if self.three_pointers_attempted == 0:
            return 0.0
        return round(self.three_pointers_made / self.three_pointers_attempted * 100, 1)
    
    @property
    def ft_pct(self):
        if self.free_throws_attempted == 0:
            return 0.0
        return round(self.free_throws_made / self.free_throws_attempted * 100, 1)
    
    @property
    def rpg(self):
        return round(self.total_rebounds / self.games_played, 1) if self.games_played else 0
    
    @property
    def apg(self):
        return round(self.assists / self.games_played, 1) if self.games_played else 0
    
    @property
    def spg(self):
        return round(self.steals / self.games_played, 1) if self.games_played else 0
    
    @property
    def bpg(self):
        return round(self.blocks / self.games_played, 1) if self.games_played else 0
    
    @property
    def topg(self):
        return round(self.turnovers / self.games_played, 1) if self.games_played else 0
