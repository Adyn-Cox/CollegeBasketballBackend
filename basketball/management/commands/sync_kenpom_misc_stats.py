"""
Django management command to sync KenPom miscellaneous statistics.

Usage:
    python manage.py sync_kenpom_misc_stats --season=2025
    python manage.py sync_kenpom_misc_stats --season=2025 --conference=B12
    python manage.py sync_kenpom_misc_stats --season=2025 --conference-only
"""
from django.core.management.base import BaseCommand
from basketball.models import Team, KenPomTeam, KenPomMiscStats
from basketball.kenpom.client import KenPomClient, KenPomAPIError


class Command(BaseCommand):
    help = 'Sync KenPom miscellaneous advanced statistics'

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
        
        self.stdout.write(f'Syncing KenPom Misc Stats...')
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
        
        for mapping in KenPomTeam.objects.select_related('team').all():
            name_to_team[mapping.kenpom_team_name.lower()] = mapping.team
        
        self.stdout.write(f'  {len(name_to_team)} team name mappings')
        
        # Fetch misc stats
        self.stdout.write('Fetching misc stats from KenPom API...')
        try:
            misc_data = client.get_misc_stats(
                season=season,
                team_id=team_id,
                conference=conference,
                conf_only=conf_only
            )
        except KenPomAPIError as e:
            self.stderr.write(self.style.ERROR(f'API Error: {e}'))
            return
        
        self.stdout.write(f'  Received {len(misc_data)} misc stats records')
        
        # Process data
        created = 0
        updated = 0
        skipped = 0
        
        for m in misc_data:
            team_name = m.get('TeamName', '')
            m_season = m.get('Season', season)
            is_conf_only = m.get('ConfOnly', 'false').lower() == 'true'
            
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
                m_obj, was_created = KenPomMiscStats.objects.update_or_create(
                    team=team,
                    season=m_season,
                    is_conference_only=is_conf_only,
                    defaults={
                        'data_through': m.get('DataThrough', ''),
                        
                        # Offensive shooting
                        'fg3_pct': m.get('FG3Pct', 0.0),
                        'rank_fg3_pct': m.get('RankFG3Pct', 0),
                        'fg2_pct': m.get('FG2Pct', 0.0),
                        'rank_fg2_pct': m.get('RankFG2Pct', 0),
                        'ft_pct': m.get('FTPct', 0.0),
                        'rank_ft_pct': m.get('RankFTPct', 0),
                        
                        # Offensive advanced
                        'block_pct': m.get('BlockPct', 0.0),
                        'rank_block_pct': m.get('RankBlockPct', 0),
                        'steal_rate': m.get('StlRate', 0.0),
                        'rank_steal_rate': m.get('RankStlRate', 0),
                        'ns_turnover_rate': m.get('NSTRate', 0.0),
                        'rank_ns_turnover_rate': m.get('RankNSTRate', 0),
                        'assist_rate': m.get('ARate', 0.0),
                        'rank_assist_rate': m.get('RankARate', 0),
                        'fg3_attempt_rate': m.get('F3GRate', 0.0),
                        'rank_fg3_attempt_rate': m.get('RankF3GRate', 0),
                        'avg_2pa_distance': m.get('Avg2PADist', 0.0),
                        'rank_avg_2pa_distance': m.get('RankAvg2PADist', 0),
                        
                        # Defensive shooting allowed
                        'opp_fg3_pct': m.get('OppFG3Pct', 0.0),
                        'rank_opp_fg3_pct': m.get('RankOppFG3Pct', 0),
                        'opp_fg2_pct': m.get('OppFG2Pct', 0.0),
                        'rank_opp_fg2_pct': m.get('RankOppFG2Pct', 0),
                        'opp_ft_pct': m.get('OppFTPct', 0.0),
                        'rank_opp_ft_pct': m.get('RankOppFTPct', 0),
                        
                        # Defensive advanced
                        'opp_block_pct': m.get('OppBlockPct', 0.0),
                        'rank_opp_block_pct': m.get('RankOppBlockPct', 0),
                        'opp_steal_rate': m.get('OppStlRate', 0.0),
                        'rank_opp_steal_rate': m.get('RankOppStlRate', 0),
                        'opp_ns_turnover_rate': m.get('OppNSTRate', 0.0),
                        'rank_opp_ns_turnover_rate': m.get('RankOppNSTRate', 0),
                        'opp_assist_rate': m.get('OppARate', 0.0),
                        'rank_opp_assist_rate': m.get('RankOppARate', 0),
                        'opp_fg3_attempt_rate': m.get('OppF3GRate', 0.0),
                        'rank_opp_fg3_attempt_rate': m.get('RankOppF3GRate', 0),
                        'opp_avg_2pa_distance': m.get('OppAvg2PADist', 0.0),
                        'rank_opp_avg_2pa_distance': m.get('RankOppAvg2PADist', 0),
                        
                        # Efficiency ratings
                        'adj_oe': m.get('AdjOE', 0.0),
                        'rank_adj_oe': m.get('RankAdjOE', 0),
                        'adj_de': m.get('AdjDE', 0.0),
                        'rank_adj_de': m.get('RankAdjDE', 0),
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
        self.stdout.write(f'  Total Misc Stats in DB: {KenPomMiscStats.objects.count()}')
