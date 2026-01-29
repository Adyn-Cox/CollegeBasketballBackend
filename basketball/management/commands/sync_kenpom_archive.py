"""
Django management command to sync KenPom historical archived ratings.

Usage:
    python manage.py sync_kenpom_archive --date=2025-02-15
    python manage.py sync_kenpom_archive --preseason --season=2025
    python manage.py sync_kenpom_archive --start-date=2025-01-01 --end-date=2025-03-15
"""
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from basketball.models import Team, KenPomTeam, KenPomRatingArchive
from basketball.kenpom.client import KenPomClient, KenPomAPIError


class Command(BaseCommand):
    help = 'Sync KenPom historical archived ratings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date in YYYY-MM-DD format'
        )
        parser.add_argument(
            '--season',
            type=int,
            help='Season year (required for preseason)'
        )
        parser.add_argument(
            '--preseason',
            action='store_true',
            help='Fetch preseason ratings (requires --season)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for date range sync (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for date range sync (YYYY-MM-DD)'
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
        date_str = options.get('date')
        season = options.get('season')
        preseason = options.get('preseason', False)
        start_date_str = options.get('start_date')
        end_date_str = options.get('end_date')
        team_id = options.get('team_id')
        conference = options.get('conference')
        
        # Validate arguments
        if preseason and not season:
            self.stderr.write(self.style.ERROR('--season is required when using --preseason'))
            return
        
        if not date_str and not preseason and not (start_date_str and end_date_str):
            self.stderr.write(self.style.ERROR(
                'Either --date, --preseason, or both --start-date and --end-date are required'
            ))
            return
        
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
        
        # Determine dates to sync
        dates_to_sync = []
        
        if preseason:
            # Preseason is a special case - no specific date
            dates_to_sync = [('preseason', season)]
            self.stdout.write(f'Syncing preseason ratings for {season}...')
        elif date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                dates_to_sync = [(date, season or date.year)]
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
            self.stdout.write(f'Syncing archive for {date_str}...')
        elif start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
            
            # Generate all dates in range
            current = start_date
            while current <= end_date:
                dates_to_sync.append((current, season or current.year))
                current += timedelta(days=1)
            
            self.stdout.write(f'Syncing archive from {start_date_str} to {end_date_str}...')
            self.stdout.write(f'  {len(dates_to_sync)} dates to sync')
        
        total_created = 0
        total_updated = 0
        total_skipped = 0
        
        # Process each date
        for date_info in dates_to_sync:
            if date_info[0] == 'preseason':
                # Preseason sync
                archive_date = None
                is_preseason = True
                archive_season = date_info[1]
                date_display = f'preseason {archive_season}'
            else:
                archive_date = date_info[0]
                is_preseason = False
                archive_season = date_info[1]
                date_display = archive_date.strftime('%Y-%m-%d')
            
            self.stdout.write(f'\nFetching archive for {date_display}...')
            
            try:
                if is_preseason:
                    archive_data = client.get_archive(
                        season=archive_season,
                        preseason=True,
                        team_id=team_id,
                        conference=conference
                    )
                else:
                    archive_data = client.get_archive(
                        date=archive_date.strftime('%Y-%m-%d'),
                        team_id=team_id,
                        conference=conference
                    )
            except KenPomAPIError as e:
                self.stderr.write(self.style.WARNING(f'  API Error for {date_display}: {e}'))
                continue
            
            self.stdout.write(f'  Received {len(archive_data)} archive records')
            
            # Process records
            created = 0
            updated = 0
            skipped = 0
            
            for a in archive_data:
                team_name = a.get('TeamName', '')
                a_season = a.get('Season', archive_season)
                
                # Parse archive date from response if available
                if is_preseason:
                    record_date = None  # Will use a sentinel date for preseason
                    record_is_preseason = True
                else:
                    archive_date_str = a.get('ArchiveDate', '')
                    if archive_date_str:
                        try:
                            record_date = datetime.strptime(archive_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            record_date = archive_date
                    else:
                        record_date = archive_date
                    record_is_preseason = a.get('Preseason', 'false').lower() == 'true'
                
                # For preseason, use a sentinel date (e.g., Nov 1 of the season start year)
                if record_is_preseason:
                    record_date = datetime(a_season - 1, 11, 1).date()
                
                # Find the team
                team = name_to_team.get(team_name.lower())
                
                if not team:
                    skipped += 1
                    continue
                
                # Create or update
                try:
                    a_obj, was_created = KenPomRatingArchive.objects.update_or_create(
                        team=team,
                        season=a_season,
                        archive_date=record_date,
                        defaults={
                            'is_preseason': record_is_preseason,
                            
                            # Ratings on archive date
                            'adj_em': a.get('AdjEM', 0.0),
                            'rank_adj_em': a.get('RankAdjEM', 0),
                            'adj_oe': a.get('AdjOE', 0.0),
                            'rank_adj_oe': a.get('RankAdjOE', 0),
                            'adj_de': a.get('AdjDE', 0.0),
                            'rank_adj_de': a.get('RankAdjDE', 0),
                            'adj_tempo': a.get('AdjTempo', 0.0),
                            'rank_adj_tempo': a.get('RankAdjTempo', 0),
                            
                            # Final ratings (may be null if season not over)
                            'adj_em_final': a.get('AdjEMFinal'),
                            'rank_adj_em_final': a.get('RankAdjEMFinal'),
                            'adj_oe_final': a.get('AdjOEFinal'),
                            'rank_adj_oe_final': a.get('RankAdjOEFinal'),
                            'adj_de_final': a.get('AdjDEFinal'),
                            'rank_adj_de_final': a.get('RankAdjDEFinal'),
                            'adj_tempo_final': a.get('AdjTempoFinal'),
                            'rank_adj_tempo_final': a.get('RankAdjTempoFinal'),
                            
                            # Changes
                            'rank_change': a.get('RankChg'),
                            'adj_em_change': a.get('AdjEMChg'),
                            'adj_tempo_change': a.get('AdjTChg'),
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
            
            self.stdout.write(f'  Created: {created}, Updated: {updated}, Skipped: {skipped}')
            
            total_created += created
            total_updated += updated
            total_skipped += skipped
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sync completed!'))
        self.stdout.write(f'  Total created: {total_created}')
        self.stdout.write(f'  Total updated: {total_updated}')
        self.stdout.write(f'  Total skipped: {total_skipped}')
        self.stdout.write(f'  Total archives in DB: {KenPomRatingArchive.objects.count()}')
