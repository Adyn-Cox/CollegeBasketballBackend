"""
ML Model wrapper for loading and making predictions.

This module provides a high-level interface for:
- Loading trained XGBoost models
- Making predictions for games
- Managing model versions
"""
import os
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any, List, Tuple

# Lazy imports for ML libraries
_xgb = None
_joblib = None
_np = None


def _import_ml_libs():
    """Lazy import ML libraries."""
    global _xgb, _joblib, _np
    if _xgb is None:
        try:
            import xgboost as xgb
            import joblib
            import numpy as np
            _xgb = xgb
            _joblib = joblib
            _np = np
        except ImportError as e:
            raise ImportError(
                "ML libraries not installed. Run: pip install xgboost scikit-learn joblib numpy"
            ) from e
    return _xgb, _joblib, _np


class MLPredictor:
    """Wrapper for XGBoost prediction model."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the predictor.
        
        Args:
            model_path: Path to the model file. If None, loads active model from DB.
        """
        self.model = None
        self.calibrator = None  # Isotonic calibrator for probability calibration
        self.model_version = None
        self.feature_names = None
        self.model_path = model_path
        self._feature_extractor = None
    
    def _get_feature_extractor(self):
        """Get feature extractor instance."""
        if self._feature_extractor is None:
            from basketball.ml_features import get_feature_extractor
            self._feature_extractor = get_feature_extractor()
        return self._feature_extractor
    
    def load_model(self, model_path: Optional[str] = None) -> bool:
        """
        Load a trained model from file.
        
        Args:
            model_path: Path to model file. If None, loads active model from DB.
            
        Returns:
            True if model loaded successfully
        """
        xgb, joblib, _ = _import_ml_libs()
        
        if model_path is None:
            # Load active model from database
            from basketball.models import MLModelVersion
            active_model = MLModelVersion.objects.filter(is_active=True).first()
            
            if not active_model:
                raise ValueError("No active model found. Train a model first.")
            
            model_path = active_model.model_file_path
            self.model_version = active_model.version
            self.feature_names = active_model.feature_list
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Load the model
        model_data = joblib.load(model_path)
        
        if isinstance(model_data, dict):
            self.model = model_data.get('model')
            self.calibrator = model_data.get('calibrator')  # Load calibrator if available
            self.feature_names = model_data.get('feature_names', self.feature_names)
            self.model_version = model_data.get('version', self.model_version)
        else:
            self.model = model_data
        
        self.model_path = model_path
        return True
    
    def predict_game(self, game) -> Dict[str, Any]:
        """
        Make prediction for a single game.
        
        Args:
            game: Game model instance
            
        Returns:
            Dictionary with prediction results
        """
        if self.model is None:
            self.load_model()
        
        # Extract features
        extractor = self._get_feature_extractor()
        features = extractor.extract_game_features(game)
        
        # Prepare feature vector
        feature_vector = self._prepare_feature_vector(features)
        
        # Make prediction
        xgb, _, _ = _import_ml_libs()
        dmatrix = xgb.DMatrix(feature_vector, feature_names=self.feature_names)
        
        # Get raw probability
        home_win_prob_raw = float(self.model.predict(dmatrix)[0])
        
        # Apply calibration if available (makes probabilities more reliable)
        if self.calibrator is not None:
            home_win_prob = float(self.calibrator.predict([home_win_prob_raw])[0])
        else:
            home_win_prob = home_win_prob_raw
        
        # Calculate confidence (distance from 0.5)
        confidence = abs(home_win_prob - 0.5) * 2
        
        # Predict scores
        home_adj_oe = features.get('home_adj_oe', 100)
        home_adj_de = features.get('home_adj_de', 100)
        away_adj_oe = features.get('away_adj_oe', 100)
        away_adj_de = features.get('away_adj_de', 100)
        tempo = (features.get('home_adj_tempo', 68) + features.get('away_adj_tempo', 68)) / 2
        
        home_score, away_score = extractor.predict_score(
            home_adj_oe, home_adj_de,
            away_adj_oe, away_adj_de,
            tempo
        )
        
        return {
            'home_win_probability': round(home_win_prob, 4),
            'predicted_home_score': home_score,
            'predicted_away_score': away_score,
            'predicted_margin': round(home_score - away_score, 1),
            'confidence_score': round(confidence, 4),
            'model_version': self.model_version,
            'features': features,
            'features_hash': self._hash_features(features),
        }
    
    def predict_matchup(
        self, 
        home_team, 
        away_team, 
        season: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make prediction for a hypothetical matchup.
        
        Args:
            home_team: Home team model instance
            away_team: Away team model instance
            season: Season year (defaults to current)
            
        Returns:
            Dictionary with prediction results
        """
        if self.model is None:
            self.load_model()
        
        from datetime import date
        
        if season is None:
            season = date.today().year
        
        # Create a mock game object for feature extraction
        class MockGame:
            def __init__(self, home, away, s):
                self.home_team = home
                self.away_team = away
                self.season = s
                self.date = date.today()
                self.venue = getattr(home, 'venue', None)
                self.pk = None  # Mock game has no DB primary key
                self.id = None
        
        mock_game = MockGame(home_team, away_team, season)
        
        return self.predict_game(mock_game)
    
    def predict_batch(self, games: List) -> List[Dict[str, Any]]:
        """
        Make predictions for multiple games.
        
        Args:
            games: List of Game model instances
            
        Returns:
            List of prediction dictionaries
        """
        if self.model is None:
            self.load_model()
        
        predictions = []
        for game in games:
            try:
                pred = self.predict_game(game)
                pred['game_id'] = game.id
                predictions.append(pred)
            except Exception as e:
                predictions.append({
                    'game_id': game.id,
                    'error': str(e),
                })
        
        return predictions
    
    def _prepare_feature_vector(self, features: Dict[str, Any]):
        """
        Prepare feature vector for model input.
        
        Args:
            features: Dictionary of feature values
            
        Returns:
            NumPy array with features in correct order
        """
        _, _, np = _import_ml_libs()
        
        if self.feature_names is None:
            # Use default feature names
            extractor = self._get_feature_extractor()
            self.feature_names = extractor.get_feature_names()
        
        # Create feature vector in correct order
        vector = []
        for name in self.feature_names:
            value = features.get(name, 0.0)
            # Handle None values
            if value is None:
                value = 0.0
            vector.append(float(value))
        
        return np.array([vector])
    
    def _hash_features(self, features: Dict[str, Any]) -> str:
        """
        Create hash of feature values for tracking.
        
        Args:
            features: Dictionary of feature values
            
        Returns:
            SHA256 hash string (first 16 chars)
        """
        # Sort keys for consistent hashing
        sorted_features = {k: features.get(k) for k in sorted(features.keys())}
        feature_str = json.dumps(sorted_features, sort_keys=True, default=str)
        return hashlib.sha256(feature_str.encode()).hexdigest()[:16]
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from the model.
        
        Returns:
            Dictionary of feature_name -> importance score
        """
        if self.model is None:
            self.load_model()
        
        importance = self.model.get_score(importance_type='gain')
        
        # Map to feature names
        result = {}
        for i, name in enumerate(self.feature_names or []):
            key = f'f{i}'
            result[name] = importance.get(key, 0.0)
        
        # Sort by importance
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))


