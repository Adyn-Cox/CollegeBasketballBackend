#!/bin/bash
# =============================================================================
# ML Model Retraining Script
# Run this after syncing new KenPom data or games
# 
# Usage:
#   ./retrain.sh              # Full retrain with latest data
#   ./retrain.sh --quick      # Quick retrain (fewer trees, faster)
#   ./retrain.sh --no-sync    # Retrain only (skip data sync)
# =============================================================================

set -e

cd "$(dirname "$0")"
source .venv/bin/activate

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Parse arguments
QUICK=false
SKIP_SYNC=false
for arg in "$@"; do
    case $arg in
        --quick) QUICK=true ;;
        --no-sync) SKIP_SYNC=true ;;
    esac
done

SEASON=${SEASON:-2026}
echo "======================================"
echo "ML Model Retraining - Season $SEASON"
echo "======================================"
echo ""

# Step 1: Sync latest data (optional)
if [ "$SKIP_SYNC" = false ]; then
    echo "📥 Step 1: Syncing latest data..."
    echo "-----------------------------------"
    
    # Sync KenPom ratings (requires KENPOM_API_KEY)
    if [ -n "$KENPOM_API_KEY" ]; then
        echo "  → Syncing KenPom ratings..."
        python manage.py sync_kenpom_ratings --season=$SEASON 2>&1 | tail -5
        
        echo "  → Syncing KenPom four factors..."
        python manage.py sync_kenpom_four_factors --season=$SEASON 2>&1 | tail -3
        
        echo "  → Syncing KenPom height..."
        python manage.py sync_kenpom_height --season=$SEASON 2>&1 | tail -3
    else
        echo "  ⚠️  KENPOM_API_KEY not set - skipping KenPom sync"
    fi
    
    # Sync games (last 7 days)
    echo "  → Syncing recent games..."
    python manage.py sync_games --days=7 2>&1 | tail -3
    
    # Sync box scores
    echo "  → Syncing box scores..."
    python manage.py sync_box_scores --days=7 2>&1 | tail -3
    
    echo ""
fi

# Step 2: Train the model
echo "🎓 Step 2: Training ML model..."
echo "-----------------------------------"

# Generate version with timestamp
VERSION="v$(date +%Y%m%d_%H%M%S)"

if [ "$QUICK" = true ]; then
    echo "  → Quick training mode (500 trees, 0.1 LR)"
    python manage.py train_ml_model \
        --season=$SEASON \
        --version=$VERSION \
        --n-estimators=500 \
        --learning-rate=0.1 \
        --activate
else
    echo "  → Full training mode (1000 trees, 0.03 LR)"
    python manage.py train_ml_model \
        --season=$SEASON \
        --version=$VERSION \
        --activate
fi

echo ""
echo "======================================"
echo "✅ Retraining complete!"
echo "   Model version: $VERSION"
echo "======================================"
