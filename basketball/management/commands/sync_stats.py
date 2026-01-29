"""
Django management command to sync team stats from NCAA API standings.
Usage: python manage.py sync_stats
       python manage.py sync_stats --conference=SEC
"""
import requests
import re
from django.core.management.base import BaseCommand
from basketball.models import Team, TeamStats


NCAA_API_BASE = 'http://localhost:3005'


class Command(BaseCommand):
    help = 'Sync team statistics from NCAA API standings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--conference',
            type=str,
            help='Sync only teams in a specific conference (e.g., SEC, ACC)'
        )
        parser.add_argument(
            '--season',
            type=int,
            default=2026,
            help='Season year (default: 2026)'
        )

    def handle(self, *args, **options):
        season = options['season']
        conference_filter = options.get('conference')
        
        # Build team lookup by normalized name
        self.stdout.write('Building team name lookup...')
        name_to_team = {}
        for team in Team.objects.all():
            name_to_team[self.normalize_name(team.school)] = team
            name_to_team[self.normalize_name(team.short_display_name)] = team
            name_to_team[self.normalize_name(team.display_name)] = team
        
        self.stdout.write(f'  Cached {Team.objects.count()} teams')
        
        # Fetch standings
        self.stdout.write('Fetching standings from NCAA API...')
        standings_data = self.fetch_standings()
        
        if not standings_data:
            self.stderr.write(self.style.ERROR('Failed to fetch standings'))
            return
        
        stats_created = 0
        stats_updated = 0
        not_matched = 0
        
        for conf_data in standings_data:
            conf_name = conf_data.get('conference', '')
            
            # Skip if filtering by conference
            if conference_filter and conf_name.upper() != conference_filter.upper():
                continue
            
            standings = conf_data.get('standings', [])
            
            for team_standing in standings:
                school_name = team_standing.get('School', '')
                
                # Find team
                team = name_to_team.get(self.normalize_name(school_name))
                if not team:
                    not_matched += 1
                    continue
                
                # Parse record
                conf_wins = self.parse_int(team_standing.get('Conference W', '0'))
                conf_losses = self.parse_int(team_standing.get('Conference L', '0'))
                overall_wins = self.parse_int(team_standing.get('Overall W', '0'))
                overall_losses = self.parse_int(team_standing.get('Overall L', '0'))
                
                # Create or update stats
                stats_defaults = {
                    'wins': overall_wins,
                    'losses': overall_losses,
                    'conference_wins': conf_wins,
                    'conference_losses': conf_losses,
                }
                
                team_stats, created = TeamStats.objects.update_or_create(
                    team=team,
                    season=season,
                    defaults=stats_defaults
                )
                
                if created:
                    stats_created += 1
                else:
                    stats_updated += 1
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sync completed!'))
        self.stdout.write(f'  Stats created: {stats_created}')
        self.stdout.write(f'  Stats updated: {stats_updated}')
        self.stdout.write(f'  Teams not matched: {not_matched}')
        self.stdout.write(f'  Total stats in database: {TeamStats.objects.count()}')

    def normalize_name(self, name):
        """Normalize school name for matching."""
        if not name:
            return ''
        name = name.lower()
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', '', name)
        return name

    def parse_int(self, value):
        """Parse integer from string, return 0 on failure."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def fetch_standings(self):
        """Fetch standings from NCAA API."""
        url = f'{NCAA_API_BASE}/standings/basketball-men/d1'
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except requests.RequestException as e:
            self.stderr.write(self.style.WARNING(f'API error: {e}'))
            return []
        except ValueError as e:
            self.stderr.write(self.style.WARNING(f'JSON parse error: {e}'))
            return []
