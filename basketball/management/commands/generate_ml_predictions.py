"""
Django management command to generate ML predictions for games.

Usage:
    python manage.py generate_ml_predictions
    python manage.py generate_ml_predictions --date=2025-02-01
    python manage.py generate_ml_predictions --start-date=2025-02-01 --end-date=2025-02-28
    python manage.py generate_ml_predictions --update-existing
"""
from datetime import datetime, timedelta, date
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = 'Generate ML predictions for upcoming games'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Generate predictions for specific date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for date range (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for date range (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing predictions (re-run with latest data)'
        )
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=7,
            help='Number of days ahead to predict (default: 7)'
        )
        parser.add_argument(
            '--model-version',
            type=str,
            help='Specific model version to use (defaults to active model)'
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        start_date_str = options.get('start_date')
        end_date_str = options.get('end_date')
        update_existing = options.get('update_existing', False)
        days_ahead = options['days_ahead']
        model_version = options.get('model_version')
        
        self.stdout.write('Generating ML predictions...')
        
        # Check for required libraries
        try:
            import xgboost
            import numpy as np
        except ImportError as e:
            self.stderr.write(self.style.ERROR(
                f'Missing required library: {e}\n'
                'Install with: pip install xgboost numpy'
            ))
            return
        
        # Import models
        from basketball.models import Game, MLPrediction, MLModelVersion
        from basketball.ml_model import MLPredictor
        
        # Load model
        self.stdout.write('Loading ML model...')
        predictor = MLPredictor()
        
        try:
            if model_version:
                # Load specific version
                version_record = MLModelVersion.objects.filter(version=model_version).first()
                if not version_record:
                    self.stderr.write(self.style.ERROR(f'Model version {model_version} not found'))
                    return
                predictor.load_model(version_record.model_file_path)
            else:
                # Load active model
                predictor.load_model()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error loading model: {e}'))
            return
        
        self.stdout.write(f'  Using model version: {predictor.model_version}')
        
        # Determine date range
        today = date.today()
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_date = target_date
                end_date = target_date
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        elif start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            # Default: today through days_ahead
            start_date = today
            end_date = today + timedelta(days=days_ahead)
        
        self.stdout.write(f'  Date range: {start_date} to {end_date}')
        
        # Get games
        games_qs = Game.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            status__in=['scheduled', 'in_progress']  # Only non-final games
        ).select_related(
            'home_team', 'away_team', 'venue',
            'home_team__conference', 'away_team__conference'
        ).order_by('date', 'time')
        
        if not update_existing:
            # Exclude games that already have predictions
            games_qs = games_qs.exclude(ml_prediction__isnull=False)
        
        games = list(games_qs)
        self.stdout.write(f'  Found {len(games)} games to predict')
        
        if not games:
            self.stdout.write(self.style.WARNING('No games to predict'))
            return
        
        # Generate predictions
        created = 0
        updated = 0
        errors = 0
        
        for game in games:
            try:
                # Make prediction
                prediction = predictor.predict_game(game)
                
                # Create or update MLPrediction record
                ml_pred, was_created = MLPrediction.objects.update_or_create(
                    game=game,
                    defaults={
                        'home_win_probability': prediction['home_win_probability'],
                        'predicted_home_score': prediction['predicted_home_score'],
                        'predicted_away_score': prediction['predicted_away_score'],
                        'predicted_margin': prediction['predicted_margin'],
                        'confidence_score': prediction['confidence_score'],
                        'model_version': prediction['model_version'],
                        'model_features_hash': prediction['features_hash'],
                        
                        # Key features
                        'home_adj_em': prediction['features'].get('home_adj_em'),
                        'away_adj_em': prediction['features'].get('away_adj_em'),
                        'home_momentum': prediction['features'].get('home_momentum'),
                        'away_momentum': prediction['features'].get('away_momentum'),
                        'venue_hca': prediction['features'].get('venue_hca'),
                        'efg_mismatch': prediction['features'].get('efg_mismatch'),
                        'to_mismatch': prediction['features'].get('to_mismatch'),
                        
                        # Full features
                        'features_json': prediction['features'],
                    }
                )
                
                if was_created:
                    created += 1
                else:
                    updated += 1
                
                # Log prediction
                winner = game.home_team.school if prediction['home_win_probability'] > 0.5 else game.away_team.school
                prob = max(prediction['home_win_probability'], 1 - prediction['home_win_probability'])
                
                self.stdout.write(
                    f'  {game.date} {game.away_team.abbreviation} @ {game.home_team.abbreviation}: '
                    f'{winner} ({prob:.1%})'
                )
                
            except Exception as e:
                errors += 1
                self.stderr.write(
                    self.style.WARNING(f'  Error predicting {game}: {e}')
                )
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Prediction generation completed!'))
        self.stdout.write(f'  Created: {created}')
        self.stdout.write(f'  Updated: {updated}')
        self.stdout.write(f'  Errors: {errors}')
        self.stdout.write(f'  Total predictions in DB: {MLPrediction.objects.count()}')
