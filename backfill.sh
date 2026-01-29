#!/bin/bash
# =============================================================================
# Historical Data Backfill Script
# 
# Syncs multiple seasons of games, KenPom data, and box scores for training
# 
# Recommended: 2020-2026 (5-6 seasons) for best accuracy
# 
# Usage:
#   ./backfill.sh                     # Default: 2020-2026
#   ./backfill.sh 2018 2026           # Custom: 2018-2026
#   ./backfill.sh --kenpom-only       # Only sync KenPom (if games exist)
# =============================================================================

set -e

cd "$(dirname "$0")"
source .venv/bin/activate

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default seasons
START_SEASON=${1:-2020}
END_SEASON=${2:-2026}
KENPOM_ONLY=false

for arg in "$@"; do
    case $arg in
        --kenpom-only) KENPOM_ONLY=true ;;
    esac
done

echo "========================================"
echo "🏀 Historical Data Backfill"
echo "   Seasons: $START_SEASON to $END_SEASON"
echo "========================================"
echo ""

# Season date ranges (NCAA basketball typically Nov-April)
get_season_dates() {
    local season=$1
    local start_year=$((season - 1))
    echo "${start_year}-11-01" "${season}-04-15"
}

# =============================================================================
# STEP 1: Sync KenPom Archive Data
# =============================================================================
echo "📈 STEP 1: Syncing KenPom Archive Data"
echo "--------------------------------------"

if [ -z "$KENPOM_API_KEY" ]; then
    echo "⚠️  KENPOM_API_KEY not set"
    echo "   Set it with: export KENPOM_API_KEY='your-key'"
    echo "   Skipping KenPom sync..."
else
    for season in $(seq $START_SEASON $END_SEASON); do
        echo ""
        echo "  → Season $season:"
        
        # Archive historical ratings (for point-in-time features)
        if [ $season -lt 2026 ]; then
            echo "    Syncing archive..."
            python manage.py sync_kenpom_archive --season=$season 2>&1 | grep -E "(Created|Updated|Error)" | head -2 || true
        fi
        
        # Current/final ratings for that season
        echo "    Syncing ratings..."
        python manage.py sync_kenpom_ratings --season=$season 2>&1 | grep -E "(Created|Updated|Skipped)" | head -2 || true
        
        # Four factors
        echo "    Syncing four factors..."
        python manage.py sync_kenpom_four_factors --season=$season 2>&1 | tail -1 || true
        
        sleep 1  # Rate limit courtesy
    done
fi

if [ "$KENPOM_ONLY" = true ]; then
    echo ""
    echo "✅ KenPom sync complete (--kenpom-only mode)"
    exit 0
fi

# =============================================================================
# STEP 2: Sync Games for Each Season
# =============================================================================
echo ""
echo "📅 STEP 2: Syncing Games"
echo "------------------------"

for season in $(seq $START_SEASON $END_SEASON); do
    read start_date end_date <<< $(get_season_dates $season)
    
    # Calculate days
    start_sec=$(date -d "$start_date" +%s)
    end_sec=$(date -d "$end_date" +%s)
    days=$(( (end_sec - start_sec) / 86400 ))
    
    echo ""
    echo "  → Season $season: $start_date to $end_date (~$days days)"
    
    python manage.py sync_games --date=$start_date --days=$days --season=$season 2>&1 | grep -E "(created|Total)" | tail -2 || true
    
    sleep 2  # Rate limit
done

# =============================================================================
# STEP 3: Sync Box Scores (for player/injury features)
# =============================================================================
echo ""
echo "📊 STEP 3: Syncing Box Scores (takes a while...)"
echo "-------------------------------------------------"

for season in $(seq $START_SEASON $END_SEASON); do
    echo ""
    echo "  → Season $season..."
    
    # Sync box scores - this uses games already in DB
    python manage.py sync_box_scores --season=$season 2>&1 | grep -E "(Synced|Updated|Detected)" | tail -3 || true
done

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "========================================"
echo "✅ Backfill Complete!"
echo "========================================"
echo ""

python -c "
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()
from basketball.models import Game, KenPomRating, PlayerGameStats
from django.db.models import Count

print('Data by season:')
seasons = Game.objects.values('season').annotate(count=Count('id')).order_by('season')
for s in seasons:
    final = Game.objects.filter(season=s['season'], status='final').count()
    kenpom = KenPomRating.objects.filter(season=s['season']).count()
    print(f\"  {s['season']}: {s['count']} games ({final} final), {kenpom} KenPom ratings\")

print(f\"\\nTotal box scores: {PlayerGameStats.objects.count()}\")
"

echo ""
echo "Next: Run './retrain.sh' to train model on all historical data"
