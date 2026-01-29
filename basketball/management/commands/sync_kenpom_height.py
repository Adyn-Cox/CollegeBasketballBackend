"""
Django management command to sync KenPom height, experience, and bench statistics.

Usage:
    python manage.py sync_kenpom_height --season=2025
    python manage.py sync_kenpom_height --season=2025 --conference=B12
"""
from django.core.management.base import BaseCommand
from basketball.models import Team, KenPomTeam, KenPomHeight
from basketball.kenpom.client import KenPomClient, KenPomAPIError


class Command(BaseCommand):
    help = 'Sync KenPom height, experience, and bench statistics'

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
        
        self.stdout.write(f'Syncing KenPom Height/Experience stats...')
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
        
        # Build name-based lookup
        self.stdout.write('Building team lookup...')
        name_to_team = {}
        for team in Team.objects.all():
            name_to_team[team.school.lower()] = team
            if team.display_name:
                name_to_team[team.display_name.lower()] = team
        
        for mapping in KenPomTeam.objects.select_related('team').all():
            name_to_team[mapping.kenpom_team_name.lower()] = mapping.team
        
        self.stdout.write(f'  {len(name_to_team)} team name mappings')
        
        # Fetch height data
        self.stdout.write('Fetching height data from KenPom API...')
        try:
            height_data = client.get_height(
                season=season,
                team_id=team_id,
                conference=conference
            )
        except KenPomAPIError as e:
            self.stderr.write(self.style.ERROR(f'API Error: {e}'))
            return
        
        self.stdout.write(f'  Received {len(height_data)} height records')
        
        # Process data
        created = 0
        updated = 0
        skipped = 0
        
        for h in height_data:
            team_name = h.get('TeamName', '')
            h_season = h.get('Season', season)
            
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
                h_obj, was_created = KenPomHeight.objects.update_or_create(
                    team=team,
                    season=h_season,
                    defaults={
                        'data_through': h.get('DataThrough', ''),
                        
                        # Height stats
                        'avg_height': h.get('AvgHgt', 0.0),
                        'avg_height_rank': h.get('AvgHgtRank', 0),
                        'effective_height': h.get('HgtEff', 0.0),
                        'effective_height_rank': h.get('HgtEffRank', 0),
                        
                        # Position heights
                        'height_center': h.get('Hgt5', 0.0),
                        'height_center_rank': h.get('Hgt5Rank', 0),
                        'height_pf': h.get('Hgt4', 0.0),
                        'height_pf_rank': h.get('Hgt4Rank', 0),
                        'height_sf': h.get('Hgt3', 0.0),
                        'height_sf_rank': h.get('Hgt3Rank', 0),
                        'height_sg': h.get('Hgt2', 0.0),
                        'height_sg_rank': h.get('Hgt2Rank', 0),
                        'height_pg': h.get('Hgt1', 0.0),
                        'height_pg_rank': h.get('Hgt1Rank', 0),
                        
                        # Experience & Bench
                        'experience': h.get('Exp', 0.0),
                        'experience_rank': h.get('ExpRank', 0),
                        'bench_strength': h.get('Bench', 0.0),
                        'bench_strength_rank': h.get('BenchRank', 0),
                        'continuity': h.get('Continuity', 0.0),
                        'continuity_rank': h.get('RankContinuity', 0),
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
        self.stdout.write(f'  Total Height records in DB: {KenPomHeight.objects.count()}')
