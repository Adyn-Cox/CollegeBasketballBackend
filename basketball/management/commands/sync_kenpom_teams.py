"""
Django management command to sync KenPom teams and map them to our Team model.

Usage:
    python manage.py sync_kenpom_teams --season=2025
    python manage.py sync_kenpom_teams --season=2025 --force
"""
import re
from difflib import SequenceMatcher
from django.core.management.base import BaseCommand
from basketball.models import Team, KenPomTeam
from basketball.kenpom.client import KenPomClient, KenPomAPIError


class Command(BaseCommand):
    help = 'Sync KenPom teams and map them to our Team model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            required=True,
            help='Season year (ending year, e.g., 2025 for 2024-25 season)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync even if team mapping already exists'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        season = options['season']
        force = options['force']
        dry_run = options['dry_run']
        
        self.stdout.write(f'Syncing KenPom teams for season {season}...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        # Initialize client
        try:
            client = KenPomClient()
        except ValueError as e:
            self.stderr.write(self.style.ERROR(f'Error: {e}'))
            return
        
        # Fetch KenPom teams
        self.stdout.write('Fetching teams from KenPom API...')
        try:
            kenpom_teams = client.get_teams(season=season)
        except KenPomAPIError as e:
            self.stderr.write(self.style.ERROR(f'API Error: {e}'))
            return
        
        self.stdout.write(f'  Found {len(kenpom_teams)} teams from KenPom')
        
        # Build lookup tables for our teams
        self.stdout.write('Building team lookup tables...')
        our_teams = Team.objects.all()
        
        # Multiple lookup strategies
        exact_name_lookup = {}
        normalized_name_lookup = {}
        display_name_lookup = {}
        abbreviation_lookup = {}
        
        for team in our_teams:
            # Exact school name
            exact_name_lookup[team.school.lower()] = team
            
            # Normalized name (remove punctuation, extra spaces)
            normalized = self._normalize_name(team.school)
            normalized_name_lookup[normalized] = team
            
            # Display name
            if team.display_name:
                display_name_lookup[team.display_name.lower()] = team
                normalized_name_lookup[self._normalize_name(team.display_name)] = team
            
            # Short display name
            if team.short_display_name:
                normalized_name_lookup[self._normalize_name(team.short_display_name)] = team
            
            # Abbreviation
            if team.abbreviation:
                abbreviation_lookup[team.abbreviation.lower()] = team
        
        self.stdout.write(f'  Cached {len(our_teams)} teams from database')
        
        # Process KenPom teams
        matched = 0
        created = 0
        updated = 0
        unmatched = []
        
        for kp_team in kenpom_teams:
            kp_team_id = kp_team.get('TeamID')
            kp_team_name = kp_team.get('TeamName', '')
            
            if not kp_team_id or not kp_team_name:
                continue
            
            # Check if mapping already exists
            existing = KenPomTeam.objects.filter(kenpom_team_id=kp_team_id).first()
            if existing and not force:
                matched += 1
                continue
            
            # Try to find matching team
            our_team = self._find_matching_team(
                kp_team_name,
                exact_name_lookup,
                normalized_name_lookup,
                display_name_lookup,
                abbreviation_lookup
            )
            
            if our_team:
                if dry_run:
                    self.stdout.write(f'  Would map: {kp_team_name} -> {our_team.school}')
                else:
                    # Check if this team is already mapped to a different KenPom team
                    existing_team_mapping = KenPomTeam.objects.filter(team=our_team).exclude(kenpom_team_id=kp_team_id).first()
                    if existing_team_mapping:
                        # Team is already mapped to another KenPom ID - skip to avoid duplicates
                        self.stdout.write(self.style.WARNING(
                            f'  Skipping: {kp_team_name} -> {our_team.school} '
                            f'(already mapped to KenPom ID {existing_team_mapping.kenpom_team_id})'
                        ))
                        unmatched.append({
                            'kenpom_id': kp_team_id,
                            'kenpom_name': kp_team_name,
                            'conference': kp_team.get('ConfShort', ''),
                            'reason': f'Team already mapped to KenPom ID {existing_team_mapping.kenpom_team_id}',
                        })
                        continue
                    
                    # Create or update mapping
                    try:
                        mapping, was_created = KenPomTeam.objects.update_or_create(
                            kenpom_team_id=kp_team_id,
                            defaults={
                                'team': our_team,
                                'kenpom_team_name': kp_team_name,
                            }
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(
                            f'  Error mapping {kp_team_name} -> {our_team.school}: {e}'
                        ))
                        continue
                matched += 1
            else:
                unmatched.append({
                    'kenpom_id': kp_team_id,
                    'kenpom_name': kp_team_name,
                    'conference': kp_team.get('ConfShort', ''),
                })
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sync completed!'))
        self.stdout.write(f'  Matched: {matched}')
        if not dry_run:
            self.stdout.write(f'  Created: {created}')
            self.stdout.write(f'  Updated: {updated}')
        self.stdout.write(f'  Unmatched: {len(unmatched)}')
        
        # Report unmatched teams
        if unmatched:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Unmatched teams (need manual mapping):'))
            for team in unmatched[:20]:  # Show first 20
                self.stdout.write(
                    f"  - {team['kenpom_name']} (ID: {team['kenpom_id']}, Conf: {team['conference']})"
                )
            if len(unmatched) > 20:
                self.stdout.write(f'  ... and {len(unmatched) - 20} more')
            
            # Suggest similar teams
            self.stdout.write('')
            self.stdout.write('Possible matches (fuzzy):')
            for team in unmatched[:10]:
                suggestions = self._find_similar_teams(team['kenpom_name'], our_teams)
                if suggestions:
                    self.stdout.write(f"  {team['kenpom_name']}:")
                    for suggestion, score in suggestions[:3]:
                        self.stdout.write(f"    - {suggestion.school} (score: {score:.2f})")

    def _normalize_name(self, name: str) -> str:
        """Normalize team name for matching."""
        if not name:
            return ''
        # Lowercase
        name = name.lower()
        # Remove common suffixes/prefixes
        name = re.sub(r'\b(university|college|state|st\.?)\b', '', name)
        # Remove punctuation
        name = re.sub(r'[^\w\s]', '', name)
        # Remove extra whitespace
        name = ' '.join(name.split())
        return name.strip()

    def _find_matching_team(
        self,
        kp_name: str,
        exact_lookup: dict,
        normalized_lookup: dict,
        display_lookup: dict,
        abbrev_lookup: dict
    ):
        """Try multiple strategies to find a matching team."""
        # Strategy 1: Exact name match
        if kp_name.lower() in exact_lookup:
            return exact_lookup[kp_name.lower()]
        
        # Strategy 2: Display name match
        if kp_name.lower() in display_lookup:
            return display_lookup[kp_name.lower()]
        
        # Strategy 3: Normalized name match
        normalized = self._normalize_name(kp_name)
        if normalized in normalized_lookup:
            return normalized_lookup[normalized]
        
        # Strategy 4: Handle common variations
        variations = self._get_name_variations(kp_name)
        for variation in variations:
            if variation.lower() in exact_lookup:
                return exact_lookup[variation.lower()]
            if variation.lower() in display_lookup:
                return display_lookup[variation.lower()]
            norm_var = self._normalize_name(variation)
            if norm_var in normalized_lookup:
                return normalized_lookup[norm_var]
        
        return None

    def _get_name_variations(self, name: str) -> list:
        """Generate common name variations."""
        variations = [name]
        
        # Handle "St." vs "State" vs "Saint"
        if 'St.' in name:
            variations.append(name.replace('St.', 'State'))
            variations.append(name.replace('St.', 'Saint'))
        if 'State' in name:
            variations.append(name.replace('State', 'St.'))
        if 'Saint' in name:
            variations.append(name.replace('Saint', 'St.'))
        
        # Handle "USC" style abbreviations
        if name.upper() == name and len(name) <= 5:
            # Might be an abbreviation
            pass
        
        # Handle "North Carolina" vs "UNC" style
        abbreviation_map = {
            'North Carolina': 'UNC',
            'Southern California': 'USC',
            'Central Florida': 'UCF',
            'Connecticut': 'UConn',
            'Louisiana State': 'LSU',
            'Texas Christian': 'TCU',
            'Southern Methodist': 'SMU',
            'Brigham Young': 'BYU',
            'Virginia Commonwealth': 'VCU',
        }
        for full, abbrev in abbreviation_map.items():
            if full in name:
                variations.append(name.replace(full, abbrev))
            if abbrev in name:
                variations.append(name.replace(abbrev, full))
        
        return variations

    def _find_similar_teams(self, kp_name: str, our_teams, threshold: float = 0.6) -> list:
        """Find similar teams using fuzzy matching."""
        matches = []
        normalized_kp = self._normalize_name(kp_name)
        
        for team in our_teams:
            # Compare with school name
            score = SequenceMatcher(
                None, 
                normalized_kp, 
                self._normalize_name(team.school)
            ).ratio()
            
            if score >= threshold:
                matches.append((team, score))
            else:
                # Also try display name
                if team.display_name:
                    score2 = SequenceMatcher(
                        None,
                        normalized_kp,
                        self._normalize_name(team.display_name)
                    ).ratio()
                    if score2 >= threshold:
                        matches.append((team, score2))
        
        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
