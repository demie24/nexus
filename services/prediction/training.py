"""
Predictive Model Training & Benchmark Pipeline
Trains ML models on synthetic trajectory datasets, evaluates against Persistence and Linear Baselines,
and serializes artifacts to disk.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Tuple
import joblib
import numpy as np
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    mean_absolute_error,
    root_mean_squared_error,
)

from services.prediction.config import (
    DEFAULT_HORIZONS_MINUTES,
    PREDICTIVE_MODEL_PATH,
    ARTIFACTS_DIR,
    MODEL_VERSION,
    FEATURE_VERSION,
)
from services.prediction.dataset import generate_predictive_dataset, DatasetSplit
from services.prediction.models import (
    PersistenceBaseline,
    LinearDegradationBaseline,
    MultiHorizonFailureClassifier,
    RULRegressor,
    HealthTrajectoryForecaster,
)


@dataclass
class PredictiveSuite:
    failure_classifier: MultiHorizonFailureClassifier
    rul_regressor: RULRegressor
    health_forecaster: HealthTrajectoryForecaster
    model_version: str = MODEL_VERSION
    feature_version: str = FEATURE_VERSION
    metrics: Dict[str, Any] = None


def evaluate_suite(
    models: PredictiveSuite,
    test_split: DatasetSplit,
    horizons_minutes = DEFAULT_HORIZONS_MINUTES
) -> Dict[str, Any]:
    """
    Evaluates ML models against Persistence and Linear Baselines on the unseen test split.
    """
    X_test = test_split.X
    y_rul_test = test_split.y_rul
    y_fail_test = test_split.y_failure
    y_health_test = test_split.y_health

    # Baselines
    persistence = PersistenceBaseline(horizons_minutes)
    linear = LinearDegradationBaseline(horizons_minutes)

    p_fail_persistence = persistence.predict_failure_probabilities(X_test)
    p_fail_linear = linear.predict_failure_probabilities(X_test)
    p_fail_ml = models.failure_classifier.predict_proba(X_test)

    rul_persistence = persistence.predict_rul(X_test)
    rul_linear = linear.predict_rul(X_test)
    rul_ml, rul_low_ml, rul_high_ml = models.rul_regressor.predict(X_test)

    health_persistence = persistence.predict_health(X_test)
    health_linear = linear.predict_health(X_test)
    health_ml = models.health_forecaster.predict(X_test)

    # Classification Metrics
    classification_report: Dict[str, Any] = {}
    for h in horizons_minutes:
        y_true = y_fail_test[h]
        if len(np.unique(y_true)) > 1:
            try:
                auc_ml = float(roc_auc_score(y_true, p_fail_ml[h]))
            except Exception:
                auc_ml = 0.5
            try:
                pr_ml = float(average_precision_score(y_true, p_fail_ml[h]))
            except Exception:
                pr_ml = 0.5
            try:
                auc_linear = float(roc_auc_score(y_true, p_fail_linear[h]))
            except Exception:
                auc_linear = 0.5
            try:
                auc_persist = float(roc_auc_score(y_true, p_fail_persistence[h]))
            except Exception:
                auc_persist = 0.5
        else:
            auc_ml, pr_ml, auc_linear, auc_persist = 1.0, 1.0, 1.0, 1.0

        brier_ml = float(brier_score_loss(y_true, p_fail_ml[h]))
        brier_linear = float(brier_score_loss(y_true, p_fail_linear[h]))
        brier_persist = float(brier_score_loss(y_true, p_fail_persistence[h]))

        classification_report[f"{h}m"] = {
            "roc_auc": {"ml": round(auc_ml, 4), "linear": round(auc_linear, 4), "persistence": round(auc_persist, 4)},
            "pr_auc": {"ml": round(pr_ml, 4)},
            "brier_score": {"ml": round(brier_ml, 4), "linear": round(brier_linear, 4), "persistence": round(brier_persist, 4)},
        }

    # RUL Metrics
    rul_report = {
        "mae": {
            "ml": round(float(mean_absolute_error(y_rul_test, rul_ml)), 3),
            "linear": round(float(mean_absolute_error(y_rul_test, rul_linear)), 3),
            "persistence": round(float(mean_absolute_error(y_rul_test, rul_persistence)), 3),
        },
        "rmse": {
            "ml": round(float(root_mean_squared_error(y_rul_test, rul_ml)), 3),
            "linear": round(float(root_mean_squared_error(y_rul_test, rul_linear)), 3),
            "persistence": round(float(root_mean_squared_error(y_rul_test, rul_persistence)), 3),
        }
    }

    # Health Trajectory Metrics
    health_report: Dict[str, Any] = {}
    for h in horizons_minutes:
        y_true_h = y_health_test[h]
        health_report[f"{h}m"] = {
            "mae": {
                "ml": round(float(mean_absolute_error(y_true_h, health_ml[h])), 3),
                "linear": round(float(mean_absolute_error(y_true_h, health_linear[h])), 3),
                "persistence": round(float(mean_absolute_error(y_true_h, health_persistence[h])), 3),
            },
            "rmse": {
                "ml": round(float(root_mean_squared_error(y_true_h, health_ml[h])), 3),
                "linear": round(float(root_mean_squared_error(y_true_h, health_linear[h])), 3),
                "persistence": round(float(root_mean_squared_error(y_true_h, health_persistence[h])), 3),
            }
        }

    return {
        "classification": classification_report,
        "rul": rul_report,
        "health_trajectory": health_report,
        "test_samples": len(X_test),
        "test_trajectories": test_split.trajectories_count,
    }


def train_predictive_suite(
    save_path: Path = PREDICTIVE_MODEL_PATH,
    num_trajectories_per_scenario: int = 12,
    steps_per_trajectory: int = 90
) -> Tuple[PredictiveSuite, Dict[str, Any]]:
    """
    Orchestrates full training, validation, testing, and saving of predictive models.
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate Dataset with strict trajectory splitting
    train_split, val_split, test_split = generate_predictive_dataset(
        num_trajectories_per_scenario=num_trajectories_per_scenario,
        steps_per_trajectory=steps_per_trajectory
    )

    # 2. Train Multi-Horizon Failure Classifier
    failure_clf = MultiHorizonFailureClassifier(DEFAULT_HORIZONS_MINUTES)
    failure_clf.fit(train_split.X, train_split.y_failure)

    # 3. Train RUL Regressor
    rul_reg = RULRegressor()
    rul_reg.fit(train_split.X, train_split.y_rul)

    # 4. Train Health Trajectory Forecaster
    health_forecaster = HealthTrajectoryForecaster(DEFAULT_HORIZONS_MINUTES)
    health_forecaster.fit(train_split.X, train_split.y_health)

    # 5. Build Suite & Evaluate
    suite = PredictiveSuite(
        failure_classifier=failure_clf,
        rul_regressor=rul_reg,
        health_forecaster=health_forecaster,
        model_version=MODEL_VERSION,
        feature_version=FEATURE_VERSION,
    )

    metrics = evaluate_suite(suite, test_split)
    suite.metrics = metrics

    # 6. Save dictionary payload to disk (immune to __main__ class path issues)
    payload = {
        "failure_classifier": failure_clf,
        "rul_regressor": rul_reg,
        "health_forecaster": health_forecaster,
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "metrics": metrics,
    }
    joblib.dump(payload, save_path)

    return suite, metrics


if __name__ == "__main__":
    suite, metrics = train_predictive_suite()
    print("=== Training & Evaluation Complete ===")
    print("Test Samples:", metrics["test_samples"])
    print("RUL MAE (ML vs Linear vs Persistence):", metrics["rul"]["mae"])
    print("RUL RMSE (ML vs Linear vs Persistence):", metrics["rul"]["rmse"])
    print("Classification 120m ROC-AUC:", metrics["classification"]["120m"]["roc_auc"])
    print("Classification 120m Brier Score:", metrics["classification"]["120m"]["brier_score"])
    print("Saved to:", PREDICTIVE_MODEL_PATH)