class ModelTrainer:
    """Train XGBoost models for game prediction."""
    
    def __init__(self, model_dir: str = 'basketball/ml_models'):
        """
        Initialize the trainer.
        
        Args:
            model_dir: Directory to save trained models
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._feature_extractor = None
    
    def _get_feature_extractor(self):
        """Get feature extractor instance."""
        if self._feature_extractor is None:
            from basketball.ml_features import get_feature_extractor
            self._feature_extractor = get_feature_extractor()
        return self._feature_extractor
    
    def _compute_sample_weights(
        self, 
        game_dates: list, 
        current_season: int = 2026
    ):
        """
        Compute sample weights based on recency.
        
        More recent games get higher weight:
        - Current season (2026): 2.0x
        - Previous season (2025): 1.5x
        - 2 seasons ago (2024): 1.2x
        - 3 seasons ago (2023): 1.0x
        - 4+ seasons ago: 0.8x
        
        Plus exponential decay within each season (more recent games matter more).
        
        Args:
            game_dates: List of game dates
            current_season: Current season year
            
        Returns:
            NumPy array of sample weights
        """
        _, _, np = _import_ml_libs()
        from datetime import date
        
        weights = []
        
        # Reference date: end of current season
        reference_date = date(current_season, 4, 15)
        
        for game_date in game_dates:
            if isinstance(game_date, str):
                from datetime import datetime
                game_date = datetime.strptime(game_date, '%Y-%m-%d').date()
            
            # Determine season (games from Nov-Apr belong to the ending year)
            if game_date.month >= 11:
                game_season = game_date.year + 1
            else:
                game_season = game_date.year
            
            # Base weight by season
            seasons_ago = current_season - game_season
            
            if seasons_ago <= 0:  # Current season
                base_weight = 2.0
            elif seasons_ago == 1:  # Last season
                base_weight = 1.5
            elif seasons_ago == 2:  # 2 seasons ago
                base_weight = 1.2
            elif seasons_ago == 3:  # 3 seasons ago
                base_weight = 1.0
            else:  # 4+ seasons ago
                base_weight = 0.8
            
            # Exponential decay within the season (lambda = 0.002 per day)
            # Games 1 month ago: 0.94x, 3 months ago: 0.84x, 6 months ago: 0.70x
            days_ago = (reference_date - game_date).days
            days_ago = max(0, days_ago)
            recency_decay = 0.998 ** days_ago  # Very slow decay
            
            final_weight = base_weight * recency_decay
            weights.append(final_weight)
        
        return np.array(weights)
    
    def prepare_training_data(
        self, 
        games: List,
        feature_names: Optional[List[str]] = None,
        use_archive: bool = True
    ) -> Tuple[Any, Any, List[str], List]:
        """
        Prepare training data from games.
        
        Args:
            games: List of Game model instances (must be final games)
            feature_names: List of feature names to use
            use_archive: Use point-in-time KenPom archive (prevents leakage)
            
        Returns:
            Tuple of (X features, y labels, feature_names, game_dates)
        """
        _, _, np = _import_ml_libs()
        
        extractor = self._get_feature_extractor()
        
        if feature_names is None:
            feature_names = extractor.get_feature_names()
        
        X = []
        y = []
        game_dates = []
        
        for game in games:
            if not game.is_final:
                continue
            
            try:
                # Extract features AS OF GAME DATE (critical for preventing leakage)
                # This uses KenPomRatingArchive when available
                features = extractor.extract_game_features(
                    game, 
                    prediction_date=game.date,
                    use_archive=use_archive
                )
                
                # Create feature vector
                vector = []
                for name in feature_names:
                    value = features.get(name, 0.0)
                    if value is None:
                        value = 0.0
                    vector.append(float(value))
                
                X.append(vector)
                
                # Target: 1 if home team won, 0 otherwise
                y.append(1 if game.winner == game.home_team else 0)
                
                # Store game date for time-based split
                game_dates.append(game.date)
                
            except Exception:
                # Skip games with errors
                continue
        
        return np.array(X), np.array(y), feature_names, game_dates
    
    def train(
        self,
        X: Any,
        y: Any,
        feature_names: List[str],
        version: str,
        hyperparameters: Optional[Dict[str, Any]] = None,
        test_size: float = 0.2,
        game_dates: Optional[List] = None,
        time_based_split: bool = True,
        use_sample_weights: bool = True,
        current_season: int = 2026
    ) -> Dict[str, Any]:
        """
        Train XGBoost model.
        
        Args:
            X: Feature matrix
            y: Labels
            feature_names: List of feature names
            version: Model version string
            hyperparameters: XGBoost hyperparameters
            test_size: Fraction of data for testing
            game_dates: List of game dates (for time-based split)
            time_based_split: Use chronological split (recommended)
            
        Returns:
            Dictionary with training results
        """
        xgb, joblib, np = _import_ml_libs()
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
        from sklearn.isotonic import IsotonicRegression
        
        # Default hyperparameters
        default_params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'max_depth': 6,
            'learning_rate': 0.03,
            'n_estimators': 1000,
            'early_stopping_rounds': 50,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
        }
        
        if hyperparameters:
            default_params.update(hyperparameters)
        
        # TIME-BASED SPLIT (prevents data leakage from future games)
        sample_weights_train = None
        
        if time_based_split and game_dates is not None and len(game_dates) == len(X):
            # Sort by date
            sorted_indices = np.argsort(game_dates)
            X_sorted = X[sorted_indices]
            y_sorted = y[sorted_indices]
            dates_sorted = np.array(game_dates)[sorted_indices]
            
            # Use last test_size% of games as test set
            split_idx = int(len(X_sorted) * (1 - test_size))
            X_train, X_test = X_sorted[:split_idx], X_sorted[split_idx:]
            y_train, y_test = y_sorted[:split_idx], y_sorted[split_idx:]
            train_dates = dates_sorted[:split_idx]
            
            cutoff_date = dates_sorted[split_idx]
            print(f"  Time-based split: Train < {cutoff_date}, Test >= {cutoff_date}")
            
            # SAMPLE WEIGHTING BY RECENCY
            # More recent games get higher weight for training
            if use_sample_weights:
                sample_weights_train = self._compute_sample_weights(
                    train_dates, current_season
                )
                print(f"  Sample weights: Recent games weighted higher (range: {sample_weights_train.min():.2f} - {sample_weights_train.max():.2f})")
        else:
            # Fall back to random split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42
            )
            print("  Using random train/test split (consider --time-split for better accuracy)")
        
        # Create DMatrix with optional sample weights
        if sample_weights_train is not None:
            dtrain = xgb.DMatrix(X_train, label=y_train, weight=sample_weights_train, feature_names=feature_names)
        else:
            dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=feature_names)
        dtest = xgb.DMatrix(X_test, label=y_test, feature_names=feature_names)
        
        # Train model
        params = {k: v for k, v in default_params.items() 
                  if k not in ['n_estimators', 'early_stopping_rounds']}
        
        model = xgb.train(
            params,
            dtrain,
            num_boost_round=default_params['n_estimators'],
            evals=[(dtest, 'test')],
            early_stopping_rounds=default_params['early_stopping_rounds'],
            verbose_eval=False
        )
        
        # Evaluate (raw probabilities)
        y_pred_proba_raw = model.predict(dtest)
        
        # PROBABILITY CALIBRATION using Isotonic Regression
        # This ensures predicted probabilities match actual outcomes
        # (e.g., 70% predictions win 70% of the time)
        calibrator = IsotonicRegression(out_of_bounds='clip')
        
        # Train calibrator on training set predictions
        y_train_pred = model.predict(dtrain)
        calibrator.fit(y_train_pred, y_train)
        
        # Apply calibration to test predictions
        y_pred_proba = calibrator.predict(y_pred_proba_raw)
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        # Metrics before and after calibration
        accuracy = accuracy_score(y_test, y_pred)
        logloss_raw = log_loss(y_test, y_pred_proba_raw)
        logloss = log_loss(y_test, y_pred_proba)
        brier_raw = brier_score_loss(y_test, y_pred_proba_raw)
        brier = brier_score_loss(y_test, y_pred_proba)
        
        print(f"  Calibration: Brier {brier_raw:.4f} → {brier:.4f}, LogLoss {logloss_raw:.4f} → {logloss:.4f}")
        
        # Save model with calibrator
        model_filename = f'xgboost_{version}.pkl'
        model_path = self.model_dir / model_filename
        
        model_data = {
            'model': model,
            'calibrator': calibrator,  # Save calibrator for inference
            'feature_names': feature_names,
            'version': version,
            'hyperparameters': default_params,
            'training_date': datetime.now().isoformat(),
        }
        
        joblib.dump(model_data, model_path)
        
        # Save feature importance plot
        try:
            import matplotlib.pyplot as plt
            
            importance = model.get_score(importance_type='gain')
            
            # Map to feature names
            importance_dict = {}
            for i, name in enumerate(feature_names):
                key = f'f{i}'
                importance_dict[name] = importance.get(key, 0.0)
            
            # Sort and take top 20
            sorted_importance = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:20]
            
            fig, ax = plt.subplots(figsize=(10, 8))
            names = [x[0] for x in sorted_importance]
            values = [x[1] for x in sorted_importance]
            
            ax.barh(names, values)
            ax.set_xlabel('Importance (Gain)')
            ax.set_title(f'Feature Importance - {version}')
            ax.invert_yaxis()
            
            plot_path = self.model_dir / f'feature_importance_{version}.png'
            plt.savefig(plot_path, bbox_inches='tight', dpi=150)
            plt.close()
            
        except Exception:
            plot_path = None
        
        return {
            'version': version,
            'model_path': str(model_path),
            'accuracy': accuracy,
            'log_loss': logloss,
            'brier_score': brier,
            'training_games': len(X_train),
            'test_games': len(X_test),
            'feature_names': feature_names,
            'hyperparameters': default_params,
            'feature_importance_plot': str(plot_path) if plot_path else None,
            'calibrated': True,
        }
    
    def time_series_cv(
        self,
        X: Any,
        y: Any,
        game_dates: list,
        feature_names: List[str],
        n_splits: int = 5,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform time-series cross-validation.
        
        Unlike regular k-fold, this respects temporal order:
        - Fold 1: Train on 20%, test on next 20%
        - Fold 2: Train on 40%, test on next 20%
        - etc.
        
        Args:
            X: Feature matrix
            y: Labels
            game_dates: Game dates for temporal ordering
            feature_names: Feature names
            n_splits: Number of CV folds
            hyperparameters: XGBoost hyperparameters
            
        Returns:
            Dictionary with CV results (mean/std accuracy, log_loss, brier)
        """
        xgb, _, np = _import_ml_libs()
        from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
        
        # Sort by date
        sorted_indices = np.argsort(game_dates)
        X_sorted = X[sorted_indices]
        y_sorted = y[sorted_indices]
        
        # Default hyperparameters
        default_params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'max_depth': 6,
            'learning_rate': 0.03,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
        }
        if hyperparameters:
            default_params.update(hyperparameters)
        
        # Calculate fold sizes
        n_samples = len(X_sorted)
        fold_size = n_samples // (n_splits + 1)
        
        accuracies = []
        log_losses = []
        brier_scores = []
        
        for fold in range(n_splits):
            # Training: all data up to this fold
            train_end = (fold + 1) * fold_size
            test_start = train_end
            test_end = test_start + fold_size
            
            if test_end > n_samples:
                test_end = n_samples
            
            X_train_fold = X_sorted[:train_end]
            y_train_fold = y_sorted[:train_end]
            X_test_fold = X_sorted[test_start:test_end]
            y_test_fold = y_sorted[test_start:test_end]
            
            if len(X_test_fold) == 0:
                continue
            
            # Train
            dtrain = xgb.DMatrix(X_train_fold, label=y_train_fold, feature_names=feature_names)
            dtest = xgb.DMatrix(X_test_fold, label=y_test_fold, feature_names=feature_names)
            
            model = xgb.train(
                default_params,
                dtrain,
                num_boost_round=500,
                evals=[(dtest, 'test')],
                early_stopping_rounds=30,
                verbose_eval=False
            )
            
            # Evaluate
            y_pred_proba = model.predict(dtest)
            y_pred = (y_pred_proba > 0.5).astype(int)
            
            accuracies.append(accuracy_score(y_test_fold, y_pred))
            log_losses.append(log_loss(y_test_fold, y_pred_proba))
            brier_scores.append(brier_score_loss(y_test_fold, y_pred_proba))
        
        return {
            'n_splits': len(accuracies),
            'accuracy_mean': np.mean(accuracies),
            'accuracy_std': np.std(accuracies),
            'log_loss_mean': np.mean(log_losses),
            'log_loss_std': np.std(log_losses),
            'brier_mean': np.mean(brier_scores),
            'brier_std': np.std(brier_scores),
            'fold_accuracies': accuracies,
        }
    
    def create_model_version_record(self, training_results: Dict[str, Any]) -> 'MLModelVersion':
        """
        Create MLModelVersion record in database.
        
        Args:
            training_results: Results from train() method
            
        Returns:
            MLModelVersion instance
        """
        from basketball.models import MLModelVersion
        
        model_version = MLModelVersion.objects.create(
            version=training_results['version'],
            model_file_path=training_results['model_path'],
            training_date=datetime.now(),
            training_games_count=training_results['training_games'],
            test_accuracy=training_results['accuracy'],
            test_log_loss=training_results['log_loss'],
            feature_list=training_results['feature_names'],
            hyperparameters=training_results['hyperparameters'],
            is_active=False,
        )
        
        return model_version


# Singleton predictor instance
_predictor = None


def get_predictor() -> MLPredictor:
    """Get singleton MLPredictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = MLPredictor()
    return _predictor
