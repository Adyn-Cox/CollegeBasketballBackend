"""
Django management command for automated model retraining.

Checks if retraining is needed based on:
1. New games since last training
2. KenPom data updates
3. Time since last training

Usage:
    python manage.py auto_retrain                    # Check and retrain if needed
    python manage.py auto_retrain --force            # Force retrain
    python manage.py auto_retrain --check-only       # Just check, don't train
    python manage.py auto_retrain --min-new-games=50 # Require 50 new games
"""
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone


class Command(BaseCommand):
    help = 'Auto-retrain ML model when new data is available'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force retraining regardless of conditions'
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check if retraining is needed, do not train'
        )
        parser.add_argument(
            '--min-new-games',
            type=int,
            default=25,
            help='Minimum new games required to trigger retrain (default: 25)'
        )
        parser.add_argument(
            '--max-age-hours',
            type=int,
            default=24,
            help='Max hours since last training before forcing retrain (default: 24)'
        )
        parser.add_argument(
            '--season',
            type=int,
            default=2026,
            help='Season year (default: 2026)'
        )

    def handle(self, *args, **options):
        from basketball.models import Game, MLModelVersion, KenPomRating
        
        force = options['force']
        check_only = options['check_only']
        min_new_games = options['min_new_games']
        max_age_hours = options['max_age_hours']
        season = options['season']
        
        self.stdout.write('=' * 50)
        self.stdout.write('ML Model Auto-Retrain Check')
        self.stdout.write('=' * 50)
        
        # Get current active model
        active_model = MLModelVersion.objects.filter(is_active=True).first()
        
        if active_model:
            self.stdout.write(f'\nCurrent model: {active_model.version}')
            self.stdout.write(f'  Trained: {active_model.training_date}')
            self.stdout.write(f'  Accuracy: {active_model.test_accuracy:.2%}')
            self.stdout.write(f'  Games trained on: {active_model.training_games_count}')
            
            model_age = timezone.now() - active_model.training_date
            model_age_hours = model_age.total_seconds() / 3600
            self.stdout.write(f'  Age: {model_age_hours:.1f} hours')
        else:
            self.stdout.write('\n⚠️  No active model found!')
            model_age_hours = float('inf')
        
        # Count final games
        total_final_games = Game.objects.filter(
            status='final',
            season=season
        ).count()
        self.stdout.write(f'\nTotal final games (season {season}): {total_final_games}')
        
        # Count games since last training
        if active_model:
            new_games = Game.objects.filter(
                status='final',
                season=season,
                updated_at__gt=active_model.training_date
            ).count()
            self.stdout.write(f'New games since training: {new_games}')
        else:
            new_games = total_final_games
        
        # Check KenPom update
        latest_kenpom = KenPomRating.objects.filter(season=season).order_by('-updated_at').first()
        if latest_kenpom and active_model:
            kenpom_newer = latest_kenpom.updated_at > active_model.training_date
            self.stdout.write(f'KenPom updated since training: {"Yes" if kenpom_newer else "No"}')
        else:
            kenpom_newer = True
        
        # Determine if retraining is needed
        reasons = []
        
        if force:
            reasons.append('Force flag set')
        
        if not active_model:
            reasons.append('No active model')
        
        if new_games >= min_new_games:
            reasons.append(f'{new_games} new games (min: {min_new_games})')
        
        if model_age_hours >= max_age_hours:
            reasons.append(f'Model age {model_age_hours:.1f}h (max: {max_age_hours}h)')
        
        if kenpom_newer and new_games > 0:
            reasons.append('KenPom data updated')
        
        # Decision
        self.stdout.write('\n' + '-' * 50)
        
        if reasons:
            self.stdout.write(self.style.WARNING('\n🔄 RETRAINING RECOMMENDED'))
            self.stdout.write('Reasons:')
            for reason in reasons:
                self.stdout.write(f'  • {reason}')
            
            if check_only:
                self.stdout.write('\n(Check-only mode - skipping training)')
                return
            
            # Perform retraining
            self.stdout.write('\n' + '=' * 50)
            self.stdout.write('Starting retraining...')
            self.stdout.write('=' * 50 + '\n')
            
            version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            try:
                call_command(
                    'train_ml_model',
                    season=season,
                    model_version=version,
                    activate=True,
                    verbosity=1
                )
                
                self.stdout.write(self.style.SUCCESS(f'\n✅ Model {version} trained and activated!'))
                
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'\n❌ Training failed: {e}'))
                return
        
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Model is up-to-date'))
            self.stdout.write('No retraining needed.')
        
        self.stdout.write('')
