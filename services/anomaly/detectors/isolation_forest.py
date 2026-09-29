"""
Detector C — Unsupervised Isolation Forest Anomaly Detection
Uses Scikit-Learn IsolationForest with model versioning, reproducible offline baseline training,
and calibrated normalized anomaly scoring.
"""

from datetime import datetime, timezone
import logging
import os
from typing import Dict, List, Optional, Any
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest

from services.anomaly.config import get_anomaly_config
from services.simulation.config import get_default_factory_spec

logger = logging.getLogger("nexus.anomaly.isolation_forest")

MODEL_DIR = "/home/demie/nexus/artifacts/models"
MODEL_PATH = os.path.join(MODEL_DIR, "isolation_forest_v1.joblib")


class IsolationForestDetector:
    def __init__(self):
        self.config = get_anomaly_config()
        self.model: Optional[IsolationForest] = None
        self.metadata: Dict[str, Any] = {}
        self._ensure_trained_model()

    def _generate_normal_training_data(self, n_samples: int = 1200) -> np.ndarray:
        """
        Generates clean baseline training distribution under nominal operating factory physics
        across all registered industrial assets in the Virtual Factory.
        Features: [temperature, vibration, pressure, current, voltage, rpm, power_kw, load, efficiency, output_rate]
        """
        rng = np.random.default_rng(self.config.isolation_forest_random_seed)
        samples = []

        factory_spec = get_default_factory_spec()
        machines = factory_spec.all_machines() if factory_spec else []
        per_machine = max(50, n_samples // len(machines))

        for m in machines:
            for _ in range(per_machine):
                temp = rng.normal(m.nominal_temp_c, max(0.5, m.temp_noise_std * 3.0))
                vib = max(0.2, rng.normal(m.nominal_vib_mms, max(0.05, m.vib_noise_std * 3.0)))
                press = max(0.5, rng.normal(m.nominal_pressure_bar, max(0.05, m.pressure_noise_std * 3.0)))
                curr = max(1.0, rng.normal(m.nominal_current_a, max(0.2, m.current_noise_std * 3.0)))
                volt = rng.normal(m.nominal_voltage_v, max(1.0, m.voltage_noise_std * 2.0))
                rpm = max(0.0, rng.normal(m.nominal_rpm, max(2.0, m.rpm_noise_std * 2.0)))
                pwr = max(1.0, rng.normal(m.nominal_power_kw, max(0.2, m.power_noise_std * 3.0)))
                load = max(0.5, rng.normal(1.0, 0.04))
                eff = min(100.0, max(88.0, rng.normal(96.0, 1.2)))
                out = max(10.0, rng.normal(m.nominal_output_rate, 3.0))

                samples.append([temp, vib, press, curr, volt, rpm, pwr, load, eff, out])

        return np.array(samples)

    def train_and_save(self) -> None:
        """Trains the Isolation Forest on clean baseline normal data and saves model + metadata."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        X_train = self._generate_normal_training_data()

        forest = IsolationForest(
            n_estimators=self.config.isolation_forest_n_estimators,
            contamination=self.config.isolation_forest_contamination,
            random_state=self.config.isolation_forest_random_seed,
            n_jobs=-1
        )
        forest.fit(X_train)
        self.model = forest

        self.metadata = {
            "model_name": "NEXUS_IsolationForest_Unsupervised",
            "model_version": self.config.model_version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "feature_version": "v1",
            "training_samples_count": len(X_train),
            "features": self.config.isolation_forest_features,
            "parameters": {
                "n_estimators": self.config.isolation_forest_n_estimators,
                "contamination": self.config.isolation_forest_contamination,
                "random_state": self.config.isolation_forest_random_seed,
            },
            "random_seed": self.config.isolation_forest_random_seed,
        }

        artifact = {"model": forest, "metadata": self.metadata}
        joblib.dump(artifact, MODEL_PATH)
        logger.info(f"Isolation Forest model v{self.config.model_version} trained and persisted at {MODEL_PATH}")

    def _ensure_trained_model(self) -> None:
        if os.path.exists(MODEL_PATH):
            try:
                artifact = joblib.load(MODEL_PATH)
                self.model = artifact["model"]
                self.metadata = artifact.get("metadata", {})
                logger.info(f"Loaded existing Isolation Forest model v{self.metadata.get('model_version')}")
                return
            except Exception as exc:
                logger.warning(f"Failed to load cached model from {MODEL_PATH}: {exc}. Retraining...")
        self.train_and_save()

    def detect(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs inference on single ML feature vector and calibrates raw decision score into [0.0, 1.0].
        Piecewise calibration:
        - Inliers (raw_score >= 0.0): score <= 0.20 (NORMAL)
        - Moderate outliers (-0.15 <= raw_score < 0.0): score 0.25 to 0.75 (LOW to HIGH)
        - Extreme outliers (raw_score < -0.15): score >= 0.75 up to 1.00 (HIGH to CRITICAL)
        """
        if self.model is None:
            self._ensure_trained_model()

        vec = np.array(features["ml_vector"], dtype=float).reshape(1, -1)
        raw_score = float(self.model.decision_function(vec)[0])
        # prediction: +1 for inlier, -1 for anomaly
        prediction = int(self.model.predict(vec)[0])

        if raw_score >= 0.12:
            calibrated_score = 0.05
        elif raw_score >= 0.0:
            calibrated_score = 0.05 + 0.15 * (1.0 - raw_score / 0.12)
        elif raw_score >= -0.10:
            calibrated_score = 0.30 + (abs(raw_score) / 0.10) * 0.45
        else:
            calibrated_score = min(1.0, 0.75 + (abs(raw_score) - 0.10) * 2.5)

        normalized_score = round(float(min(1.0, max(0.0, calibrated_score))), 3)

        return {
            "detector": "isolation_forest",
            "score": normalized_score,
            "raw_decision_score": round(raw_score, 4),
            "is_outlier": prediction == -1,
            "model_version": self.metadata.get("model_version", self.config.model_version),
            "feature_version": self.metadata.get("feature_version", "v1"),
        }
