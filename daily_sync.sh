#!/bin/bash
# =============================================================================
# Daily Data Sync & Model Retrain Script
# 
# Run this daily (e.g., via cron) to keep data and models up-to-date
# 
# Cron example (run at 6 AM daily):
#   0 6 * * * /path/to/CollegeBasketballBackend/daily_sync.sh >> /var/log/basketball_sync.log 2>&1
#
# Required environment variables:
#   KENPOM_API_KEY - Your KenPom API key
#
# Usage:
#   ./daily_sync.sh           # Full daily sync
#   ./daily_sync.sh --skip-ml # Skip ML retraining
# =============================================================================

set -e

cd "$(dirname "$0")"
source .venv/bin/activate

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

SEASON=${SEASON:-2026}
DATE=$(date +%Y-%m-%d)
SKIP_ML=false

for arg in "$@"; do
    case $arg in
        --skip-ml) SKIP_ML=true ;;
    esac
done

echo ""
echo "========================================"
echo "🏀 College Basketball Daily Sync"
echo "   Date: $DATE"
echo "   Season: $SEASON"
echo "========================================"
echo ""

# =============================================================================
# STEP 1: Sync Games
# =============================================================================
echo "📅 STEP 1: Syncing Games"
echo "------------------------"

# Sync today and yesterday (in case late games)
python manage.py sync_games --days=3 2>&1 | grep -E "(created|updated|Total)" || true

echo ""

# =============================================================================
# STEP 2: Sync Box Scores (for injuries & player stats)
# =============================================================================
echo "📊 STEP 2: Syncing Box Scores"
echo "-----------------------------"

python manage.py sync_box_scores --days=3 2>&1 | grep -E "(Synced|Detected|Updated)" | head -10 || true

echo ""

# =============================================================================
# STEP 3: Sync KenPom Data
# =============================================================================
echo "📈 STEP 3: Syncing KenPom Data"
echo "------------------------------"

if [ -z "$KENPOM_API_KEY" ]; then
    echo "⚠️  KENPOM_API_KEY not set - skipping KenPom sync"
else
    # Ratings (most important - updates daily)
    echo "  → Ratings..."
    python manage.py sync_kenpom_ratings --season=$SEASON 2>&1 | grep -E "(Created|Updated|Skipped)" | head -3 || true
    
    # Four Factors (weekly is fine)
    if [ "$(date +%u)" -eq 1 ]; then  # Monday only
        echo "  → Four Factors (weekly)..."
        python manage.py sync_kenpom_four_factors --season=$SEASON 2>&1 | tail -2 || true
    fi
    
    # Height/Experience (weekly is fine)
    if [ "$(date +%u)" -eq 1 ]; then  # Monday only
        echo "  → Height/Experience (weekly)..."
        python manage.py sync_kenpom_height --season=$SEASON 2>&1 | tail -2 || true
    fi
fi

echo ""

# =============================================================================
# STEP 4: Auto-Retrain ML Model (if needed)
# =============================================================================
if [ "$SKIP_ML" = false ]; then
    echo "🤖 STEP 4: Checking ML Model"
    echo "----------------------------"
    
    # Auto-retrain if 25+ new games or model > 24h old
    python manage.py auto_retrain --season=$SEASON --min-new-games=25 --max-age-hours=24 2>&1 | grep -E "(model|RECOMMENDED|trained|up-to-date)" || true
    
    echo ""
fi

# =============================================================================
# STEP 5: Generate predictions for today's games
# =============================================================================
echo "🔮 STEP 5: Generating Predictions"
echo "----------------------------------"

python manage.py generate_ml_predictions --days=2 2>&1 | grep -E "(Generated|predictions)" | head -3 || true

echo ""

# =============================================================================
# Summary
# =============================================================================
echo "========================================"
echo "✅ Daily Sync Complete"
echo "   Finished: $(date)"
echo "========================================"

# Quick stats
echo ""
echo "Database stats:"
python -c "
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()
from basketball.models import Game, Team, KenPomRating, InjuryReport, MLModelVersion
print(f'  Teams: {Team.objects.count()}')
print(f'  Games (final): {Game.objects.filter(status=\"final\").count()}')
print(f'  Games (scheduled): {Game.objects.filter(status=\"scheduled\").count()}')
print(f'  KenPom Ratings: {KenPomRating.objects.count()}')
print(f'  Active Injuries: {InjuryReport.objects.filter(is_active=True).count()}')
model = MLModelVersion.objects.filter(is_active=True).first()
if model:
    print(f'  Active Model: {model.version} ({model.test_accuracy:.1%} accuracy)')
"
