#!/usr/bin/env python3
"""
Standalone script to quickly test NCAA API endpoints.
Can be run without Django: python test_ncaa_api.py

This helps you quickly explore the API structure before using the full Django command.
"""
import json
import requests
import sys

NCAA_API_BASE = 'https://ncaa-api.henrygd.me'


def test_endpoint(url, description):
    """Test a single endpoint and print results."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print('='*60)
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✓ Success! Response type: {type(data).__name__}")
                
                if isinstance(data, dict):
                    print(f"Keys: {list(data.keys())[:10]}")
                elif isinstance(data, list):
                    print(f"List length: {len(data)}")
                    if len(data) > 0:
                        print(f"First item keys: {list(data[0].keys())[:10] if isinstance(data[0], dict) else 'N/A'}")
                
                # Look for player minutes
                if 'min' in str(data).lower() or 'minute' in str(data).lower():
                    print("🎯 FOUND MINUTES DATA!")
                
                # Save sample to file
                safe_desc = description.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '').lower()
                filename = f"api_response_{safe_desc}.json"
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"Sample saved to: {filename}")
                
                return True, data
            except json.JSONDecodeError:
                print("⚠️  Response is not JSON")
                print(f"First 500 chars: {response.text[:500]}")
                return False, None
        else:
            print(f"✗ Failed with status {response.status_code}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        return False, None


def main():
    """Run a series of API tests."""
    print("\n" + "="*60)
    print("NCAA API EXPLORER - Quick Test")
    print("="*60)
    
    # Test 1: Teams endpoint
    test_endpoint(
        f"{NCAA_API_BASE}/schools-index",
        "Schools Index (known working endpoint)"
    )
    
    # Test 2: Try different team endpoints
    team_id = 2246  # Example: Duke (you'll need to find actual IDs)
    test_endpoint(
        f"{NCAA_API_BASE}/teams/{team_id}",
        f"Team Details (ID: {team_id})"
    )
    
    # Test 3: Schedule
    test_endpoint(
        f"{NCAA_API_BASE}/teams/{team_id}/schedule",
        f"Team Schedule (ID: {team_id})"
    )
    
    # Test 4: Try to get a game from scoreboard (we know this pattern)
    from datetime import datetime
    today = datetime.now()
    date_str = today.strftime("%Y/%m/%d")
    test_endpoint(
        f"{NCAA_API_BASE}/scoreboard/basketball-men/d1/{date_str}",
        f"Today's Scoreboard ({date_str})"
    )
    
    # Test 5: Box score (need actual game ID)
    # This is the most important one!
    print("\n" + "="*60)
    print("⚠️  BOX SCORE TEST")
    print("="*60)
    print("To test box scores, you need a game ID from the scoreboard.")
    print("Extract a game ID from the scoreboard response above,")
    print("then test:")
    print(f"  {NCAA_API_BASE}/games/[GAME_ID]/boxscore")
    
    # Test 6: Roster
    test_endpoint(
        f"{NCAA_API_BASE}/teams/{team_id}/roster",
        f"Team Roster (ID: {team_id})"
    )
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("Check the generated JSON files to see the actual API structure.")
    print("Once you find working endpoints, use the Django command:")
    print("  python manage.py explore_ncaa_api --endpoint [endpoint_name]")


if __name__ == "__main__":
    main()
