"""
Django management command to import teams from CSV file and match NCAA slugs.
Usage: python manage.py import_teams
"""
import csv
import requests
from pathlib import Path
from django.core.management.base import BaseCommand
from basketball.models import Conference, Venue, Team


NCAA_API_BASE = 'http://localhost:3005'


class Command(BaseCommand):
    help = 'Import teams from public/teams.csv and match NCAA slugs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-path',
            type=str,
            default='public/teams.csv',
            help='Path to the teams CSV file (default: public/teams.csv)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing teams, conferences, and venues before importing'
        )
        parser.add_argument(
            '--skip-slugs',
            action='store_true',
            help='Skip fetching NCAA slugs (faster, but games sync won\'t work)'
        )

    def handle(self, *args, **options):
        csv_path = Path(options['csv_path'])
        
        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f'CSV file not found: {csv_path}'))
            return
        
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            Team.objects.all().delete()
            Conference.objects.all().delete()
            Venue.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared existing data'))
        
        # Fetch NCAA slugs
        ncaa_slugs = {}
        if not options['skip_slugs']:
            ncaa_slugs = self.fetch_ncaa_slugs()
        
        # Track statistics
        conferences_created = 0
        venues_created = 0
        teams_created = 0
        teams_updated = 0
        slugs_matched = 0
        
        # Cache for conferences and venues to avoid repeated lookups
        conference_cache = {}
        venue_cache = {}
        
        self.stdout.write(f'Reading CSV file: {csv_path}')
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Skip rows with invalid/unknown source IDs
                source_id = row.get('SourceId', '').strip()
                if not source_id or source_id.startswith('UNKNOWN'):
                    continue
                
                # Get or create conference
                conference = None
                conference_abbr = row.get('Conference', '').strip()
                if conference_abbr:
                    if conference_abbr not in conference_cache:
                        conference, created = Conference.objects.get_or_create(
                            abbreviation=conference_abbr,
                            defaults={'name': conference_abbr}  # Use abbr as name initially
                        )
                        conference_cache[conference_abbr] = conference
                        if created:
                            conferences_created += 1
                    else:
                        conference = conference_cache[conference_abbr]
                
                # Get or create venue
                venue = None
                venue_id = row.get('CurrentVenueId', '').strip()
                venue_name = row.get('CurrentVenue', '').strip()
                if venue_id and venue_name:
                    try:
                        venue_id_int = int(venue_id)
                        if venue_id_int not in venue_cache:
                            venue, created = Venue.objects.get_or_create(
                                source_id=venue_id_int,
                                defaults={
                                    'name': venue_name,
                                    'city': row.get('CurrentCity', '').strip(),
                                    'state': row.get('CurrentState', '').strip(),
                                }
                            )
                            venue_cache[venue_id_int] = venue
                            if created:
                                venues_created += 1
                        else:
                            venue = venue_cache[venue_id_int]
                    except ValueError:
                        pass  # Invalid venue ID, skip
                
                # Try to match NCAA slug
                school_name = row.get('School', '').strip()
                ncaa_slug = self.match_slug(school_name, ncaa_slugs)
                if ncaa_slug:
                    slugs_matched += 1
                
                # Create or update team
                team_defaults = {
                    'school': school_name,
                    'mascot': row.get('Mascot', '').strip(),
                    'abbreviation': row.get('Abbreviation', '').strip(),
                    'display_name': row.get('DisplayName', '').strip(),
                    'short_display_name': row.get('ShortDisplayName', '').strip(),
                    'primary_color': row.get('PrimaryColor', '').strip(),
                    'secondary_color': row.get('SecondaryColor', '').strip(),
                    'conference': conference,
                    'venue': venue,
                    'ncaa_slug': ncaa_slug or '',
                }
                
                team, created = Team.objects.update_or_create(
                    source_id=source_id,
                    defaults=team_defaults
                )
                
                if created:
                    teams_created += 1
                else:
                    teams_updated += 1
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Import completed!'))
        self.stdout.write(f'  Conferences created: {conferences_created}')
        self.stdout.write(f'  Venues created: {venues_created}')
        self.stdout.write(f'  Teams created: {teams_created}')
        self.stdout.write(f'  Teams updated: {teams_updated}')
        self.stdout.write(f'  NCAA slugs matched: {slugs_matched}')
        self.stdout.write(f'  Total teams in database: {Team.objects.count()}')

    def fetch_ncaa_slugs(self):
        """Fetch school slugs from NCAA API."""
        self.stdout.write('Fetching NCAA school slugs...')
        
        try:
            response = requests.get(f'{NCAA_API_BASE}/schools-index', timeout=30)
            response.raise_for_status()
            schools = response.json()
            
            # Build lookup dict by normalized name
            slugs = {}
            for school in schools:
                slug = school.get('slug', '')
                name = school.get('name', '')
                long_name = school.get('long', '')
                
                if slug:
                    # Add multiple keys for matching
                    slugs[self.normalize_name(name)] = slug
                    slugs[self.normalize_name(long_name)] = slug
                    # Also add the slug itself as a key
                    slugs[slug.replace('-', '')] = slug
            
            self.stdout.write(f'  Fetched {len(schools)} schools from NCAA API')
            return slugs
            
        except requests.RequestException as e:
            self.stderr.write(self.style.WARNING(f'  Failed to fetch NCAA slugs: {e}'))
            return {}

    def normalize_name(self, name):
        """Normalize school name for matching."""
        if not name:
            return ''
        # Lowercase, remove punctuation, collapse whitespace
        import re
        name = name.lower()
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', '', name)
        return name

    def match_slug(self, school_name, ncaa_slugs):
        """Try to find matching NCAA slug for a school."""
        if not ncaa_slugs:
            return None
        
        normalized = self.normalize_name(school_name)
        if normalized in ncaa_slugs:
            return ncaa_slugs[normalized]
        
        # Try variations
        variations = [
            school_name,
            school_name.replace(' State', ' St.'),
            school_name.replace(' St.', ' State'),
            school_name.replace('University of ', ''),
            school_name.replace(' University', ''),
        ]
        
        for var in variations:
            norm = self.normalize_name(var)
            if norm in ncaa_slugs:
                return ncaa_slugs[norm]
        
        return None
