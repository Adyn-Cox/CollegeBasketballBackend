"""
Django management command to explore NCAA API endpoints and detect injuries via player minutes.

This script helps explore the NCAA API structure and identify potential injuries
by analyzing player minutes changes between games.

Usage:
    python manage.py explore_ncaa_api --endpoint teams
    python manage.py explore_ncaa_api --endpoint boxscore --game-id 123456
    python manage.py explore_ncaa_api --detect-injuries --team-id 2246 --games 5
"""
import json
import requests
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from basketball.models import Team, Game
from collections import defaultdict
from django.db.models import Q


NCAA_API_BASE = 'https://ncaa-api.henrygd.me'


class Command(BaseCommand):
    help = 'Explore NCAA API endpoints and detect injuries via player minutes analysis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--endpoint',
            type=str,
            choices=['teams', 'team', 'schedule', 'boxscore', 'roster', 'stats'],
            help='Endpoint to explore'
        )
        parser.add_argument(
            '--team-id',
            type=int,
            help='Team ID for team-specific endpoints'
        )
        parser.add_argument(
            '--game-id',
            type=str,
            help='Game ID for game-specific endpoints'
        )
        parser.add_argument(
            '--year',
            type=int,
            default=datetime.now().year,
            help='Season year (default: current year)'
        )
        parser.add_argument(
            '--detect-injuries',
            action='store_true',
            help='Detect potential injuries by analyzing player minutes'
        )
        parser.add_argument(
            '--games',
            type=int,
            default=5,
            help='Number of recent games to analyze for injury detection (default: 5)'
        )
        parser.add_argument(
            '--minute-drop-threshold',
            type=float,
            default=0.20,
            help='Minimum percentage drop in minutes to flag as potential injury (default: 0.20 = 20%%)'
        )
        parser.add_argument(
            '--extract-game-ids',
            action='store_true',
            help='Extract game IDs from today\'s scoreboard for testing'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date for scoreboard (YYYY-MM-DD format, defaults to today)'
        )

    def handle(self, *args, **options):
        if options['extract_game_ids']:
            self.extract_game_ids(options)
        elif options['detect_injuries']:
            self.detect_injuries(options)
        elif options['endpoint']:
            self.explore_endpoint(options)
        else:
            self.stdout.write(self.style.ERROR('Please specify --endpoint, --detect-injuries, or --extract-game-ids'))
            self.show_help()

    def show_help(self):
        """Show available endpoints and usage examples."""
        self.stdout.write(self.style.SUCCESS('\n=== NCAA API Explorer ===\n'))
        self.stdout.write('Available endpoints to explore:')
        self.stdout.write('  teams      - List all teams')
        self.stdout.write('  team       - Get team details (requires --team-id)')
        self.stdout.write('  schedule   - Get team schedule (requires --team-id)')
        self.stdout.write('  boxscore   - Get game box score (requires --game-id)')
        self.stdout.write('  roster     - Get team roster (requires --team-id)')
        self.stdout.write('  stats      - Get player stats\n')
        self.stdout.write('Examples:')
        self.stdout.write('  python manage.py explore_ncaa_api --endpoint teams')
        self.stdout.write('  python manage.py explore_ncaa_api --endpoint team --team-id 2246')
        self.stdout.write('  python manage.py explore_ncaa_api --endpoint boxscore --game-id 123456')
        self.stdout.write('  python manage.py explore_ncaa_api --detect-injuries --team-id 2246 --games 5\n')

    def explore_endpoint(self, options):
        """Explore a specific endpoint."""
        endpoint = options['endpoint']
        
        if endpoint == 'teams':
            self.explore_teams(options)
        elif endpoint == 'team':
            if not options['team_id']:
                self.stdout.write(self.style.ERROR('--team-id required for team endpoint'))
                return
            self.explore_team(options)
        elif endpoint == 'schedule':
            if not options['team_id']:
                self.stdout.write(self.style.ERROR('--team-id required for schedule endpoint'))
                return
            self.explore_schedule(options)
        elif endpoint == 'boxscore':
            if not options['game_id']:
                self.stdout.write(self.style.ERROR('--game-id required for boxscore'))
                return
            self.explore_boxscore(options)
        elif endpoint == 'roster':
            if not options['team_id']:
                self.stdout.write(self.style.ERROR('--team-id required for roster endpoint'))
                return
            self.explore_roster(options)
        elif endpoint == 'stats':
            self.explore_stats(options)

    def explore_teams(self, options):
        """Explore teams endpoint."""
        self.stdout.write(f'\n=== Exploring Teams Endpoint ===\n')
        
        # Try different URL patterns
        urls_to_try = [
            f"{NCAA_API_BASE}/teams",
            f"{NCAA_API_BASE}/teams?year={options['year']}",
            f"{NCAA_API_BASE}/schools-index",  # We know this one works
        ]
        
        for url in urls_to_try:
            self.stdout.write(f'Trying: {url}')
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.stdout.write(self.style.SUCCESS(f'✓ Success! Status: {response.status_code}'))
                    self.print_json_structure(data, max_items=3)
                    return
                else:
                    self.stdout.write(self.style.WARNING(f'  Status: {response.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))
        
        self.stdout.write(self.style.ERROR('\nNo working teams endpoint found'))

    def explore_team(self, options):
        """Explore team details endpoint."""
        self.stdout.write(f'\n=== Exploring Team Details ===\n')
        team_id = options['team_id']
        
        urls_to_try = [
            f"{NCAA_API_BASE}/teams/{team_id}",
            f"{NCAA_API_BASE}/team/{team_id}",
            f"{NCAA_API_BASE}/teams/{team_id}?year={options['year']}",
        ]
        
        for url in urls_to_try:
            self.stdout.write(f'Trying: {url}')
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.stdout.write(self.style.SUCCESS(f'✓ Success!'))
                    self.print_json_structure(data)
                    return
                else:
                    self.stdout.write(self.style.WARNING(f'  Status: {response.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))
        
        self.stdout.write(self.style.ERROR('\nNo working team endpoint found'))

    def explore_schedule(self, options):
        """Explore team schedule endpoint."""
        self.stdout.write(f'\n=== Exploring Team Schedule ===\n')
        team_id = options['team_id']
        
        urls_to_try = [
            f"{NCAA_API_BASE}/teams/{team_id}/schedule",
            f"{NCAA_API_BASE}/teams/{team_id}/schedule?year={options['year']}",
            f"{NCAA_API_BASE}/team/{team_id}/schedule",
            f"{NCAA_API_BASE}/team/{team_id}/games",
        ]
        
        for url in urls_to_try:
            self.stdout.write(f'Trying: {url}')
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.stdout.write(self.style.SUCCESS(f'✓ Success!'))
                    self.print_json_structure(data, max_items=2)
                    
                    # Extract game IDs if available
                    if isinstance(data, list) and len(data) > 0:
                        self.stdout.write(f'\nFound {len(data)} games')
                        if 'gameId' in str(data[0]) or 'id' in str(data[0]):
                            self.stdout.write('Game IDs found in schedule!')
                    elif isinstance(data, dict) and 'games' in data:
                        games = data['games']
                        self.stdout.write(f'Found {len(games)} games')
                    
                    return
                else:
                    self.stdout.write(self.style.WARNING(f'  Status: {response.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))
        
        self.stdout.write(self.style.ERROR('\nNo working schedule endpoint found'))

    def explore_boxscore(self, options):
        """Explore box score endpoint - THE GOLDMINE."""
        self.stdout.write(f'\n=== Exploring Box Score (INJURY DETECTION KEY) ===\n')
        game_id = options['game_id']
        
        urls_to_try = [
            f"{NCAA_API_BASE}/games/{game_id}/boxscore",
            f"{NCAA_API_BASE}/games/{game_id}/boxscore",
            f"{NCAA_API_BASE}/game/{game_id}/boxscore",
            f"{NCAA_API_BASE}/boxscore/{game_id}",
            f"{NCAA_API_BASE}/scoreboard/basketball-men/d1/2026/01/20",  # We know this pattern
        ]
        
        for url in urls_to_try:
            self.stdout.write(f'Trying: {url}')
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.stdout.write(self.style.SUCCESS(f'✓ Success!'))
                    
                    # Look for player minutes specifically
                    self.stdout.write('\n=== Analyzing for Player Minutes ===')
                    self.find_player_minutes(data)
                    
                    self.print_json_structure(data, max_items=5)
                    return
                else:
                    self.stdout.write(self.style.WARNING(f'  Status: {response.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))
        
        self.stdout.write(self.style.ERROR('\nNo working boxscore endpoint found'))

    def explore_roster(self, options):
        """Explore roster endpoint."""
        self.stdout.write(f'\n=== Exploring Team Roster ===\n')
        team_id = options['team_id']
        
        urls_to_try = [
            f"{NCAA_API_BASE}/teams/{team_id}/roster",
            f"{NCAA_API_BASE}/team/{team_id}/roster",
            f"{NCAA_API_BASE}/teams/{team_id}/players",
        ]
        
        for url in urls_to_try:
            self.stdout.write(f'Trying: {url}')
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.stdout.write(self.style.SUCCESS(f'✓ Success!'))
                    self.print_json_structure(data, max_items=3)
                    return
                else:
                    self.stdout.write(self.style.WARNING(f'  Status: {response.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))
        
        self.stdout.write(self.style.ERROR('\nNo working roster endpoint found'))

    def explore_stats(self, options):
        """Explore player stats endpoint."""
        self.stdout.write(f'\n=== Exploring Player Stats ===\n')
        
        urls_to_try = [
            f"{NCAA_API_BASE}/stats/players",
            f"{NCAA_API_BASE}/stats/players?year={options['year']}",
            f"{NCAA_API_BASE}/players/stats",
        ]
        
        for url in urls_to_try:
            self.stdout.write(f'Trying: {url}')
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.stdout.write(self.style.SUCCESS(f'✓ Success!'))
                    self.print_json_structure(data, max_items=2)
                    return
                else:
                    self.stdout.write(self.style.WARNING(f'  Status: {response.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))
        
        self.stdout.write(self.style.ERROR('\nNo working stats endpoint found'))

    def extract_game_ids(self, options=None):
        """Extract game IDs from today's scoreboard for testing boxscore endpoints."""
        self.stdout.write(self.style.SUCCESS('\n=== Extracting Game IDs from Scoreboard ===\n'))
        
        # Get date (from options or default to today)
        if options and options.get('date'):
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            # Use today - try tomorrow first in case API is ahead (timezone issues)
            from django.utils import timezone
            today = timezone.now().date()
            tomorrow = today + timedelta(days=1)
            # Try tomorrow first since API might be ahead
            dates_to_try = [tomorrow, today]
            target_date = tomorrow  # Use tomorrow as primary for display
        
        date_str = target_date.strftime("%Y/%m/%d")
        
        all_games = []
        for date_to_try in dates_to_try:
            date_str_try = date_to_try.strftime("%Y/%m/%d")
            url = f"{NCAA_API_BASE}/scoreboard/basketball-men/d1/{date_str_try}"
            
            self.stdout.write(f'Trying: {date_to_try} ({date_str_try})...')
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    games = data.get('games', [])
                    if games:
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Found {len(games)} games'))
                        all_games.extend([(g, date_str_try) for g in games])
                    else:
                        self.stdout.write(f'  No games found')
                else:
                    self.stdout.write(f'  Status: {response.status_code}')
            except Exception as e:
                self.stdout.write(f'  Error: {e}')
        
        if not all_games:
            self.stdout.write(self.style.ERROR('\nNo games found for any date'))
            return
        
        games = [g[0] for g in all_games]  # Extract just the game objects
        self.stdout.write(f'\nTotal games found: {len(games)}\n')
        self.stdout.write('Game IDs to test boxscore endpoints:\n')
        
        game_ids = []
        for i, game_wrapper in enumerate(games[:10]):  # Show first 10
            game = game_wrapper.get('game', {})
            game_id = game.get('gameID')
            if game_id:
                away = game.get('away', {}).get('names', {}).get('short', 'Unknown')
                home = game.get('home', {}).get('names', {}).get('short', 'Unknown')
                status = game.get('finalMessage', game.get('gameState', 'Unknown'))
                
                self.stdout.write(f'  {i+1}. Game ID: {game_id} - {away} @ {home} ({status})')
                game_ids.append(game_id)
        
        if game_ids:
            self.stdout.write(f'\n=== Testing Boxscore Endpoints ===\n')
            self.stdout.write('Testing first game ID with different patterns...\n')
            test_game_id = game_ids[0]
            
            patterns = [
                f"{NCAA_API_BASE}/games/{test_game_id}/boxscore",
                f"{NCAA_API_BASE}/game/{test_game_id}/boxscore",
                f"{NCAA_API_BASE}/boxscore/{test_game_id}",
                f"{NCAA_API_BASE}/games/{test_game_id}/box",
                f"{NCAA_API_BASE}/boxscore/game/{test_game_id}",
            ]
            
            for pattern in patterns:
                self.stdout.write(f'  Trying: {pattern}')
                try:
                    resp = requests.get(pattern, timeout=10)
                    if resp.status_code == 200:
                        self.stdout.write(self.style.SUCCESS(f'    ✓ SUCCESS! Status 200'))
                        # Quick check for player data
                        data = resp.json()
                        if 'player' in str(data).lower() or 'min' in str(data).lower():
                            self.stdout.write(self.style.SUCCESS(f'    🎯 Contains player/minutes data!'))
                        break
                    else:
                        self.stdout.write(f'    Status: {resp.status_code}')
                except Exception as e:
                    self.stdout.write(f'    Error: {e}')
            
            # Save game IDs for later use
            with open('game_ids_for_testing.json', 'w') as f:
                json.dump({
                    'date': date_str,
                    'game_ids': game_ids,
                    'games': [
                        {
                            'gameID': g.get('game', {}).get('gameID'),
                            'away': g.get('game', {}).get('away', {}).get('names', {}).get('short'),
                            'home': g.get('game', {}).get('home', {}).get('names', {}).get('short'),
                        }
                        for g in games[:20]
                    ]
                }, f, indent=2)
            
            self.stdout.write(f'\n  Game IDs saved to: game_ids_for_testing.json')
        else:
            self.stdout.write(self.style.WARNING('  No game IDs found'))

    def find_player_minutes(self, data, path=""):
        """Recursively search for player minutes in JSON structure."""
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                
                # Look for minute-related keys
                if any(term in key.lower() for term in ['min', 'minute', 'mp', 'time']):
                    self.stdout.write(self.style.SUCCESS(f'  Found minutes field: {new_path} = {value}'))
                
                # Look for player data
                if any(term in key.lower() for term in ['player', 'roster', 'boxscore', 'stats']):
                    if isinstance(value, (dict, list)):
                        self.find_player_minutes(value, new_path)
                
                # Recurse into nested structures
                if isinstance(value, (dict, list)):
                    self.find_player_minutes(value, new_path)
        
        elif isinstance(data, list):
            for i, item in enumerate(data[:3]):  # Check first 3 items
                if isinstance(item, (dict, list)):
                    self.find_player_minutes(item, f"{path}[{i}]")

    def print_json_structure(self, data, max_items=3, indent=0):
        """Print JSON structure in a readable format."""
        indent_str = "  " * indent
        
        if isinstance(data, dict):
            for i, (key, value) in enumerate(list(data.items())[:max_items]):
                if isinstance(value, (dict, list)):
                    self.stdout.write(f"{indent_str}{key}: {type(value).__name__}")
                    self.print_json_structure(value, max_items, indent + 1)
                else:
                    self.stdout.write(f"{indent_str}{key}: {value}")
            if len(data) > max_items:
                self.stdout.write(f"{indent_str}... ({len(data) - max_items} more keys)")
        
        elif isinstance(data, list):
            self.stdout.write(f"{indent_str}List with {len(data)} items")
            if len(data) > 0:
                self.stdout.write(f"{indent_str}First item structure:")
                self.print_json_structure(data[0], max_items, indent + 1)
        
        else:
            self.stdout.write(f"{indent_str}{data}")

    def detect_injuries(self, options):
        """Detect potential injuries by analyzing player minutes across games."""
        self.stdout.write(self.style.SUCCESS('\n=== INJURY DETECTION SYSTEM ===\n'))
        
        team_id = options['team_id']
        if not team_id:
            self.stdout.write(self.style.ERROR('--team-id required for injury detection'))
            return
        
        # Try to get team schedule - but also try scoreboard approach
        self.stdout.write(f'Step 1: Getting games for team {team_id}...')
        schedule = self.get_schedule(team_id, options['year'])
        
        # If schedule doesn't work, try getting games from scoreboard
        if not schedule:
            self.stdout.write('  Schedule endpoint not working, trying scoreboard approach...')
            schedule = self.get_games_from_scoreboard(team_id, options['games'])
        
        if not schedule:
            self.stdout.write(self.style.ERROR('Could not fetch games. Try exploring endpoints first.'))
            self.stdout.write('  Tip: Use --endpoint boxscore to find working boxscore patterns')
            return
        
        # Get recent games
        recent_games = schedule[:options['games']]
        self.stdout.write(f'Step 2: Analyzing {len(recent_games)} recent games...\n')
        
        # Collect player minutes across games
        player_minutes = defaultdict(list)  # {player_name: [min1, min2, ...]}
        game_dates = []
        
        for game_data in recent_games:
            # Handle different game data structures
            if isinstance(game_data, dict) and 'game' in game_data:
                game = game_data['game']
                date = game_data.get('date', 'Unknown')
            else:
                game = game_data
                date = self.extract_game_date(game)
            
            game_id = self.extract_game_id(game)
            if not game_id:
                self.stdout.write(f'  ⚠️  Skipping game - no game ID found')
                continue
            
            game_dates.append(date)
            
            self.stdout.write(f'  Fetching box score for game {game_id} ({date})...')
            boxscore = self.get_boxscore(game_id)
            
            if boxscore:
                # Determine which team we're analyzing
                team_slug = None
                try:
                    team = Team.objects.get(id=team_id)
                    team_slug = team.ncaa_slug
                except:
                    pass
                
                minutes = self.extract_player_minutes(boxscore, team_slug)
                if minutes:
                    self.stdout.write(f'    ✓ Found minutes for {len(minutes)} players')
                    for player, mins in minutes.items():
                        player_minutes[player].append(mins)
                else:
                    self.stdout.write(f'    ⚠️  No player minutes found in boxscore')
            else:
                self.stdout.write(f'    ⚠️  Could not fetch boxscore (trying different patterns...)')
                # Try alternative boxscore endpoints
                boxscore = self.try_boxscore_patterns(game_id)
                if boxscore:
                    team_slug = None
                    try:
                        team = Team.objects.get(id=team_id)
                        team_slug = team.ncaa_slug
                    except:
                        pass
                    minutes = self.extract_player_minutes(boxscore, team_slug)
                    if minutes:
                        for player, mins in minutes.items():
                            player_minutes[player].append(mins)
        
        # Analyze minute changes
        self.stdout.write(f'\n=== INJURY ANALYSIS ===\n')
        threshold = options['minute_drop_threshold']
        
        injuries_found = []
        for player, minutes_list in player_minutes.items():
            if len(minutes_list) < 2:
                continue
            
            # Calculate average and recent minutes
            avg_minutes = sum(minutes_list) / len(minutes_list)
            recent_minutes = minutes_list[0]  # Most recent game
            previous_minutes = minutes_list[1] if len(minutes_list) > 1 else avg_minutes
            
            # Check for significant drop
            if avg_minutes > 0:
                drop_pct = (avg_minutes - recent_minutes) / avg_minutes
                
                if drop_pct >= threshold:
                    injuries_found.append({
                        'player': player,
                        'avg_minutes': round(avg_minutes, 1),
                        'recent_minutes': recent_minutes,
                        'previous_minutes': previous_minutes,
                        'drop_pct': round(drop_pct * 100, 1),
                        'severity': 'HIGH' if drop_pct >= 0.40 else 'MEDIUM' if drop_pct >= 0.30 else 'LOW'
                    })
        
        # Report findings
        if injuries_found:
            self.stdout.write(self.style.WARNING(f'\n⚠️  POTENTIAL INJURIES DETECTED ({len(injuries_found)}):\n'))
            for injury in sorted(injuries_found, key=lambda x: x['drop_pct'], reverse=True):
                self.stdout.write(f"  {injury['player']}:")
                self.stdout.write(f"    Avg: {injury['avg_minutes']} min → Recent: {injury['recent_minutes']} min")
                self.stdout.write(f"    Drop: {injury['drop_pct']}% ({injury['severity']} severity)")
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ No significant minute drops detected'))
        
        # Save to file
        output_file = f'injury_report_{team_id}_{datetime.now().strftime("%Y%m%d")}.json'
        with open(output_file, 'w') as f:
            json.dump({
                'team_id': team_id,
                'analysis_date': datetime.now().isoformat(),
                'games_analyzed': len(recent_games),
                'potential_injuries': injuries_found,
                'all_player_minutes': dict(player_minutes)
            }, f, indent=2)
        
        self.stdout.write(f'\n  Report saved to: {output_file}')

    def get_schedule(self, team_id, year):
        """Get team schedule from API."""
        urls = [
            f"{NCAA_API_BASE}/teams/{team_id}/schedule?year={year}",
            f"{NCAA_API_BASE}/team/{team_id}/schedule",
        ]
        
        for url in urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and 'games' in data:
                        return data['games']
            except:
                continue
        return None

    def get_games_from_scoreboard(self, team_slug_or_id, num_games):
        """Get games from scoreboard by searching for team."""
        from datetime import datetime, timedelta
        
        # Try to match team by slug or ID
        team_slug = None
        if isinstance(team_slug_or_id, int):
            # Try to find team slug from our database
            try:
                team = Team.objects.get(id=team_slug_or_id)
                team_slug = team.ncaa_slug
            except Team.DoesNotExist:
                self.stdout.write(f'  Team ID {team_slug_or_id} not found in database')
                return None
        else:
            team_slug = team_slug_or_id
        
        if not team_slug:
            self.stdout.write('  Could not determine team slug')
            return None
        
        self.stdout.write(f'  Searching scoreboard for team: {team_slug}')
        
        # Search last N days of scoreboards
        games_found = []
        today = datetime.now().date()
        
        for days_back in range(14):  # Check last 14 days
            date = today - timedelta(days=days_back)
            date_str = date.strftime("%Y/%m/%d")
            
            url = f"{NCAA_API_BASE}/scoreboard/basketball-men/d1/{date_str}"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'games' in data:
                        for game_wrapper in data['games']:
                            game = game_wrapper.get('game', {})
                            away_slug = game.get('away', {}).get('names', {}).get('seo', '')
                            home_slug = game.get('home', {}).get('names', {}).get('seo', '')
                            
                            if team_slug.lower() in [away_slug.lower(), home_slug.lower()]:
                                games_found.append({
                                    'game': game,
                                    'date': date_str
                                })
                                
                                if len(games_found) >= num_games:
                                    return games_found
            except:
                continue
        
        return games_found if games_found else None

    def get_boxscore(self, game_id):
        """Get box score from API."""
        return self.try_boxscore_patterns(game_id)
    
    def try_boxscore_patterns(self, game_id):
        """Try multiple boxscore endpoint patterns."""
        patterns = [
            f"{NCAA_API_BASE}/games/{game_id}/boxscore",
            f"{NCAA_API_BASE}/game/{game_id}/boxscore",
            f"{NCAA_API_BASE}/boxscore/{game_id}",
            f"{NCAA_API_BASE}/games/{game_id}/box",
            f"{NCAA_API_BASE}/boxscore/game/{game_id}",
            # Try with different game ID formats
            f"{NCAA_API_BASE}/games/{str(game_id).zfill(8)}/boxscore",
        ]
        
        for url in patterns:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    self.stdout.write(f'    ✓ Found boxscore at: {url}')
                    return response.json()
            except:
                continue
        return None

    def extract_game_id(self, game):
        """Extract game ID from game object."""
        if isinstance(game, dict):
            return game.get('gameId') or game.get('id') or game.get('game_id')
        return None

    def extract_game_date(self, game):
        """Extract game date from game object."""
        if isinstance(game, dict):
            return game.get('date') or game.get('gameDate') or 'Unknown'
        return 'Unknown'

    def extract_player_minutes(self, boxscore, team_slug):
        """Extract player minutes from box score."""
        minutes = {}
        
        # Recursively search for player minutes
        def search_minutes(data, path="", current_team=None):
            if isinstance(data, dict):
                # Check if this is a team object
                if 'names' in data and 'seo' in data.get('names', {}):
                    current_team = data['names']['seo'].lower()
                
                # Look for player arrays
                if 'players' in data or 'roster' in data or 'boxscore' in data:
                    players = data.get('players') or data.get('roster') or data.get('boxscore', {}).get('players', [])
                    if isinstance(players, list):
                        for player in players:
                            if isinstance(player, dict):
                                player_name = player.get('name') or player.get('playerName') or player.get('player')
                                # Look for minutes - try multiple field names
                                for key in player.keys():
                                    key_lower = key.lower()
                                    if any(term in key_lower for term in ['min', 'mp', 'minutesplayed']):
                                        value = player[key]
                                        if isinstance(value, (int, float)) and value > 0:
                                            if player_name:
                                                minutes[player_name] = value
                                            break
                
                # Look for player objects directly
                if 'name' in data or 'player' in data or 'playerName' in data:
                    player_name = data.get('name') or data.get('player') or data.get('playerName')
                    # Look for minutes in same object
                    for key, value in data.items():
                        key_lower = key.lower()
                        if any(term in key_lower for term in ['min', 'mp', 'minutesplayed']):
                            if isinstance(value, (int, float)) and value > 0:
                                if player_name:
                                    minutes[player_name] = value
                                break
                
                # Recurse into nested structures
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        search_minutes(value, f"{path}.{key}" if path else key, current_team)
            
            elif isinstance(data, list):
                for i, item in enumerate(data[:20]):  # Limit recursion
                    if isinstance(item, (dict, list)):
                        search_minutes(item, f"{path}[{i}]" if path else f"[{i}]", current_team)
        
        search_minutes(boxscore)
        
        # Filter by team if team_slug provided
        if team_slug and minutes:
            # If we can't filter by team in the data, return all minutes
            # (The boxscore structure might not have team separation)
            pass
        
        return minutes
