"""Django admin configuration for basketball models."""
from django.contrib import admin
from .models import (
    Conference, Venue, Team, Game, TeamStats, FavoriteTeam, MatchupPrediction,
    KenPomTeam, KenPomRating, KenPomRatingArchive, KenPomFourFactors,
    KenPomFanMatch, KenPomHeight, KenPomMiscStats,
    MLModelVersion, MLPrediction
)


@admin.register(Conference)
class ConferenceAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation']
    search_fields = ['name', 'abbreviation']
    ordering = ['name']


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'state', 'capacity', 'source_id']
    search_fields = ['name', 'city']
    list_filter = ['state']
    ordering = ['name']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['school', 'abbreviation', 'conference', 'mascot']
    search_fields = ['school', 'abbreviation', 'display_name']
    list_filter = ['conference']
    ordering = ['school']
    raw_id_fields = ['conference', 'venue']


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['date', 'away_team', 'home_team', 'away_score', 'home_score', 'status']
    search_fields = ['home_team__school', 'away_team__school', 'ncaa_game_id']
    list_filter = ['status', 'season', 'season_type', 'date']
    ordering = ['-date', '-time']
    raw_id_fields = ['home_team', 'away_team', 'venue']
    date_hierarchy = 'date'


@admin.register(TeamStats)
class TeamStatsAdmin(admin.ModelAdmin):
    list_display = ['team', 'season', 'record', 'conference_record', 'points_per_game']
    search_fields = ['team__school']
    list_filter = ['season']
    ordering = ['-season', 'team__school']
    raw_id_fields = ['team']


@admin.register(FavoriteTeam)
class FavoriteTeamAdmin(admin.ModelAdmin):
    list_display = ['user', 'team', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'team__school']
    raw_id_fields = ['user', 'team']


@admin.register(MatchupPrediction)
class MatchupPredictionAdmin(admin.ModelAdmin):
    list_display = ['user', 'game', 'predicted_winner', 'is_correct', 'checked_at', 'created_at']
    list_filter = ['is_correct', 'checked_at', 'created_at']
    search_fields = ['user__email', 'game__home_team__school', 'game__away_team__school', 'predicted_winner__school']
    raw_id_fields = ['user', 'game', 'predicted_winner']


# ============== KenPom Admin ==============

@admin.register(KenPomTeam)
class KenPomTeamAdmin(admin.ModelAdmin):
    list_display = ['team', 'kenpom_team_id', 'kenpom_team_name', 'matched_at', 'last_verified']
    search_fields = ['team__school', 'kenpom_team_name']
    raw_id_fields = ['team']
    ordering = ['team__school']


@admin.register(KenPomRating)
class KenPomRatingAdmin(admin.ModelAdmin):
    list_display = ['team', 'season', 'rank_adj_em', 'adj_em', 'adj_oe', 'adj_de', 'wins', 'losses']
    search_fields = ['team__school']
    list_filter = ['season']
    ordering = ['rank_adj_em']
    raw_id_fields = ['team']


@admin.register(KenPomRatingArchive)
class KenPomRatingArchiveAdmin(admin.ModelAdmin):
    list_display = ['team', 'season', 'archive_date', 'is_preseason', 'rank_adj_em', 'adj_em']
    search_fields = ['team__school']
    list_filter = ['season', 'is_preseason', 'archive_date']
    ordering = ['-archive_date', 'rank_adj_em']
    raw_id_fields = ['team']
    date_hierarchy = 'archive_date'


@admin.register(KenPomFourFactors)
class KenPomFourFactorsAdmin(admin.ModelAdmin):
    list_display = ['team', 'season', 'is_conference_only', 'efg_pct', 'to_pct', 'or_pct', 'ft_rate']
    search_fields = ['team__school']
    list_filter = ['season', 'is_conference_only']
    ordering = ['-season', 'team__school']
    raw_id_fields = ['team']


@admin.register(KenPomFanMatch)
class KenPomFanMatchAdmin(admin.ModelAdmin):
    list_display = ['date', 'away_team', 'home_team', 'home_win_probability', 'predicted_margin', 'thrill_score']
    search_fields = ['home_team__school', 'away_team__school']
    list_filter = ['season', 'date']
    ordering = ['-date']
    raw_id_fields = ['home_team', 'away_team', 'game']
    date_hierarchy = 'date'


@admin.register(KenPomHeight)
class KenPomHeightAdmin(admin.ModelAdmin):
    list_display = ['team', 'season', 'avg_height', 'effective_height', 'experience', 'bench_strength', 'continuity']
    search_fields = ['team__school']
    list_filter = ['season']
    ordering = ['-season', 'team__school']
    raw_id_fields = ['team']


@admin.register(KenPomMiscStats)
class KenPomMiscStatsAdmin(admin.ModelAdmin):
    list_display = ['team', 'season', 'is_conference_only', 'fg3_pct', 'fg2_pct', 'ft_pct', 'adj_oe', 'adj_de']
    search_fields = ['team__school']
    list_filter = ['season', 'is_conference_only']
    ordering = ['-season', 'team__school']
    raw_id_fields = ['team']


# ============== ML Prediction Admin ==============

@admin.register(MLModelVersion)
class MLModelVersionAdmin(admin.ModelAdmin):
    list_display = ['version', 'is_active', 'test_accuracy', 'test_log_loss', 'training_games_count', 'training_date']
    list_filter = ['is_active', 'training_date']
    search_fields = ['version']
    ordering = ['-training_date']
    readonly_fields = ['training_date', 'created_at']
    
    actions = ['activate_model']
    
    def activate_model(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one model to activate.", level='error')
            return
        model = queryset.first()
        model.activate()
        self.message_user(request, f"Model {model.version} activated.")
    activate_model.short_description = "Activate selected model"


@admin.register(MLPrediction)
class MLPredictionAdmin(admin.ModelAdmin):
    list_display = ['game', 'home_win_probability', 'predicted_margin', 'confidence_score', 'model_version', 'predicted_at']
    list_filter = ['model_version', 'predicted_at']
    search_fields = ['game__home_team__school', 'game__away_team__school']
    ordering = ['-predicted_at']
    raw_id_fields = ['game']
    readonly_fields = ['predicted_at', 'updated_at']
