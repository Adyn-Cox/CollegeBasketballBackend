"""
Django management command to sync KenPom FanMatch game predictions.

Usage:
    python manage.py sync_kenpom_fanmatch --date=2025-01-30
    python manage.py sync_kenpom_fanmatch --date=2025-01-30 --link-games
"""
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q
from basketball.models import Team, Game, KenPomTeam, KenPomFanMatch
from basketball.kenpom.client import KenPomClient, KenPomAPIError


class Command(BaseCommand):
    help = 'Sync KenPom FanMatch game predictions for a date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            required=True,
            help='Date in YYYY-MM-DD format'
        )
        parser.add_argument(
            '--link-games',
            action='store_true',
            help='Try to link FanMatch predictions to existing Game records'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days to sync starting from --date (default: 1)'
        )

    def handle(self, *args, **options):
        date_str = options['date']
        link_games = options.get('link_games', False)
        days = options.get('days', 1)
        
        # Parse date
        try:
            start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
            return
        
        self.stdout.write(f'Syncing KenPom FanMatch predictions...')
        self.stdout.write(f'  Start date: {start_date}')
        self.stdout.write(f'  Days: {days}')
        
        # Initialize client
        try:
            client = KenPomClient()
        except ValueError as e:
            self.stderr.write(self.style.ERROR(f'Error: {e}'))
            return
        
        # Build name-based lookup
        self.stdout.write('Building team lookup...')
        name_to_team = {}
        for team in Team.objects.all():
            name_to_team[team.school.lower()] = team
            if team.display_name:
                name_to_team[team.display_name.lower()] = team
        
        # Also use KenPomTeam mappings
        for mapping in KenPomTeam.objects.select_related('team').all():
            name_to_team[mapping.kenpom_team_name.lower()] = mapping.team
        
        self.stdout.write(f'  {len(name_to_team)} team name mappings')
        
        total_created = 0
        total_updated = 0
        total_skipped = 0
        total_linked = 0
        
        # Process each day
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            current_date_str = current_date.strftime('%Y-%m-%d')
            
            self.stdout.write(f'\nFetching FanMatch for {current_date_str}...')
            
            try:
                fanmatch_data = client.get_fanmatch(date=current_date_str)
            except KenPomAPIError as e:
                self.stderr.write(self.style.WARNING(f'  API Error for {current_date_str}: {e}'))
                continue
            
            self.stdout.write(f'  Received {len(fanmatch_data)} game predictions')
            
            # Process predictions
            created = 0
            updated = 0
            skipped = 0
            linked = 0
            
            for prediction in fanmatch_data:
                kenpom_game_id = prediction.get('GameID')
                home_name = prediction.get('Home', '')
                visitor_name = prediction.get('Visitor', '')
                game_date_str = prediction.get('DateOfGame', '')
                season = prediction.get('Season')
                
                if not kenpom_game_id or not home_name or not visitor_name:
                    skipped += 1
                    continue
                
                # Parse game date
                try:
                    game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
                except ValueError:
                    game_date = current_date
                
                # Find teams
                home_team = name_to_team.get(home_name.lower())
                away_team = name_to_team.get(visitor_name.lower())
                
                if not home_team:
                    self.stdout.write(
                        self.style.WARNING(f'  Skipping: Home team "{home_name}" not found')
                    )
                    skipped += 1
                    continue
                
                if not away_team:
                    self.stdout.write(
                        self.style.WARNING(f'  Skipping: Away team "{visitor_name}" not found')
                    )
                    skipped += 1
                    continue
                
                # Try to find matching Game record
                game = None
                if link_games:
                    game = Game.objects.filter(
                        home_team=home_team,
                        away_team=away_team,
                        date=game_date
                    ).first()
                    
                    if not game:
                        # Try reverse (sometimes home/away is swapped)
                        game = Game.objects.filter(
                            home_team=away_team,
                            away_team=home_team,
                            date=game_date
                        ).first()
                    
                    if game:
                        linked += 1
                
                # Create or update FanMatch record
                try:
                    fm_obj, was_created = KenPomFanMatch.objects.update_or_create(
                        kenpom_game_id=kenpom_game_id,
                        defaults={
                            'season': season or game_date.year,
                            'date': game_date,
                            'home_team': home_team,
                            'away_team': away_team,
                            'home_rank': prediction.get('HomeRank', 0),
                            'away_rank': prediction.get('VisitorRank', 0),
                            'home_predicted_score': prediction.get('HomePred', 0.0),
                            'away_predicted_score': prediction.get('VisitorPred', 0.0),
                            'home_win_probability': prediction.get('HomeWP', 0.5),
                            'predicted_tempo': prediction.get('PredTempo', 0.0),
                            'thrill_score': prediction.get('ThrillScore', 0.0),
                            'game': game,
                        }
                    )
                    
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                        
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f'  Error saving {home_name} vs {visitor_name}: {e}')
                    )
                    skipped += 1
            
            self.stdout.write(f'  Created: {created}, Updated: {updated}, Skipped: {skipped}')
            if link_games:
                self.stdout.write(f'  Linked to games: {linked}')
            
            total_created += created
            total_updated += updated
            total_skipped += skipped
            total_linked += linked
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sync completed!'))
        self.stdout.write(f'  Total created: {total_created}')
        self.stdout.write(f'  Total updated: {total_updated}')
        self.stdout.write(f'  Total skipped: {total_skipped}')
        if link_games:
            self.stdout.write(f'  Total linked to games: {total_linked}')
        self.stdout.write(f'  Total FanMatch in DB: {KenPomFanMatch.objects.count()}')
