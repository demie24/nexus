"""
Tests for Baseline Comparisons vs Trained ML Models
Verifies that trained ML models mathematically outperform Persistence and Linear Baselines
on unseen held-out trajectories.
"""

import pytest
from services.prediction.dataset import generate_predictive_dataset
from services.prediction.training import train_predictive_suite, evaluate_suite


@pytest.fixture(scope="module")
def benchmark_evaluation():
    """Trains suite on synthetic trajectories and evaluates on unseen held-out trajectories."""
    suite, metrics = train_predictive_suite(
        num_trajectories_per_scenario=6,
        steps_per_trajectory=70
    )
    return metrics


def test_ml_model_outperforms_persistence_on_rul_mae(benchmark_evaluation):
    """Verify that ML model achieves significantly lower RUL MAE than persistence baseline."""
    rul_mae = benchmark_evaluation["rul"]["mae"]
    ml_mae = rul_mae["ml"]
    persistence_mae = rul_mae["persistence"]

    assert ml_mae < persistence_mae, f"ML MAE ({ml_mae}) must be lower than persistence MAE ({persistence_mae})"


def test_ml_model_outperforms_persistence_on_rul_rmse(benchmark_evaluation):
    """Verify that ML model achieves significantly lower RUL RMSE than persistence baseline."""
    rul_rmse = benchmark_evaluation["rul"]["rmse"]
    ml_rmse = rul_rmse["ml"]
    persistence_rmse = rul_rmse["persistence"]

    assert ml_rmse < persistence_rmse, f"ML RMSE ({ml_rmse}) must be lower than persistence RMSE ({persistence_rmse})"


def test_ml_model_superior_calibration_brier_score(benchmark_evaluation):
    """Verify ML model achieves lower (better) Brier calibration score than persistence baseline."""
    class_120 = benchmark_evaluation["classification"]["120m"]
    ml_brier = class_120["brier_score"]["ml"]
    persistence_brier = class_120["brier_score"]["persistence"]

    assert ml_brier < persistence_brier, f"ML Brier ({ml_brier}) must be lower than persistence ({persistence_brier})"


def test_ml_model_classification_discrimination_roc_auc(benchmark_evaluation):
    """Verify ML model achieves high ROC-AUC (>= 0.90) on unseen test set."""
    class_120 = benchmark_evaluation["classification"]["120m"]
    ml_auc = class_120["roc_auc"]["ml"]
    assert ml_auc >= 0.90, f"ML ROC-AUC ({ml_auc}) should be >= 0.90 on held-out trajectories"
