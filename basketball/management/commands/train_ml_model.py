"""
Django management command to train ML prediction model.

Usage:
    python manage.py train_ml_model --season=2025
    python manage.py train_ml_model --season=2025 --min-games=500
    python manage.py train_ml_model --season=2025 --activate
"""
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = 'Train XGBoost ML model for game predictions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            help='Season year to train on (defaults to all available seasons)'
        )
        parser.add_argument(
            '--seasons',
            type=str,
            help='Comma-separated seasons or range (e.g., "2020,2021,2026" or "2020-2026")'
        )
        parser.add_argument(
            '--min-games',
            type=int,
            default=100,
            help='Minimum number of games required for training (default: 100)'
        )
        parser.add_argument(
            '--model-version',
            type=str,
            dest='model_version',
            help='Model version string (defaults to v{timestamp})'
        )
        parser.add_argument(
            '--activate',
            action='store_true',
            help='Activate this model after training'
        )
        parser.add_argument(
            '--test-size',
            type=float,
            default=0.2,
            help='Fraction of data for testing (default: 0.2)'
        )
        parser.add_argument(
            '--max-depth',
            type=int,
            default=6,
            help='XGBoost max_depth parameter (default: 6)'
        )
        parser.add_argument(
            '--learning-rate',
            type=float,
            default=0.03,
            help='XGBoost learning_rate parameter (default: 0.03)'
        )
        parser.add_argument(
            '--n-estimators',
            type=int,
            default=1000,
            help='XGBoost n_estimators parameter (default: 1000)'
        )
        parser.add_argument(
            '--time-split',
            action='store_true',
            default=True,
            help='Use time-based train/test split (recommended, default: True)'
        )
        parser.add_argument(
            '--random-split',
            action='store_true',
            help='Use random train/test split instead of time-based'
        )
        parser.add_argument(
            '--no-weights',
            action='store_true',
            help='Disable sample weighting (weight all games equally)'
        )
        parser.add_argument(
            '--cv',
            action='store_true',
            help='Run time-series cross-validation before final training'
        )
        parser.add_argument(
            '--cv-folds',
            type=int,
            default=5,
            help='Number of CV folds (default: 5)'
        )

    def handle(self, *args, **options):
        season = options.get('season')
        min_games = options['min_games']
        version = options.get('model_version')
        activate = options.get('activate', False)
        test_size = options['test_size']
        
        # Generate version if not provided
        if not version:
            version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.stdout.write(f'Training ML model {version}...')
        
        # Check for required libraries
        try:
            import xgboost
            import sklearn
            import joblib
            import numpy as np
        except ImportError as e:
            self.stderr.write(self.style.ERROR(
                f'Missing required library: {e}\n'
                'Install with: pip install xgboost scikit-learn joblib numpy'
            ))
            return
        
        # Import models
        from basketball.models import Game, MLModelVersion
        from basketball.ml_model import ModelTrainer
        from basketball.ml_features import get_feature_extractor
        
        # Parse seasons argument
        seasons_list = None
        seasons_str = options.get('seasons')
        
        if seasons_str:
            if '-' in seasons_str and ',' not in seasons_str:
                # Range format: "2020-2026"
                start, end = map(int, seasons_str.split('-'))
                seasons_list = list(range(start, end + 1))
            else:
                # Comma-separated: "2020,2021,2026"
                seasons_list = [int(s.strip()) for s in seasons_str.split(',')]
        elif season:
            seasons_list = [season]
        
        # Get games for training
        self.stdout.write('Loading games...')
        games_qs = Game.objects.filter(status='final').select_related(
            'home_team', 'away_team', 'venue',
            'home_team__conference', 'away_team__conference'
        )
        
        if seasons_list:
            games_qs = games_qs.filter(season__in=seasons_list)
            self.stdout.write(f'  Filtering to seasons: {seasons_list}')
        elif season:
            games_qs = games_qs.filter(season=season)
            self.stdout.write(f'  Filtering to season {season}')
        
        games = list(games_qs.order_by('date'))
        self.stdout.write(f'  Found {len(games)} final games')
        
        if len(games) < min_games:
            self.stderr.write(self.style.ERROR(
                f'Not enough games for training. Found {len(games)}, need at least {min_games}.'
            ))
            return
        
        # Prepare training data
        self.stdout.write('Extracting features...')
        trainer = ModelTrainer()
        
        try:
            X, y, feature_names, game_dates = trainer.prepare_training_data(games, use_archive=True)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error preparing training data: {e}'))
            import traceback
            self.stderr.write(traceback.format_exc())
            return
        
        self.stdout.write(f'  Extracted {len(X)} samples with {len(feature_names)} features')
        
        if len(X) < min_games:
            self.stderr.write(self.style.ERROR(
                f'Not enough valid samples after feature extraction. '
                f'Got {len(X)}, need at least {min_games}.'
            ))
            return
        
        # Hyperparameters
        hyperparameters = {
            'max_depth': options['max_depth'],
            'learning_rate': options['learning_rate'],
            'n_estimators': options['n_estimators'],
        }
        
        # Determine split type and weighting
        use_time_split = not options.get('random_split', False)
        use_weights = not options.get('no_weights', False)
        current_season = max(seasons_list) if seasons_list else (season if season else 2026)
        
        # Run time-series cross-validation if requested
        if options.get('cv', False):
            self.stdout.write('')
            self.stdout.write('Running time-series cross-validation...')
            cv_folds = options.get('cv_folds', 5)
            
            try:
                cv_results = trainer.time_series_cv(
                    X, y, game_dates, feature_names,
                    n_splits=cv_folds,
                    hyperparameters=hyperparameters
                )
                
                self.stdout.write(self.style.SUCCESS(f'  CV Results ({cv_results["n_splits"]} folds):'))
                self.stdout.write(f'    Accuracy: {cv_results["accuracy_mean"]:.2%} ± {cv_results["accuracy_std"]:.2%}')
                self.stdout.write(f'    Log Loss: {cv_results["log_loss_mean"]:.4f} ± {cv_results["log_loss_std"]:.4f}')
                self.stdout.write(f'    Brier:    {cv_results["brier_mean"]:.4f} ± {cv_results["brier_std"]:.4f}')
                self.stdout.write(f'    Per-fold: {[f"{a:.1%}" for a in cv_results["fold_accuracies"]]}')
            except Exception as e:
                self.stderr.write(f'  CV failed: {e}')
            
            self.stdout.write('')
        
        # Train model
        self.stdout.write('Training XGBoost model...')
        self.stdout.write(f'  Hyperparameters: {hyperparameters}')
        self.stdout.write(f'  Split type: {"Time-based (recommended)" if use_time_split else "Random"}')
        self.stdout.write(f'  Sample weights: {"Enabled (recent games weighted higher)" if use_weights else "Disabled"}')
        
        try:
            results = trainer.train(
                X, y, feature_names,
                version=version,
                hyperparameters=hyperparameters,
                test_size=test_size,
                game_dates=game_dates,
                time_based_split=use_time_split,
                use_sample_weights=use_weights,
                current_season=current_season
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error training model: {e}'))
            import traceback
            self.stderr.write(traceback.format_exc())
            return
        
        # Display results
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Training completed!'))
        self.stdout.write(f'  Version: {results["version"]}')
        self.stdout.write(f'  Model path: {results["model_path"]}')
        self.stdout.write(f'  Training games: {results["training_games"]}')
        self.stdout.write(f'  Test games: {results["test_games"]}')
        self.stdout.write(f'  Test accuracy: {results["accuracy"]:.2%}')
        self.stdout.write(f'  Test log loss: {results["log_loss"]:.4f}')
        if results.get('brier_score'):
            self.stdout.write(f'  Brier score: {results["brier_score"]:.4f} (lower=better calibrated)')
        
        if results.get('feature_importance_plot'):
            self.stdout.write(f'  Feature importance plot: {results["feature_importance_plot"]}')
        
        # Create database record
        self.stdout.write('')
        self.stdout.write('Creating model version record...')
        
        try:
            model_version = trainer.create_model_version_record(results)
            self.stdout.write(f'  Created MLModelVersion: {model_version}')
            
            if activate:
                model_version.activate()
                self.stdout.write(self.style.SUCCESS(f'  Model {version} activated!'))
            else:
                self.stdout.write(
                    f'  To activate this model, run:\n'
                    f'  python manage.py activate_ml_model --version={version}'
                )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error creating model record: {e}'))
            return
        
        # Show top features
        self.stdout.write('')
        self.stdout.write('Top 10 features by importance:')
        
        try:
            import joblib
            model_data = joblib.load(results['model_path'])
            model = model_data['model']
            importance = model.get_score(importance_type='gain')
            
            # Map to feature names
            importance_dict = {}
            for i, name in enumerate(feature_names):
                key = f'f{i}'
                importance_dict[name] = importance.get(key, 0.0)
            
            # Sort and show top 10
            sorted_importance = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:10]
            
            for i, (name, score) in enumerate(sorted_importance, 1):
                self.stdout.write(f'  {i}. {name}: {score:.2f}')
                
        except Exception as e:
            self.stdout.write(f'  Could not display feature importance: {e}')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Done!'))
