"""
Django management command to sync KenPom Four Factors data.

Usage:
    python manage.py sync_kenpom_four_factors --season=2025
    python manage.py sync_kenpom_four_factors --season=2025 --conference=B12
    python manage.py sync_kenpom_four_factors --season=2025 --conference-only
"""
from django.core.management.base import BaseCommand
from basketball.models import Team, KenPomTeam, KenPomFourFactors
from basketball.kenpom.client import KenPomClient, KenPomAPIError


class Command(BaseCommand):
    help = 'Sync KenPom Four Factors statistics'

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
        parser.add_argument(
            '--conference-only',
            action='store_true',
            help='Sync conference-only statistics instead of all games'
        )

    def handle(self, *args, **options):
        season = options.get('season')
        team_id = options.get('team_id')
        conference = options.get('conference')
        conf_only = options.get('conference_only', False)
        
        if not season and not team_id:
            self.stderr.write(self.style.ERROR('At least --season or --team-id is required'))
            return
        
        self.stdout.write(f'Syncing KenPom Four Factors...')
        if season:
            self.stdout.write(f'  Season: {season}')
        if team_id:
            self.stdout.write(f'  Team ID: {team_id}')
        if conference:
            self.stdout.write(f'  Conference: {conference}')
        if conf_only:
            self.stdout.write(f'  Conference-only stats: Yes')
        
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
        
        # Fetch Four Factors
        self.stdout.write('Fetching Four Factors from KenPom API...')
        try:
            ff_data = client.get_four_factors(
                season=season,
                team_id=team_id,
                conference=conference,
                conf_only=conf_only
            )
        except KenPomAPIError as e:
            self.stderr.write(self.style.ERROR(f'API Error: {e}'))
            return
        
        self.stdout.write(f'  Received {len(ff_data)} Four Factors records')
        
        # Process data
        created = 0
        updated = 0
        skipped = 0
        
        for ff in ff_data:
            team_name = ff.get('TeamName', '')
            ff_season = ff.get('Season', season)
            is_conf_only = ff.get('ConfOnly', 'false').lower() == 'true'
            
            # Find the team
            team = name_to_team.get(team_name.lower())
            
            if not team:
                self.stdout.write(
                    self.style.WARNING(f'  Skipping {team_name}: No matching team found')
                )
                skipped += 1
                continue
            
            # Create or update
            try:
                ff_obj, was_created = KenPomFourFactors.objects.update_or_create(
                    team=team,
                    season=ff_season,
                    is_conference_only=is_conf_only,
                    defaults={
                        'data_through': ff.get('DataThrough', ''),
                        
                        # Offensive Four Factors
                        'efg_pct': ff.get('eFG_Pct', 0.0),
                        'rank_efg_pct': ff.get('RankeFG_Pct', 0),
                        'to_pct': ff.get('TO_Pct', 0.0),
                        'rank_to_pct': ff.get('RankTO_Pct', 0),
                        'or_pct': ff.get('OR_Pct', 0.0),
                        'rank_or_pct': ff.get('RankOR_Pct', 0),
                        'ft_rate': ff.get('FT_Rate', 0.0),
                        'rank_ft_rate': ff.get('RankFT_Rate', 0),
                        
                        # Defensive Four Factors
                        'defg_pct': ff.get('DeFG_Pct', 0.0),
                        'rank_defg_pct': ff.get('RankDeFG_Pct', 0),
                        'dto_pct': ff.get('DTO_Pct', 0.0),
                        'rank_dto_pct': ff.get('RankDTO_Pct', 0),
                        'dor_pct': ff.get('DOR_Pct', 0.0),
                        'rank_dor_pct': ff.get('RankDOR_Pct', 0),
                        'dft_rate': ff.get('DFT_Rate', 0.0),
                        'rank_dft_rate': ff.get('RankDFT_Rate', 0),
                        
                        # Efficiency ratings
                        'oe': ff.get('OE', 0.0),
                        'rank_oe': ff.get('RankOE', 0),
                        'de': ff.get('DE', 0.0),
                        'rank_de': ff.get('RankDE', 0),
                        'tempo': ff.get('Tempo', 0.0),
                        'rank_tempo': ff.get('RankTempo', 0),
                        'adj_oe': ff.get('AdjOE', 0.0),
                        'rank_adj_oe': ff.get('RankAdjOE', 0),
                        'adj_de': ff.get('AdjDE', 0.0),
                        'rank_adj_de': ff.get('RankAdjDE', 0),
                        'adj_tempo': ff.get('AdjTempo', 0.0),
                        'rank_adj_tempo': ff.get('RankAdjTempo', 0),
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
        self.stdout.write(f'  Total Four Factors in DB: {KenPomFourFactors.objects.count()}')
