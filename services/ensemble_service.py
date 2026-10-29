"""
services/ensemble_service.py
============================
Ensemble learning pipeline: Ebbinghaus Log-Linear + XGBoost Regressor.
"""

import numpy as np
import math
from typing import Dict, List, Tuple
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from services.forgetting_curve_service import BASELINE_LAMBDA
from services.learning_service import learn_lambda_from_attempts

class MemoryEnsembleModel:
    def __init__(self):
        self.xgb_model = XGBRegressor(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42
        )
        self.is_fitted = False
        self.blend_weights = (0.5, 0.5)

    def extract_features(self, attempts: List[Dict]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Builds feature matrix X, ground truth y (next score),
        and Ebbinghaus prior predictions from sequential attempts.
        """
        sorted_attempts = sorted(attempts, key=lambda a: float(a["simulated_time_days"]))
        X, y, priors = [], [], []

        for i in range(len(sorted_attempts) - 1):
            prev = sorted_attempts[i]
            nxt = sorted_attempts[i + 1]

            t_prev = float(prev["simulated_time_days"])
            t_next = float(nxt["simulated_time_days"])
            r_prev = float(prev["score_pct"])
            r_next = float(nxt["score_pct"])
            delta_t = max(0.01, t_next - t_prev)

            # Cumulative stats up to attempt i
            past_scores = [float(a["score_pct"]) for a in sorted_attempts[:i+1]]
            avg_past = np.mean(past_scores)

            # Ebbinghaus theoretical baseline
            ebbinghaus_prior = max(0.2, min(1.0, r_prev * math.exp(-BASELINE_LAMBDA * delta_t)))

            feature_vector = [
                delta_t,
                r_prev,
                i + 1,              # attempt count
                avg_past,           # cumulative mean
                ebbinghaus_prior    # domain prior
            ]

            X.append(feature_vector)
            y.append(r_next)
            priors.append(ebbinghaus_prior)

        return np.array(X), np.array(y), np.array(priors)

    def train_and_evaluate(self, attempts: List[Dict]) -> Dict:
        """
        Trains XGBoost on attempt history and computes comparative metrics.
        """
        if len(attempts) < 2:
            return {
                "status": "insufficient_data",
                "message": "At least 2 attempts required to evaluate predictions."
            }

        X, y, priors = self.extract_features(attempts)

        if len(X) == 0:
            return {
                "status": "insufficient_data",
                "message": "At least 2 valid consecutive attempts required."
            }

        # Train/Test Split if enough samples exist; otherwise evaluate in-sample fit
        if len(X) >= 4:
            split_idx = max(2, len(X) - max(2, int(len(X) * 0.3)))
            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]
            priors_test = priors[split_idx:]

            self.xgb_model.fit(X_train, y_train)
            eval_X, eval_y, eval_priors = X_test, y_test, priors_test
        else:
            # When sample count is small (1-3 transitions), fit on available data and evaluate
            self.xgb_model.fit(X, y)
            eval_X, eval_y, eval_priors = X, y, priors

        self.is_fitted = True

        # Predictions
        y_pred_xgb = self.xgb_model.predict(eval_X)
        y_pred_prior = eval_priors

        # Ensemble Prediction (Blend)
        w_prior, w_xgb = self.blend_weights
        y_pred_ensemble = (w_prior * y_pred_prior) + (w_xgb * y_pred_xgb)

        def _safe_r2(y_true, y_pred) -> float:
            if len(y_true) < 2 or float(np.var(y_true)) == 0.0:
                diff = float(abs(y_true[0] - y_pred[0]))
                return round(max(0.0, 1.0 - diff), 4)
            try:
                val = float(r2_score(y_true, y_pred))
                return 0.0 if (np.isnan(val) or np.isinf(val)) else round(val, 4)
            except Exception:
                return 0.0

        # Performance Metrics Comparison
        metrics = {
            "baseline_ebbinghaus": {
                "mae": float(mean_absolute_error(eval_y, y_pred_prior)),
                "rmse": float(np.sqrt(mean_squared_error(eval_y, y_pred_prior))),
                "r2": _safe_r2(eval_y, y_pred_prior)
            },
            "standalone_xgboost": {
                "mae": float(mean_absolute_error(eval_y, y_pred_xgb)),
                "rmse": float(np.sqrt(mean_squared_error(eval_y, y_pred_xgb))),
                "r2": _safe_r2(eval_y, y_pred_xgb)
            },
            "ensemble_model": {
                "mae": float(mean_absolute_error(eval_y, y_pred_ensemble)),
                "rmse": float(np.sqrt(mean_squared_error(eval_y, y_pred_ensemble))),
                "r2": _safe_r2(eval_y, y_pred_ensemble)
            },
            "test_sample_count": len(eval_y)
        }

        return metrics
