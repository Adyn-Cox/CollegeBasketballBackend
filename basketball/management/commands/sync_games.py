"""
Django management command to sync games from NCAA API.
Usage: python manage.py sync_games
       python manage.py sync_games --date=2026-01-28
       python manage.py sync_games --days=7
"""
import requests
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from basketball.models import Team, Game, MatchupPrediction


NCAA_API_BASE = 'http://localhost:3005'


class Command(BaseCommand):
    help = 'Sync games from NCAA API for a given date or date range'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date to sync (YYYY-MM-DD format). Defaults to today.'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days to sync starting from --date (default: 1)'
        )
        parser.add_argument(
            '--season',
            type=int,
            default=2026,
            help='Season year (default: 2026)'
        )

    def handle(self, *args, **options):
        # Parse start date
        if options['date']:
            try:
                start_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            start_date = datetime.now().date()
        
        days = options['days']
        season = options['season']
        
        # Build team lookup cache by ncaa_slug
        self.stdout.write('Building team cache by NCAA slug...')
        slug_to_team = {}
        name_to_team = {}
        
        for team in Team.objects.all():
            if team.ncaa_slug:
                slug_to_team[team.ncaa_slug] = team
            # Also index by various name forms for fallback matching
            name_to_team[self.normalize_name(team.school)] = team
            name_to_team[self.normalize_name(team.short_display_name)] = team
        
        self.stdout.write(f'  Cached {len(slug_to_team)} teams with NCAA slugs')
        self.stdout.write(f'  Cached {len(name_to_team)} team name variations')
        
        total_games_created = 0
        total_games_updated = 0
        total_games_skipped = 0
        
        # Sync each day
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            self.stdout.write(f'\nSyncing games for {current_date}...')
            
            created, updated, skipped = self.sync_date(
                current_date, season, slug_to_team, name_to_team
            )
            
            total_games_created += created
            total_games_updated += updated
            total_games_skipped += skipped
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sync completed!'))
        self.stdout.write(f'  Games created: {total_games_created}')
        self.stdout.write(f'  Games updated: {total_games_updated}')
        self.stdout.write(f'  Games skipped (no team match): {total_games_skipped}')
        self.stdout.write(f'  Total games in database: {Game.objects.count()}')

    def normalize_name(self, name):
        """Normalize team name for matching."""
        if not name:
            return ''
        import re
        name = name.lower()
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', '', name)
        return name

    def find_team(self, team_data, slug_to_team, name_to_team):
        """Find team by slug or name."""
        names = team_data.get('names', {})
        seo_slug = names.get('seo', '')
        short_name = names.get('short', '')
        
        # Try slug first
        if seo_slug and seo_slug in slug_to_team:
            return slug_to_team[seo_slug]
        
        # Try name fallback
        normalized = self.normalize_name(short_name)
        if normalized and normalized in name_to_team:
            return name_to_team[normalized]
        
        return None

    def sync_date(self, date, season, slug_to_team, name_to_team):
        """Sync games for a specific date."""
        games_created = 0
        games_updated = 0
        games_skipped = 0
        
        # Build API URL
        url = f'{NCAA_API_BASE}/scoreboard/basketball-men/d1/{date.year}/{date.month:02d}/{date.day:02d}'
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.stderr.write(self.style.WARNING(f'  API error for {date}: {e}'))
            return 0, 0, 0
        except ValueError as e:
            self.stderr.write(self.style.WARNING(f'  JSON parse error for {date}: {e}'))
            return 0, 0, 0
        
        # Extract games from response
        games = data.get('games', [])
        if not games:
            self.stdout.write(f'  No games found for {date}')
            return 0, 0, 0
        
        for game_entry in games:
            try:
                game_data = game_entry.get('game', {})
                
                # Get game ID
                game_id = str(game_data.get('gameID', ''))
                if not game_id:
                    continue
                
                # Get teams
                home_team_data = game_data.get('home', {})
                away_team_data = game_data.get('away', {})
                
                home_team = self.find_team(home_team_data, slug_to_team, name_to_team)
                away_team = self.find_team(away_team_data, slug_to_team, name_to_team)
                
                if not home_team or not away_team:
                    games_skipped += 1
                    continue
                
                # Parse game time
                game_time = None
                time_str = game_data.get('startTime', '')
                if time_str:
                    try:
                        # Parse "2:00 PM ET" format
                        import re
                        match = re.match(r'(\d+):(\d+)\s*(AM|PM)', time_str.upper())
                        if match:
                            hour = int(match.group(1))
                            minute = int(match.group(2))
                            ampm = match.group(3)
                            if ampm == 'PM' and hour != 12:
                                hour += 12
                            elif ampm == 'AM' and hour == 12:
                                hour = 0
                            game_time = datetime.strptime(f'{hour:02d}:{minute:02d}', '%H:%M').time()
                    except Exception:
                        pass
                
                # Get scores (they're strings in the API)
                home_score = home_team_data.get('score', '')
                away_score = away_team_data.get('score', '')
                
                try:
                    home_score = int(home_score) if home_score else None
                except ValueError:
                    home_score = None
                
                try:
                    away_score = int(away_score) if away_score else None
                except ValueError:
                    away_score = None
                
                # Determine status
                game_state = game_data.get('gameState', '').lower()
                current_period = game_data.get('currentPeriod', '')
                
                if game_state == 'final':
                    status = 'final'
                    status_detail = game_data.get('finalMessage', 'Final')
                elif game_state in ['live', 'in', 'inprogress']:
                    status = 'in_progress'
                    status_detail = current_period
                elif game_state == 'postponed':
                    status = 'postponed'
                    status_detail = 'Postponed'
                elif game_state == 'cancelled':
                    status = 'cancelled'
                    status_detail = 'Cancelled'
                else:
                    status = 'scheduled'
                    status_detail = time_str
                
                # Create or update game
                game_defaults = {
                    'date': date,
                    'time': game_time,
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': home_score,
                    'away_score': away_score,
                    'status': status,
                    'status_detail': status_detail,
                    'season': season,
                    'season_type': 'regular',
                }
                
                # Check if game was already final before update
                old_game = Game.objects.filter(ncaa_game_id=game_id).first()
                was_final_before = old_game and old_game.status == 'final'
                
                game, created = Game.objects.update_or_create(
                    ncaa_game_id=game_id,
                    defaults=game_defaults
                )
                
                # Check predictions if game just became final
                if status == 'final' and not was_final_before:
                    self._check_predictions(game)
                
                if created:
                    games_created += 1
                else:
                    games_updated += 1
                    
            except Exception as e:
                self.stderr.write(self.style.WARNING(f'  Error processing game: {e}'))
                continue
        
        self.stdout.write(f'  Processed {len(games)} games: {games_created} created, {games_updated} updated, {games_skipped} skipped')
        return games_created, games_updated, games_skipped
    
    def _check_predictions(self, game):
        """Check all predictions for a finalized game."""
        predictions = MatchupPrediction.objects.filter(
            game=game,
            is_correct__isnull=True  # Only check unchecked predictions
        )
        
        checked_count = 0
        for prediction in predictions:
            if prediction.check_prediction():
                checked_count += 1
        
        if checked_count > 0:
            self.stdout.write(f'    Checked {checked_count} prediction(s) for game {game}')
