"""
Django management command to sync box scores and player stats from NCAA API.
This populates Player, PlayerGameStats, and TeamSeasonStats.

Usage: 
    python manage.py sync_box_scores
    python manage.py sync_box_scores --days=7
    python manage.py sync_box_scores --game-id=6505927
"""
import requests
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from basketball.models import (
    Team, Game, Player, PlayerGameStats, TeamSeasonStats, InjuryReport
)


NCAA_API_BASE = 'https://ncaa-api.henrygd.me'


class Command(BaseCommand):
    help = 'Sync box scores and player stats from NCAA API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Number of days to sync (default: 3)'
        )
        parser.add_argument(
            '--game-id',
            type=str,
            help='Sync specific game by NCAA game ID'
        )
        parser.add_argument(
            '--detect-injuries',
            action='store_true',
            default=True,
            help='Detect potential injuries from minutes drops'
        )
        parser.add_argument(
            '--season',
            type=int,
            default=2026,
            help='Season year (default: 2026)'
        )

    def handle(self, *args, **options):
        season = options['season']
        detect_injuries = options['detect_injuries']
        
        if options.get('game_id'):
            # Sync specific game
            self.sync_game_box_score(options['game_id'], season, detect_injuries)
        else:
            # Sync all games in date range
            days = options['days']
            self.sync_date_range(days, season, detect_injuries)
        
        # Update team season stats
        self.update_team_season_stats(season)
        
        self.stdout.write(self.style.SUCCESS('Box score sync completed!'))

    def sync_date_range(self, days, season, detect_injuries):
        """Sync box scores for games in the last N days."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        self.stdout.write(f'Syncing box scores from {start_date} to {end_date}...')
        
        # Get final games in date range
        games = Game.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            status='final'
        ).exclude(ncaa_game_id__isnull=True).exclude(ncaa_game_id='')
        
        self.stdout.write(f'  Found {games.count()} final games to sync')
        
        synced = 0
        errors = 0
        
        for game in games:
            try:
                self.sync_game_box_score(game.ncaa_game_id, season, detect_injuries, game)
                synced += 1
            except Exception as e:
                self.stderr.write(f'  Error syncing game {game.ncaa_game_id}: {e}')
                errors += 1
        
        self.stdout.write(f'  Synced: {synced}, Errors: {errors}')

    def sync_game_box_score(self, ncaa_game_id, season, detect_injuries, game=None):
        """Sync box score for a specific game."""
        url = f'{NCAA_API_BASE}/game/{ncaa_game_id}/boxscore'
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.stderr.write(f'  API error for game {ncaa_game_id}: {e}')
            return
        except ValueError as e:
            self.stderr.write(f'  JSON parse error for game {ncaa_game_id}: {e}')
            return
        
        # Get game from DB if not provided
        if not game:
            game = Game.objects.filter(ncaa_game_id=ncaa_game_id).first()
            if not game:
                self.stderr.write(f'  Game {ncaa_game_id} not in database')
                return
        
        # Process each team's box score
        team_boxscores = data.get('teamBoxscore', [])
        teams_info = data.get('teams', [])
        
        # Build team lookup
        team_id_map = {}
        for team_info in teams_info:
            ncaa_team_id = team_info.get('teamId')
            seoname = team_info.get('seoname', '')
            is_home = team_info.get('isHome', False)
            
            # Find team in our DB
            our_team = self._find_team(seoname, team_info.get('nameShort', ''))
            if our_team:
                team_id_map[int(ncaa_team_id)] = {
                    'team': our_team,
                    'is_home': is_home
                }
        
        with transaction.atomic():
            for box in team_boxscores:
                ncaa_team_id = box.get('teamId')
                team_data = team_id_map.get(ncaa_team_id)
                
                if not team_data:
                    continue
                
                team = team_data['team']
                player_stats = box.get('playerStats', [])
                
                for player_data in player_stats:
                    self._process_player_stats(
                        player_data, team, game, season, detect_injuries
                    )
        
        self.stdout.write(f'  Synced box score for game {ncaa_game_id}')

    def _find_team(self, seoname, short_name):
        """Find team in our database by NCAA slug or name."""
        if seoname:
            team = Team.objects.filter(ncaa_slug__iexact=seoname).first()
            if team:
                return team
        
        if short_name:
            team = Team.objects.filter(short_display_name__iexact=short_name).first()
            if team:
                return team
            team = Team.objects.filter(school__icontains=short_name).first()
            if team:
                return team
        
        return None

    def _process_player_stats(self, player_data, team, game, season, detect_injuries):
        """Process and save player stats from box score."""
        # Extract player info
        ncaa_id = str(player_data.get('id', ''))
        first_name = player_data.get('firstName', '')
        last_name = player_data.get('lastName', '')
        jersey = str(player_data.get('number', ''))
        position = player_data.get('position', '')
        
        if not ncaa_id or not last_name:
            return
        
        # Create unique player ID (team + season + number + name)
        player_key = f"{team.id}_{season}_{jersey}_{last_name}"
        
        # Get or create player
        player, created = Player.objects.update_or_create(
            ncaa_player_id=player_key,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'jersey_number': jersey,
                'position': position,
                'team': team,
                'season': season,
                'is_active': True,
            }
        )
        
        # Parse stats
        minutes_str = player_data.get('minutesPlayed', '0')
        try:
            minutes = int(float(minutes_str)) if minutes_str else 0
        except (ValueError, TypeError):
            minutes = 0
        
        started = player_data.get('starter', False)
        
        # Create or update game stats
        stats_defaults = {
            'minutes': minutes,
            'started': started,
            'dnp': minutes == 0,
            'points': self._safe_int(player_data.get('points')),
            'field_goals_made': self._safe_int(player_data.get('fieldGoalsMade')),
            'field_goals_attempted': self._safe_int(player_data.get('fieldGoalsAttempted')),
            'three_pointers_made': self._safe_int(player_data.get('threePointsMade')),
            'three_pointers_attempted': self._safe_int(player_data.get('threePointsAttempted')),
            'free_throws_made': self._safe_int(player_data.get('freeThrowsMade')),
            'free_throws_attempted': self._safe_int(player_data.get('freeThrowsAttempted')),
            'offensive_rebounds': self._safe_int(player_data.get('offensiveRebounds')),
            'total_rebounds': self._safe_int(player_data.get('totalRebounds')),
            'defensive_rebounds': max(0, self._safe_int(player_data.get('totalRebounds')) - self._safe_int(player_data.get('offensiveRebounds'))),
            'assists': self._safe_int(player_data.get('assists')),
            'steals': self._safe_int(player_data.get('steals')),
            'blocks': self._safe_int(player_data.get('blockedShots')),
            'turnovers': self._safe_int(player_data.get('turnovers')),
            'fouls': self._safe_int(player_data.get('personalFouls')),
        }
        
        PlayerGameStats.objects.update_or_create(
            player=player,
            game=game,
            defaults=stats_defaults
        )
        
        # Update player averages
        self._update_player_averages(player)
        
        # Detect injuries from minutes drop
        if detect_injuries:
            self._detect_injury(player, game, minutes)

    def _safe_int(self, value):
        """Safely convert value to int."""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0

    def _update_player_averages(self, player):
        """Update player's season averages."""
        from django.db.models import Avg
        
        stats = PlayerGameStats.objects.filter(
            player=player,
            game__season=player.season,
            dnp=False
        ).aggregate(
            avg_min=Avg('minutes'),
            avg_pts=Avg('points')
        )
        
        player.avg_minutes = round(stats['avg_min'] or 0, 1)
        player.avg_points = round(stats['avg_pts'] or 0, 1)
        
        # Determine if key player (top 5 by minutes on team)
        top_players = Player.objects.filter(
            team=player.team,
            season=player.season,
            is_active=True
        ).order_by('-avg_minutes')[:5].values_list('id', flat=True)
        
        player.is_key_player = player.id in top_players
        
        # Check if starter (started most recent game)
        recent_game = PlayerGameStats.objects.filter(player=player).order_by('-game__date').first()
        if recent_game:
            player.is_starter = recent_game.started
        
        player.save()

    def _detect_injury(self, player, game, current_minutes):
        """Detect potential injury from minutes drop."""
        if not player.avg_minutes or player.avg_minutes < 10:
            return  # Not enough data or not a significant player
        
        # Check for significant minutes drop
        minutes_drop_pct = (player.avg_minutes - current_minutes) / player.avg_minutes
        
        # Thresholds:
        # - DNP or < 5 min when avg > 20: Likely injured
        # - > 50% drop: Possible injury
        # - > 70% drop: Probable injury
        
        if player.avg_minutes > 20 and current_minutes < 5:
            # Severe drop for regular player
            self._create_injury_report(
                player, game, 
                status='QUESTIONABLE' if current_minutes > 0 else 'OUT',
                detection='MINUTES_DROP' if current_minutes > 0 else 'DNP',
                minutes_before=player.avg_minutes
            )
        elif minutes_drop_pct > 0.7 and player.avg_minutes > 15:
            # Major drop
            self._create_injury_report(
                player, game,
                status='QUESTIONABLE',
                detection='MINUTES_DROP',
                minutes_before=player.avg_minutes
            )
        elif minutes_drop_pct > 0.5 and player.avg_minutes > 20:
            # Significant drop for starter
            self._create_injury_report(
                player, game,
                status='DAY_TO_DAY',
                detection='MINUTES_DROP',
                minutes_before=player.avg_minutes
            )

    def _create_injury_report(self, player, game, status, detection, minutes_before):
        """Create or update injury report for player."""
        # Check if active injury already exists
        existing = InjuryReport.objects.filter(
            player=player,
            is_active=True
        ).first()
        
        if existing:
            # Update existing if this is more severe
            severity_order = ['AVAILABLE', 'PROBABLE', 'DAY_TO_DAY', 'QUESTIONABLE', 'DOUBTFUL', 'OUT']
            if severity_order.index(status) > severity_order.index(existing.status):
                existing.status = status
                existing.detected_game = game
                existing.save()
                self.stdout.write(f'    Updated injury: {player.full_name} -> {status}')
        else:
            # Create new injury report
            injury = InjuryReport.objects.create(
                player=player,
                status=status,
                detection_method=detection,
                detected_game=game,
                reported_date=game.date,
                is_active=True,
                minutes_before_injury=minutes_before,
            )
            injury.impact_score = injury.calculate_impact()
            injury.save()
            self.stdout.write(f'    Detected injury: {player.full_name} - {status} (impact: {injury.impact_score})')

    def update_team_season_stats(self, season):
        """Update aggregated team season stats from box scores."""
        self.stdout.write('Updating team season stats...')
        
        from django.db.models import Sum, Count
        
        # Get all teams with players
        teams_with_data = Team.objects.filter(
            players__season=season
        ).distinct()
        
        for team in teams_with_data:
            # Aggregate from player game stats
            team_stats = PlayerGameStats.objects.filter(
                player__team=team,
                game__season=season
            ).aggregate(
                total_pts=Sum('points'),
                total_fgm=Sum('field_goals_made'),
                total_fga=Sum('field_goals_attempted'),
                total_3pm=Sum('three_pointers_made'),
                total_3pa=Sum('three_pointers_attempted'),
                total_ftm=Sum('free_throws_made'),
                total_fta=Sum('free_throws_attempted'),
                total_oreb=Sum('offensive_rebounds'),
                total_dreb=Sum('defensive_rebounds'),
                total_reb=Sum('total_rebounds'),
                total_ast=Sum('assists'),
                total_stl=Sum('steals'),
                total_blk=Sum('blocks'),
                total_to=Sum('turnovers'),
            )
            
            # Get game count for this team
            from django.db.models import Q as DQ
            games = Game.objects.filter(
                status='final',
                season=season
            ).filter(
                DQ(home_team=team) | DQ(away_team=team)
            )
            
            # Get points allowed (from opponent stats in those games)
            games_played = games.count()
            
            if games_played == 0:
                continue
            
            # Get team's record (winner is a property, not a field)
            wins = 0
            for game in games:
                if game.home_team == team and (game.home_score or 0) > (game.away_score or 0):
                    wins += 1
                elif game.away_team == team and (game.away_score or 0) > (game.home_score or 0):
                    wins += 1
            losses = games_played - wins
            
            # Calculate points allowed
            pts_allowed = 0
            for game in games:
                if game.home_team == team:
                    pts_allowed += game.away_score or 0
                else:
                    pts_allowed += game.home_score or 0
            
            TeamSeasonStats.objects.update_or_create(
                team=team,
                season=season,
                defaults={
                    'games_played': games_played,
                    'wins': wins,
                    'losses': losses,
                    'total_points': team_stats['total_pts'] or 0,
                    'total_points_allowed': pts_allowed,
                    'field_goals_made': team_stats['total_fgm'] or 0,
                    'field_goals_attempted': team_stats['total_fga'] or 0,
                    'three_pointers_made': team_stats['total_3pm'] or 0,
                    'three_pointers_attempted': team_stats['total_3pa'] or 0,
                    'free_throws_made': team_stats['total_ftm'] or 0,
                    'free_throws_attempted': team_stats['total_fta'] or 0,
                    'offensive_rebounds': team_stats['total_oreb'] or 0,
                    'defensive_rebounds': team_stats['total_dreb'] or 0,
                    'total_rebounds': team_stats['total_reb'] or 0,
                    'assists': team_stats['total_ast'] or 0,
                    'steals': team_stats['total_stl'] or 0,
                    'blocks': team_stats['total_blk'] or 0,
                    'turnovers': team_stats['total_to'] or 0,
                }
            )
        
        self.stdout.write(f'  Updated stats for {teams_with_data.count()} teams')
