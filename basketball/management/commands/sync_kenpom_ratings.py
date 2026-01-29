"""
Django management command to sync KenPom ratings.

Usage:
    python manage.py sync_kenpom_ratings --season=2025
    python manage.py sync_kenpom_ratings --season=2025 --conference=B12
    python manage.py sync_kenpom_ratings --team-id=73 --season=2025
"""
from django.core.management.base import BaseCommand
from basketball.models import Team, KenPomTeam, KenPomRating
from basketball.kenpom.client import KenPomClient, KenPomAPIError


class Command(BaseCommand):
    help = 'Sync KenPom ratings for teams'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            help='Season year (ending year, e.g., 2025 for 2024-25 season)'
        )
        parser.add_argument(
            '--team-id',
            type=int,
            help='KenPom Team ID to sync (optional)'
        )
        parser.add_argument(
            '--conference',
            type=str,
            help='Conference short name (e.g., B12, ACC)'
        )

    def handle(self, *args, **options):
        season = options.get('season')
        team_id = options.get('team_id')
        conference = options.get('conference')
        
        if not season and not team_id:
            self.stderr.write(self.style.ERROR('At least --season or --team-id is required'))
            return
        
        self.stdout.write(f'Syncing KenPom ratings...')
        if season:
            self.stdout.write(f'  Season: {season}')
        if team_id:
            self.stdout.write(f'  Team ID: {team_id}')
        if conference:
            self.stdout.write(f'  Conference: {conference}')
        
        # Initialize client
        try:
            client = KenPomClient()
        except ValueError as e:
            self.stderr.write(self.style.ERROR(f'Error: {e}'))
            return
        
        # Build KenPom ID to Team lookup
        self.stdout.write('Building team lookup...')
        kenpom_to_team = {}
        for mapping in KenPomTeam.objects.select_related('team').all():
            kenpom_to_team[mapping.kenpom_team_id] = mapping.team
        
        # Also build name-based lookup for teams without mapping
        name_to_team = {}
        for team in Team.objects.all():
            name_to_team[team.school.lower()] = team
            if team.display_name:
                name_to_team[team.display_name.lower()] = team
        
        self.stdout.write(f'  {len(kenpom_to_team)} teams mapped via KenPomTeam')
        
        # Fetch ratings
        self.stdout.write('Fetching ratings from KenPom API...')
        try:
            ratings_data = client.get_ratings(
                season=season,
                team_id=team_id,
                conference=conference
            )
        except KenPomAPIError as e:
            self.stderr.write(self.style.ERROR(f'API Error: {e}'))
            return
        
        self.stdout.write(f'  Received {len(ratings_data)} rating records')
        
        # Process ratings
        created = 0
        updated = 0
        skipped = 0
        
        for rating in ratings_data:
            team_name = rating.get('TeamName', '')
            rating_season = rating.get('Season', season)
            
            # Find the team
            team = None
            
            # First try by KenPom team ID (if we have it from teams endpoint)
            # The ratings endpoint doesn't include TeamID, so we match by name
            if team_name.lower() in name_to_team:
                team = name_to_team[team_name.lower()]
            else:
                # Try to find via KenPomTeam mapping by name
                kenpom_mapping = KenPomTeam.objects.filter(
                    kenpom_team_name__iexact=team_name
                ).first()
                if kenpom_mapping:
                    team = kenpom_mapping.team
            
            if not team:
                self.stdout.write(
                    self.style.WARNING(f'  Skipping {team_name}: No matching team found')
                )
                skipped += 1
                continue
            
            # Create or update rating
            try:
                rating_obj, was_created = KenPomRating.objects.update_or_create(
                    team=team,
                    season=rating_season,
                    defaults={
                        'data_through': rating.get('DataThrough', ''),
                        'seed': rating.get('Seed'),
                        'coach': rating.get('Coach', ''),
                        'wins': rating.get('Wins', 0),
                        'losses': rating.get('Losses', 0),
                        
                        # Core ratings
                        'adj_em': rating.get('AdjEM', 0.0),
                        'rank_adj_em': rating.get('RankAdjEM', 0),
                        'pythag': rating.get('Pythag', 0.0),
                        'rank_pythag': rating.get('RankPythag', 0),
                        
                        # Offense
                        'adj_oe': rating.get('AdjOE', 0.0),
                        'rank_adj_oe': rating.get('RankAdjOE', 0),
                        'oe': rating.get('OE', 0.0),
                        'rank_oe': rating.get('RankOE', 0),
                        
                        # Defense
                        'adj_de': rating.get('AdjDE', 0.0),
                        'rank_adj_de': rating.get('RankAdjDE', 0),
                        'de': rating.get('DE', 0.0),
                        'rank_de': rating.get('RankDE', 0),
                        
                        # Tempo
                        'tempo': rating.get('Tempo', 0.0),
                        'rank_tempo': rating.get('RankTempo', 0),
                        'adj_tempo': rating.get('AdjTempo', 0.0),
                        'rank_adj_tempo': rating.get('RankAdjTempo', 0),
                        
                        # Advanced
                        'luck': rating.get('Luck', 0.0),
                        'rank_luck': rating.get('RankLuck', 0),
                        'sos': rating.get('SOS', 0.0),
                        'rank_sos': rating.get('RankSOS', 0),
                        'sos_offense': rating.get('SOSO', 0.0),
                        'rank_sos_offense': rating.get('RankSOSO', 0),
                        'sos_defense': rating.get('SOSD', 0.0),
                        'rank_sos_defense': rating.get('RankSOSD', 0),
                        'ncsos': rating.get('NCSOS', 0.0),
                        'rank_ncsos': rating.get('RankNCSOS', 0),
                        
                        # Possession Length (may be null)
                        'apl_offense': rating.get('APL_Off'),
                        'rank_apl_offense': rating.get('RankAPL_Off'),
                        'apl_defense': rating.get('APL_Def'),
                        'rank_apl_defense': rating.get('RankAPL_Def'),
                        'conf_apl_offense': rating.get('ConfAPL_Off'),
                        'rank_conf_apl_offense': rating.get('RankConfAPL_Off'),
                        'conf_apl_defense': rating.get('ConfAPL_Def'),
                        'rank_conf_apl_defense': rating.get('RankConfAPL_Def'),
                        
                        # Event (handle None from API)
                        'event': rating.get('Event') or '',
                    }
                )
                
                if was_created:
                    created += 1
                else:
                    updated += 1
                    
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f'  Error saving {team_name}: {e}')
                )
                skipped += 1
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sync completed!'))
        self.stdout.write(f'  Created: {created}')
        self.stdout.write(f'  Updated: {updated}')
        self.stdout.write(f'  Skipped: {skipped}')
        self.stdout.write(f'  Total ratings in DB: {KenPomRating.objects.count()}')
