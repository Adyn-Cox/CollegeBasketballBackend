"""
Feature engineering module for ML predictions.

This module contains all feature extraction logic for the XGBoost prediction model.
Features are designed based on the priority roadmap:
1. Opponent-adjusted momentum (+2-4% accuracy)
2. Four Factors mismatches (+1-3% accuracy)
3. Venue-specific HCA (+1-2% accuracy)
"""
import math
from datetime import date, timedelta
from typing import Dict, Optional, Any, List
from django.db.models import Q, Avg, Count, F


class FeatureExtractor:
    """Extract features for ML model predictions."""
    
    def __init__(self):
        # Lazy imports to avoid circular dependencies
        self._models_imported = False
    
    def _import_models(self):
        """Lazy import models to avoid circular imports."""
        if not self._models_imported:
            from basketball.models import (
                Team, Game, KenPomRating, KenPomFourFactors,
                KenPomRatingArchive, KenPomHeight,
                Player, PlayerGameStats, InjuryReport, TeamSeasonStats
            )
            self.Team = Team
            self.Game = Game
            self.KenPomRating = KenPomRating
            self.KenPomFourFactors = KenPomFourFactors
            self.KenPomRatingArchive = KenPomRatingArchive
            self.KenPomHeight = KenPomHeight
            self.Player = Player
            self.PlayerGameStats = PlayerGameStats
            self.InjuryReport = InjuryReport
            self.TeamSeasonStats = TeamSeasonStats
            self._models_imported = True
    
    def extract_game_features(
        self, 
        game, 
        prediction_date: Optional[date] = None,
        use_archive: bool = True
    ) -> Dict[str, Any]:
        """
        Extract all features for a game at a specific date.
        
        Args:
            game: Game model instance
            prediction_date: Date to use for feature extraction (defaults to game date)
            use_archive: Use KenPomRatingArchive for point-in-time ratings (prevents leakage)
            
        Returns:
            Dictionary of feature_name -> value for XGBoost
        """
        self._import_models()
        
        if prediction_date is None:
            prediction_date = game.date
        
        home_team = game.home_team
        away_team = game.away_team
        season = game.season
        
        features = {}
        
        # 1. KenPom Features (core ratings) - USE ARCHIVE for point-in-time accuracy
        home_kenpom = self.get_kenpom_features(home_team, season, prediction_date if use_archive else None)
        away_kenpom = self.get_kenpom_features(away_team, season, prediction_date if use_archive else None)
        
        if home_kenpom:
            features.update({f'home_{k}': v for k, v in home_kenpom.items()})
        if away_kenpom:
            features.update({f'away_{k}': v for k, v in away_kenpom.items()})
        
        # Calculate differentials
        if home_kenpom and away_kenpom:
            features['adj_em_diff'] = home_kenpom.get('adj_em', 0) - away_kenpom.get('adj_em', 0)
            features['adj_oe_diff'] = home_kenpom.get('adj_oe', 0) - away_kenpom.get('adj_oe', 0)
            features['adj_de_diff'] = home_kenpom.get('adj_de', 0) - away_kenpom.get('adj_de', 0)
            features['tempo_diff'] = home_kenpom.get('adj_tempo', 0) - away_kenpom.get('adj_tempo', 0)
            features['sos_diff'] = home_kenpom.get('sos', 0) - away_kenpom.get('sos', 0)
            features['rank_diff'] = away_kenpom.get('rank_adj_em', 200) - home_kenpom.get('rank_adj_em', 200)
        
        # 2. Opponent-Adjusted Momentum (Priority #1)
        home_momentum = self.calculate_momentum_opponent_adjusted(home_team, prediction_date)
        away_momentum = self.calculate_momentum_opponent_adjusted(away_team, prediction_date)
        features['home_momentum'] = home_momentum
        features['away_momentum'] = away_momentum
        features['momentum_diff'] = home_momentum - away_momentum
        
        # 3. Four Factors Mismatches (Priority #2)
        ff_mismatches = self.calculate_four_factor_mismatches(home_team, away_team, season)
        features.update(ff_mismatches)
        
        # 4. Venue HCA (Priority #3)
        venue_hca = self.calculate_venue_hca(game)
        features['venue_hca'] = venue_hca
        
        # 5. Recent Form
        home_form = self.get_team_recent_form(home_team, prediction_date)
        away_form = self.get_team_recent_form(away_team, prediction_date)
        features.update({f'home_{k}': v for k, v in home_form.items()})
        features.update({f'away_{k}': v for k, v in away_form.items()})
        
        # 6. Rest Days
        home_rest = self.get_rest_days(home_team, prediction_date)
        away_rest = self.get_rest_days(away_team, prediction_date)
        features['home_rest_days'] = home_rest
        features['away_rest_days'] = away_rest
        features['rest_advantage'] = home_rest - away_rest
        
        # 7. Head-to-Head
        h2h = self.get_head_to_head(home_team, away_team, seasons=3)
        features.update(h2h)
        
        # 8. Height/Experience (if available)
        home_height = self.get_height_features(home_team, season)
        away_height = self.get_height_features(away_team, season)
        if home_height:
            features.update({f'home_{k}': v for k, v in home_height.items()})
        if away_height:
            features.update({f'away_{k}': v for k, v in away_height.items()})
        
        # 9. Conference strength
        features['home_conf_strength'] = self._get_conference_strength(home_team, season)
        features['away_conf_strength'] = self._get_conference_strength(away_team, season)
        
        # 10. Apply home court advantage to adj_em_diff
        if 'adj_em_diff' in features:
            features['adj_em_diff_with_hca'] = features['adj_em_diff'] + venue_hca
        
        # 11. Injury Impact (NEW!)
        home_injury = self.get_injury_impact(home_team, prediction_date)
        away_injury = self.get_injury_impact(away_team, prediction_date)
        features.update({f'home_{k}': v for k, v in home_injury.items()})
        features.update({f'away_{k}': v for k, v in away_injury.items()})
        features['injury_impact_diff'] = home_injury.get('injury_impact', 0) - away_injury.get('injury_impact', 0)
        
        # 12. Raw Team Stats (shooting, rebounding)
        home_raw = self.get_raw_team_stats(home_team, season)
        away_raw = self.get_raw_team_stats(away_team, season)
        features.update({f'home_{k}': v for k, v in home_raw.items()})
        features.update({f'away_{k}': v for k, v in away_raw.items()})
        
        # Calculate shooting differentials
        if home_raw and away_raw:
            features['fg_pct_diff'] = home_raw.get('fg_pct', 0) - away_raw.get('fg_pct', 0)
            features['three_pct_diff'] = home_raw.get('three_pct', 0) - away_raw.get('three_pct', 0)
            features['rpg_diff'] = home_raw.get('rpg', 0) - away_raw.get('rpg', 0)
        
        # 13. Player Usage/Impact Features (KEY EDGE from box score data!)
        home_player = self.get_player_impact_features(home_team, prediction_date)
        away_player = self.get_player_impact_features(away_team, prediction_date)
        features.update({f'home_{k}': v for k, v in home_player.items()})
        features.update({f'away_{k}': v for k, v in away_player.items()})
        features['star_minutes_diff'] = home_player.get('star_minutes_pct', 0) - away_player.get('star_minutes_pct', 0)
        features['depth_diff'] = home_player.get('depth_score', 0) - away_player.get('depth_score', 0)
        
        # 14. Travel/Altitude Features
        travel = self.get_travel_features(game)
        features.update(travel)
        
        return features
    
    def get_kenpom_features(
        self, 
        team, 
        season: int, 
        as_of_date: Optional[date] = None
    ) -> Dict[str, float]:
        """
        Get KenPom ratings for a team.
        
        Args:
            team: Team model instance
            season: Season year
            as_of_date: Get ratings as of this date (for historical analysis)
            
        Returns:
            Dictionary of KenPom features
        """
        self._import_models()
        
        # Try to get archived rating for specific date
        if as_of_date:
            archive = self.KenPomRatingArchive.objects.filter(
                team=team,
                season=season,
                archive_date__lte=as_of_date
            ).order_by('-archive_date').first()
            
            if archive:
                return {
                    'adj_em': archive.adj_em,
                    'rank_adj_em': archive.rank_adj_em,
                    'adj_oe': archive.adj_oe,
                    'rank_adj_oe': archive.rank_adj_oe,
                    'adj_de': archive.adj_de,
                    'rank_adj_de': archive.rank_adj_de,
                    'adj_tempo': archive.adj_tempo,
                    'rank_adj_tempo': archive.rank_adj_tempo,
                }
        
        # Fall back to current rating
        rating = self.KenPomRating.objects.filter(
            team=team,
            season=season
        ).first()
        
        if not rating:
            return {}
        
        return {
            'adj_em': rating.adj_em,
            'rank_adj_em': rating.rank_adj_em,
            'adj_oe': rating.adj_oe,
            'rank_adj_oe': rating.rank_adj_oe,
            'adj_de': rating.adj_de,
            'rank_adj_de': rating.rank_adj_de,
            'adj_tempo': rating.adj_tempo,
            'rank_adj_tempo': rating.rank_adj_tempo,
            'tempo': rating.tempo,
            'rank_tempo': rating.rank_tempo,
            'luck': rating.luck,
            'rank_luck': rating.rank_luck,
            'sos': rating.sos,
            'rank_sos': rating.rank_sos,
            'pythag': rating.pythag,
            'rank_pythag': rating.rank_pythag,
        }
    
    def calculate_momentum_opponent_adjusted(
        self, 
        team, 
        as_of_date: date,
        lookback_days: int = 14
    ) -> float:
        """
        Calculate opponent-adjusted momentum for a team.
        
        Weight recent games by opponent strength:
        - Top-25 teams (AdjEM > 15): 2.0x weight
        - Good teams (10-15): 1.8x weight
        - Average teams (5-10): 1.3x weight
        - Below average (0-5): 1.0x weight
        - Bad teams (< 0): 0.6x weight
        
        Exponential decay: more recent games matter more (0.93^days_ago)
        
        Args:
            team: Team model instance
            as_of_date: Calculate momentum as of this date
            lookback_days: Number of days to look back
            
        Returns:
            Momentum score (typically -2 to +2)
        """
        self._import_models()
        
        start_date = as_of_date - timedelta(days=lookback_days)
        
        # Get recent games
        recent_games = self.Game.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            date__gte=start_date,
            date__lt=as_of_date,
            status='final'
        ).order_by('date')
        
        if not recent_games.exists():
            return 0.0
        
        momentum_component = 0.0
        weight_sum = 0.0
        
        for game in recent_games:
            # Determine opponent and result
            if game.home_team == team:
                opponent = game.away_team
                is_win = game.winner == team if game.winner else False
            else:
                opponent = game.home_team
                is_win = game.winner == team if game.winner else False
            
            # Get opponent's KenPom rating
            opp_rating = self.KenPomRating.objects.filter(
                team=opponent,
                season=game.season
            ).first()
            
            if not opp_rating:
                # Default weight if no rating
                opponent_weight = 1.0
            else:
                opp_adj_em = opp_rating.adj_em
                
                # Weight by opponent strength
                if opp_adj_em > 15:
                    opponent_weight = 2.0
                elif opp_adj_em > 10:
                    opponent_weight = 1.8
                elif opp_adj_em > 5:
                    opponent_weight = 1.3
                elif opp_adj_em > 0:
                    opponent_weight = 1.0
                else:
                    opponent_weight = 0.6
            
            # Exponential decay for recency
            days_ago = (as_of_date - game.date).days
            recency_decay = 0.93 ** days_ago
            
            # Combine weights
            total_weight = opponent_weight * recency_decay
            
            # Momentum contribution: win = +1, loss = -0.5
            momentum_contribution = (1.0 if is_win else -0.5) * total_weight
            
            momentum_component += momentum_contribution
            weight_sum += total_weight
        
        # Normalize
        if weight_sum == 0:
            return 0.0
        
        # Scale to roughly AdjEM points
        momentum = momentum_component / weight_sum * 2
        
        return round(momentum, 3)
    
    def calculate_four_factor_mismatches(
        self, 
        home_team, 
        away_team, 
        season: int
    ) -> Dict[str, float]:
        """
        Calculate Four Factors mismatches between teams.
        
        Exploitative mismatches (what actually matters):
        - eFG% edge: Your eFG% vs their allowed eFG%
        - TO pressure: Their TO forced vs your TOs
        - Rebounding edge: Your OR% vs their DR%
        - FT rate edge: Your FT rate vs their allowed
        
        Args:
            home_team: Home team model instance
            away_team: Away team model instance
            season: Season year
            
        Returns:
            Dictionary of mismatch features
        """
        self._import_models()
        
        home_ff = self.KenPomFourFactors.objects.filter(
            team=home_team,
            season=season,
            is_conference_only=False
        ).first()
        
        away_ff = self.KenPomFourFactors.objects.filter(
            team=away_team,
            season=season,
            is_conference_only=False
        ).first()
        
        if not home_ff or not away_ff:
            return {
                'efg_mismatch': 0.0,
                'to_mismatch': 0.0,
                'or_mismatch': 0.0,
                'ftr_mismatch': 0.0,
                'efg_interaction': 0.0,
                'to_interaction': 0.0,
            }
        
        # Get AdjEM diff for interaction terms
        home_rating = self.KenPomRating.objects.filter(team=home_team, season=season).first()
        away_rating = self.KenPomRating.objects.filter(team=away_team, season=season).first()
        
        adj_em_diff = 0.0
        if home_rating and away_rating:
            adj_em_diff = home_rating.adj_em - away_rating.adj_em
        
        # EXPLOITATIVE MISMATCHES
        
        # 1. Shooting edge: Home eFG% vs Away allowed eFG%
        efg_shooting_edge = home_ff.efg_pct - away_ff.defg_pct
        
        # 2. Turnover pressure: Away TO forced vs Home TOs
        to_pressure_edge = away_ff.dto_pct - home_ff.to_pct
        
        # 3. Rebounding edge: Home OR% vs Away DR%
        # DOR_pct is defensive rebounding %, so 100 - DOR_pct is what they allow
        or_rebounding_edge = home_ff.or_pct - (100 - away_ff.dor_pct)
        
        # 4. FT rate edge: Home FT rate vs Away allowed
        ftr_edge = home_ff.ft_rate - away_ff.dft_rate
        
        # INTERACTION TERMS
        
        # Shooting mismatch is HUGE in close games, less in blowouts
        efg_interaction = efg_shooting_edge * (1.0 if abs(adj_em_diff) < 5 else 0.5)
        
        # Turnover pressure helps underdog more
        to_interaction = to_pressure_edge * (1.2 if adj_em_diff < 0 else 0.8)
        
        return {
            'efg_mismatch': round(efg_shooting_edge, 2),
            'to_mismatch': round(to_pressure_edge, 2),
            'or_mismatch': round(or_rebounding_edge, 2),
            'ftr_mismatch': round(ftr_edge, 2),
            'efg_interaction': round(efg_interaction, 2),
            'to_interaction': round(to_interaction, 2),
        }
    
    def calculate_venue_hca(self, game) -> float:
        """
        Calculate venue-specific home court advantage.
        
        Learn HCA from historical data at this venue.
        Big arenas (Duke, Kansas): +5-7 AdjEM
        Mid-majors: +2-3 AdjEM
        
        Args:
            game: Game model instance
            
        Returns:
            Home court advantage in AdjEM points (1.5 to 7.0)
        """
        self._import_models()
        
        # Default HCA
        default_hca = 3.5
        
        if not game.venue:
            return default_hca
        
        # Get historical home games at this venue
        home_games = self.Game.objects.filter(
            venue=game.venue,
            status='final'
        ).exclude(pk=game.pk).order_by('-date')[:50]  # Last 50 games
        
        if home_games.count() < 10:
            return default_hca
        
        # Calculate home win rate
        home_wins = 0
        total_games = 0
        
        for g in home_games:
            if g.winner:
                total_games += 1
                if g.winner == g.home_team:
                    home_wins += 1
        
        if total_games < 10:
            return default_hca
        
        win_pct = home_wins / total_games
        
        # Convert win % to AdjEM advantage
        # 50% win rate = 0 HCA, 70% = ~5 HCA, 80% = ~7 HCA
        hca = (win_pct - 0.5) * 20  # Scale factor
        
        # Clamp between 1.5 and 7.0
        hca = max(1.5, min(7.0, hca + default_hca))
        
        return round(hca, 2)
    
    def get_team_recent_form(
        self, 
        team, 
        as_of_date: date,
        games: int = 10
    ) -> Dict[str, float]:
        """
        Get team's recent form (win/loss record).
        
        Args:
            team: Team model instance
            as_of_date: Calculate form as of this date
            games: Number of recent games to consider
            
        Returns:
            Dictionary with win_pct, wins, losses
        """
        self._import_models()
        
        recent_games = self.Game.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            date__lt=as_of_date,
            status='final'
        ).order_by('-date')[:games]
        
        wins = 0
        losses = 0
        
        for game in recent_games:
            if game.winner == team:
                wins += 1
            else:
                losses += 1
        
        total = wins + losses
        win_pct = wins / total if total > 0 else 0.5
        
        return {
            'recent_win_pct': round(win_pct, 3),
            'recent_wins': wins,
            'recent_losses': losses,
        }
    
    def get_rest_days(self, team, game_date: date) -> int:
        """
        Get number of rest days before a game.
        
        Args:
            team: Team model instance
            game_date: Date of the game
            
        Returns:
            Number of days since last game (capped at 14)
        """
        self._import_models()
        
        last_game = self.Game.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            date__lt=game_date,
            status='final'
        ).order_by('-date').first()
        
        if not last_game:
            return 7  # Default if no previous game found
        
        rest_days = (game_date - last_game.date).days
        
        # Cap at 14 days
        return min(rest_days, 14)
    
    def get_head_to_head(
        self, 
        team_a, 
        team_b, 
        seasons: int = 3
    ) -> Dict[str, float]:
        """
        Get head-to-head record between two teams.
        
        Args:
            team_a: First team (typically home)
            team_b: Second team (typically away)
            seasons: Number of seasons to look back
            
        Returns:
            Dictionary with H2H stats
        """
        self._import_models()
        
        from datetime import datetime
        current_year = datetime.now().year
        min_season = current_year - seasons
        
        h2h_games = self.Game.objects.filter(
            Q(home_team=team_a, away_team=team_b) | Q(home_team=team_b, away_team=team_a),
            season__gte=min_season,
            status='final'
        ).order_by('-date')
        
        team_a_wins = 0
        team_b_wins = 0
        
        for game in h2h_games:
            if game.winner == team_a:
                team_a_wins += 1
            elif game.winner == team_b:
                team_b_wins += 1
        
        total = team_a_wins + team_b_wins
        
        return {
            'h2h_games': total,
            'h2h_team_a_wins': team_a_wins,
            'h2h_team_b_wins': team_b_wins,
            'h2h_win_pct': team_a_wins / total if total > 0 else 0.5,
        }
    
    def get_height_features(self, team, season: int) -> Dict[str, float]:
        """
        Get height/experience features for a team.
        
        Args:
            team: Team model instance
            season: Season year
            
        Returns:
            Dictionary of height/experience features
        """
        self._import_models()
        
        height = self.KenPomHeight.objects.filter(
            team=team,
            season=season
        ).first()
        
        if not height:
            return {}
        
        return {
            'avg_height': height.avg_height,
            'effective_height': height.effective_height,
            'experience': height.experience,
            'bench_strength': height.bench_strength,
            'continuity': height.continuity,
        }
    
    def _get_conference_strength(self, team, season: int) -> float:
        """
        Get conference strength based on average KenPom rating.
        
        Args:
            team: Team model instance
            season: Season year
            
        Returns:
            Average AdjEM of conference teams
        """
        self._import_models()
        
        if not team.conference:
            return 0.0
        
        conf_ratings = self.KenPomRating.objects.filter(
            team__conference=team.conference,
            season=season
        ).aggregate(avg_adj_em=Avg('adj_em'))
        
        return conf_ratings['avg_adj_em'] or 0.0
    
    def get_injury_impact(self, team, as_of_date: date) -> Dict[str, float]:
        """
        Calculate injury impact on team.
        
        Star player out = major penalty.
        Multiple injuries = compounding effect.
        
        Args:
            team: Team model instance
            as_of_date: Date to check injuries for
            
        Returns:
            Dictionary with injury features:
            - injury_impact: Total impact (0-15 AdjEM equivalent)
            - injuries_count: Number of active injuries
            - star_player_out: Boolean (impact > 5)
            - minutes_lost: Total minutes lost from injuries
        """
        self._import_models()
        
        # Get active injuries for this team
        active_injuries = self.InjuryReport.objects.filter(
            player__team=team,
            is_active=True,
            reported_date__lte=as_of_date
        ).select_related('player')
        
        if not active_injuries.exists():
            return {
                'injury_impact': 0.0,
                'injuries_count': 0,
                'star_player_out': 0,
                'minutes_lost': 0.0,
            }
        
        total_impact = 0.0
        minutes_lost = 0.0
        star_out = False
        
        for injury in active_injuries:
            # Weight by status
            status_weights = {
                'OUT': 1.0,
                'DOUBTFUL': 0.8,
                'QUESTIONABLE': 0.5,
                'DAY_TO_DAY': 0.3,
                'PROBABLE': 0.1,
            }
            status_weight = status_weights.get(injury.status, 0.0)
            
            # Calculate impact
            impact = (injury.impact_score or 0) * status_weight
            total_impact += impact
            
            # Minutes lost
            if injury.minutes_before_injury:
                minutes_lost += injury.minutes_before_injury * status_weight
            
            # Star player check
            if impact > 5:
                star_out = True
        
        # Cap impact at 15 (can't lose more than ~15 AdjEM from injuries)
        total_impact = min(total_impact, 15.0)
        
        return {
            'injury_impact': round(total_impact, 2),
            'injuries_count': active_injuries.count(),
            'star_player_out': 1 if star_out else 0,
            'minutes_lost': round(minutes_lost, 1),
        }
    
    def get_raw_team_stats(self, team, season: int) -> Dict[str, float]:
        """
        Get raw team statistics (actual shooting %, rebounds, etc.).
        
        Args:
            team: Team model instance
            season: Season year
            
        Returns:
            Dictionary with raw stats:
            - ppg: Points per game
            - opp_ppg: Opponent points per game
            - fg_pct: Field goal percentage
            - three_pct: Three point percentage
            - ft_pct: Free throw percentage
            - rpg: Rebounds per game
            - apg: Assists per game
            - spg: Steals per game
            - bpg: Blocks per game
            - topg: Turnovers per game
        """
        self._import_models()
        
        stats = self.TeamSeasonStats.objects.filter(
            team=team,
            season=season
        ).first()
        
        if not stats:
            return {}
        
        return {
            'ppg': stats.ppg,
            'opp_ppg': stats.opp_ppg,
            'fg_pct': stats.fg_pct,
            'three_pct': stats.three_pct,
            'ft_pct': stats.ft_pct,
            'rpg': stats.rpg,
            'apg': stats.apg,
            'spg': stats.spg,
            'bpg': stats.bpg,
            'topg': stats.topg,
        }
    
    def get_player_impact_features(
        self, 
        team, 
        as_of_date: date,
        lookback_games: int = 5
    ) -> Dict[str, float]:
        """
        Calculate player usage and impact features from box score data.
        
        This is a KEY EDGE over pure KenPom models - we have actual player minutes!
        
        Features:
        - star_minutes_pct: Top-3 usage players' minutes % (if low, injury/fatigue)
        - depth_score: How much bench is contributing
        - starter_efficiency: Rolling efficiency of starters
        - top_scorer_available: Is the team's leading scorer playing?
        
        Args:
            team: Team model instance
            as_of_date: Calculate as of this date
            lookback_games: Number of recent games to analyze
            
        Returns:
            Dictionary of player impact features
        """
        self._import_models()
        
        # Get recent games
        recent_games = self.Game.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            date__lt=as_of_date,
            status='final'
        ).order_by('-date')[:lookback_games]
        
        if not recent_games.exists():
            return {
                'star_minutes_pct': 0.5,
                'depth_score': 0.5,
                'starter_efficiency': 0.0,
                'bench_minutes_pct': 0.25,
                'top_scorer_available': 1.0,
            }
        
        game_ids = [g.id for g in recent_games]
        
        # Get player stats from recent games
        player_stats = self.PlayerGameStats.objects.filter(
            game_id__in=game_ids,
            player__team=team
        ).select_related('player')
        
        if not player_stats.exists():
            return {
                'star_minutes_pct': 0.5,
                'depth_score': 0.5,
                'starter_efficiency': 0.0,
                'bench_minutes_pct': 0.25,
                'top_scorer_available': 1.0,
            }
        
        # Aggregate stats by player
        from collections import defaultdict
        player_totals = defaultdict(lambda: {
            'minutes': 0, 'points': 0, 'rebounds': 0, 'assists': 0,
            'turnovers': 0, 'games': 0, 'is_starter': False
        })
        
        for stat in player_stats:
            pid = stat.player_id
            player_totals[pid]['minutes'] += stat.minutes or 0
            player_totals[pid]['points'] += stat.points
            player_totals[pid]['rebounds'] += stat.total_rebounds
            player_totals[pid]['assists'] += stat.assists
            player_totals[pid]['turnovers'] += stat.turnovers
            player_totals[pid]['games'] += 1
            player_totals[pid]['is_starter'] = stat.started or player_totals[pid]['is_starter']
        
        # Sort by minutes to find top usage players
        sorted_players = sorted(
            player_totals.items(), 
            key=lambda x: x[1]['minutes'], 
            reverse=True
        )
        
        total_minutes = sum(p[1]['minutes'] for p in sorted_players)
        if total_minutes == 0:
            return {
                'star_minutes_pct': 0.5,
                'depth_score': 0.5,
                'starter_efficiency': 0.0,
                'bench_minutes_pct': 0.25,
                'top_scorer_available': 1.0,
            }
        
        # Top 3 players' minutes percentage
        top3_minutes = sum(p[1]['minutes'] for p in sorted_players[:3])
        star_minutes_pct = top3_minutes / total_minutes if total_minutes > 0 else 0.5
        
        # Bench minutes (players 6+)
        bench_minutes = sum(p[1]['minutes'] for p in sorted_players[5:])
        bench_minutes_pct = bench_minutes / total_minutes if total_minutes > 0 else 0.25
        
        # Depth score: how evenly distributed are minutes? (higher = deeper bench)
        if len(sorted_players) >= 8:
            top5_pct = sum(p[1]['minutes'] for p in sorted_players[:5]) / total_minutes
            depth_score = 1.0 - top5_pct  # More depth = lower reliance on top 5
        else:
            depth_score = 0.3
        
        # Starter efficiency (PER-like): (PTS + REB + AST - TO) per game
        starter_efficiency = 0.0
        starter_count = 0
        for pid, stats in sorted_players[:5]:  # Top 5 assumed starters by minutes
            if stats['games'] > 0:
                per_game = (stats['points'] + stats['rebounds'] + stats['assists'] - stats['turnovers']) / stats['games']
                starter_efficiency += per_game
                starter_count += 1
        
        if starter_count > 0:
            starter_efficiency /= starter_count  # Average per starter
        
        # Check if top scorer played in most recent game
        top_scorer_id = max(player_totals.items(), key=lambda x: x[1]['points'])[0] if player_totals else None
        top_scorer_available = 1.0
        if top_scorer_id and recent_games:
            most_recent_game = recent_games[0]
            top_scorer_in_recent = self.PlayerGameStats.objects.filter(
                game=most_recent_game,
                player_id=top_scorer_id,
                minutes__gt=5
            ).exists()
            top_scorer_available = 1.0 if top_scorer_in_recent else 0.0
        
        return {
            'star_minutes_pct': round(star_minutes_pct, 3),
            'depth_score': round(depth_score, 3),
            'starter_efficiency': round(starter_efficiency, 2),
            'bench_minutes_pct': round(bench_minutes_pct, 3),
            'top_scorer_available': top_scorer_available,
        }
    
    def get_travel_features(self, game) -> Dict[str, float]:
        """
        Calculate travel/fatigue and altitude features.
        
        - altitude_advantage: Home team at high altitude (Colorado, Utah, etc.)
        - travel_fatigue: Long travel for away team
        - timezone_change: Crossing timezones affects performance
        
        Args:
            game: Game model instance
            
        Returns:
            Dictionary of travel features
        """
        self._import_models()
        
        features = {
            'altitude_advantage': 0.0,
            'travel_fatigue': 0.0,
            'timezone_change': 0.0,
            'back_to_back_away': 0.0,
        }
        
        # High-altitude venues (simplified - major ones)
        # Venues > 5000 ft elevation
        high_altitude_teams = {
            'colorado', 'colorado state', 'air force', 'wyoming',
            'utah', 'utah state', 'byu', 'denver',
            'new mexico', 'new mexico state', 'unlv',
            'boise state', 'idaho', 'montana', 'montana state',
        }
        
        venue = game.venue
        home_team = game.home_team
        away_team = game.away_team
        
        # Check if home team is at altitude
        home_name = home_team.school.lower() if home_team else ''
        away_name = away_team.school.lower() if away_team else ''
        
        if any(alt in home_name for alt in high_altitude_teams):
            # Away team coming from sea level to altitude
            if not any(alt in away_name for alt in high_altitude_teams):
                features['altitude_advantage'] = 2.5  # ~2.5 AdjEM advantage
        
        # Check for back-to-back away games
        if away_team:
            two_days_ago = game.date - timedelta(days=2)
            recent_away = self.Game.objects.filter(
                away_team=away_team,
                date__gte=two_days_ago,
                date__lt=game.date,
                status='final'
            ).exists()
            
            if recent_away:
                features['back_to_back_away'] = 1.0
                features['travel_fatigue'] = 1.5  # Penalty
        
        # Simplified timezone approximation (Pacific, Mountain, Central, Eastern)
        # Would need venue geocoding for accuracy
        pacific_teams = {'ucla', 'usc', 'stanford', 'cal', 'oregon', 'oregon state', 
                        'washington', 'washington state', 'arizona', 'arizona state'}
        eastern_teams = {'duke', 'north carolina', 'nc state', 'wake forest', 'virginia',
                        'virginia tech', 'miami', 'florida state', 'clemson', 'georgia tech',
                        'boston college', 'syracuse', 'pittsburgh', 'louisville', 'notre dame'}
        
        home_pacific = any(t in home_name for t in pacific_teams)
        away_pacific = any(t in away_name for t in pacific_teams)
        home_eastern = any(t in home_name for t in eastern_teams)
        away_eastern = any(t in away_name for t in eastern_teams)
        
        # Cross-country travel penalty
        if (home_pacific and away_eastern) or (home_eastern and away_pacific):
            features['timezone_change'] = 1.0  # 3-hour time zone change
            features['travel_fatigue'] += 1.0
        
        return features
    
    def calculate_win_probability(
        self, 
        adj_em_diff: float, 
        include_hca: bool = True
    ) -> float:
        """
        Calculate win probability from AdjEM differential.
        
        Uses log5 formula: P(home wins) = 1 / (1 + 10^(-adj_em_diff / 11))
        
        Args:
            adj_em_diff: Home AdjEM - Away AdjEM
            include_hca: Whether HCA is already included
            
        Returns:
            Win probability for home team (0.0 to 1.0)
        """
        # Add default HCA if not included
        if not include_hca:
            adj_em_diff += 3.5
        
        # Log5 formula
        win_prob = 1 / (1 + math.pow(10, -adj_em_diff / 11))
        
        return round(win_prob, 4)
    
    def predict_score(
        self, 
        home_adj_oe: float, 
        home_adj_de: float,
        away_adj_oe: float, 
        away_adj_de: float,
        tempo: float,
        hca: float = 3.5
    ) -> tuple:
        """
        Predict game score based on efficiency ratings using the KenPom formula.
        
        KenPom Formula:
        Expected_OE = (Team_AdjOE × Opponent_AdjDE) / 100
        Score = Expected_OE × Tempo / 100
        
        Args:
            home_adj_oe: Home team adjusted offensive efficiency
            home_adj_de: Home team adjusted defensive efficiency  
            away_adj_oe: Away team adjusted offensive efficiency
            away_adj_de: Away team adjusted defensive efficiency
            tempo: Expected tempo (possessions per 40 min)
            hca: Home court advantage in points
            
        Returns:
            Tuple of (home_score, away_score)
        """
        # KenPom formula: Expected OE = (Team AdjOE * Opp AdjDE) / 100
        home_expected_oe = (home_adj_oe * away_adj_de) / 100
        away_expected_oe = (away_adj_oe * home_adj_de) / 100
        
        # Convert to expected points: Score = Expected_OE * Tempo / 100
        # Apply half of HCA to each team's score
        home_score = (home_expected_oe * tempo / 100) + (hca / 2)
        away_score = (away_expected_oe * tempo / 100) - (hca / 2)
        
        return round(home_score, 1), round(away_score, 1)
    
    def get_feature_names(self) -> List[str]:
        """
        Get list of all feature names used by the model.
        
        Returns:
            List of feature names in consistent order
        """
        return [
            # KenPom differentials
            'adj_em_diff',
            'adj_em_diff_with_hca',
            'adj_oe_diff',
            'adj_de_diff',
            'tempo_diff',
            'sos_diff',
            'rank_diff',
            
            # Home team KenPom
            'home_adj_em',
            'home_adj_oe',
            'home_adj_de',
            'home_adj_tempo',
            'home_rank_adj_em',
            'home_luck',
            'home_sos',
            'home_pythag',
            
            # Away team KenPom
            'away_adj_em',
            'away_adj_oe',
            'away_adj_de',
            'away_adj_tempo',
            'away_rank_adj_em',
            'away_luck',
            'away_sos',
            'away_pythag',
            
            # Momentum
            'home_momentum',
            'away_momentum',
            'momentum_diff',
            
            # Four Factors
            'efg_mismatch',
            'to_mismatch',
            'or_mismatch',
            'ftr_mismatch',
            'efg_interaction',
            'to_interaction',
            
            # Venue
            'venue_hca',
            
            # Recent form
            'home_recent_win_pct',
            'home_recent_wins',
            'home_recent_losses',
            'away_recent_win_pct',
            'away_recent_wins',
            'away_recent_losses',
            
            # Rest
            'home_rest_days',
            'away_rest_days',
            'rest_advantage',
            
            # H2H
            'h2h_games',
            'h2h_team_a_wins',
            'h2h_team_b_wins',
            'h2h_win_pct',
            
            # Height/Experience
            'home_avg_height',
            'home_effective_height',
            'home_experience',
            'home_bench_strength',
            'home_continuity',
            'away_avg_height',
            'away_effective_height',
            'away_experience',
            'away_bench_strength',
            'away_continuity',
            
            # Conference
            'home_conf_strength',
            'away_conf_strength',
            
            # Injuries (NEW!)
            'home_injury_impact',
            'home_injuries_count',
            'home_star_player_out',
            'home_minutes_lost',
            'away_injury_impact',
            'away_injuries_count',
            'away_star_player_out',
            'away_minutes_lost',
            'injury_impact_diff',
            
            # Raw Stats
            'home_ppg',
            'home_opp_ppg',
            'home_fg_pct',
            'home_three_pct',
            'home_ft_pct',
            'home_rpg',
            'home_apg',
            'away_ppg',
            'away_opp_ppg',
            'away_fg_pct',
            'away_three_pct',
            'away_ft_pct',
            'away_rpg',
            'away_apg',
            'fg_pct_diff',
            'three_pct_diff',
            'rpg_diff',
            
            # Player Usage/Impact (KEY EDGE from box scores!)
            'home_star_minutes_pct',
            'home_depth_score',
            'home_starter_efficiency',
            'home_bench_minutes_pct',
            'home_top_scorer_available',
            'away_star_minutes_pct',
            'away_depth_score',
            'away_starter_efficiency',
            'away_bench_minutes_pct',
            'away_top_scorer_available',
            'star_minutes_diff',
            'depth_diff',
            
            # Travel/Altitude
            'altitude_advantage',
            'travel_fatigue',
            'timezone_change',
            'back_to_back_away',
        ]


# Singleton instance
_feature_extractor = None


def get_feature_extractor() -> FeatureExtractor:
    """Get singleton FeatureExtractor instance."""
    global _feature_extractor
    if _feature_extractor is None:
        _feature_extractor = FeatureExtractor()
    return _feature_extractor
