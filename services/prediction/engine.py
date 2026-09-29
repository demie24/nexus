"""
Predictive Intelligence Engine
Core orchestrator for multi-horizon risk forecasting, RUL estimation with uncertainty intervals,
health trajectory projection, cold-start handling, and persistence.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import joblib
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models.models import PredictionModel, MachineModel, MachineStateModel, TelemetryModel
from services.schemas import (
    TelemetryCreate,
    PredictionCreate,
    Prediction as PredictionSchema,
    PredictionStatus,
    RiskHorizonForecast,
    RiskForecastResponse,
    HealthTrajectoryPoint,
    RULResponse,
    ContributingFactor,
    PredictionAnalysisResponse,
    SeverityLevel,
    OperatingStatus,
    DataProvenance,
)
from services.prediction.config import (
    DEFAULT_HORIZONS_MINUTES,
    PRIMARY_HORIZON_MINUTES,
    CRITICAL_HEALTH_THRESHOLD,
    MAX_RUL_HOURS,
    CONFIDENCE_LEVEL,
    COLD_START_MIN_SAMPLES,
    MODEL_VERSION,
    FEATURE_VERSION,
    PREDICTIVE_MODEL_PATH,
    classify_risk,
)
from services.prediction.features import PredictiveFeatureExtractor
from services.prediction.training import PredictiveSuite, train_predictive_suite

logger = logging.getLogger("nexus.prediction")


class PredictiveIntelligenceEngine:
    def __init__(
        self,
        model_path: Path = PREDICTIVE_MODEL_PATH,
        auto_train: bool = True
    ):
        self.model_path = model_path
        self.feature_extractor = PredictiveFeatureExtractor(window_size=20)
        self.suite: Optional[PredictiveSuite] = None
        self._latest_predictions: Dict[str, PredictionSchema] = {}

        self._load_or_train_models(auto_train=auto_train)

    def _load_or_train_models(self, auto_train: bool = True) -> None:
        """Loads serialized models or triggers offline training if absent."""
        if self.model_path.exists():
            try:
                data = joblib.load(self.model_path)
                if isinstance(data, dict):
                    self.suite = PredictiveSuite(
                        failure_classifier=data["failure_classifier"],
                        rul_regressor=data["rul_regressor"],
                        health_forecaster=data["health_forecaster"],
                        model_version=data.get("model_version", MODEL_VERSION),
                        feature_version=data.get("feature_version", FEATURE_VERSION),
                        metrics=data.get("metrics", {}),
                    )
                else:
                    self.suite = data
                logger.info(f"Loaded predictive models from {self.model_path} (version: {self.suite.model_version})")
                return
            except Exception as e:
                logger.warning(f"Failed to load {self.model_path}: {e}. Retraining...")

        if auto_train:
            logger.info("Training predictive suite...")
            self.suite, _ = train_predictive_suite(save_path=self.model_path)
            logger.info(f"Predictive suite trained and saved to {self.model_path}")
        else:
            raise RuntimeError(f"Model file {self.model_path} not found and auto_train is disabled.")

    def push_telemetry(self, telemetry: TelemetryCreate, health_score: float = 100.0) -> None:
        """Buffers telemetry and health score into the feature extractor."""
        self.feature_extractor.push(telemetry, health_score)

    def predict(
        self,
        machine_id: str,
        current_telemetry: Optional[TelemetryCreate] = None,
        current_health: Optional[float] = None,
        horizon_minutes: int = PRIMARY_HORIZON_MINUTES
    ) -> PredictionAnalysisResponse:
        """
        Executes full predictive inference for a machine.
        Handles cold start safely by returning INSUFFICIENT_DATA status when history < 15 samples.
        """
        now = datetime.now(timezone.utc)
        curr_health = 100.0 if current_health is None else float(current_health)

        # 1. Cold Start Check
        if not self.feature_extractor.has_sufficient_history(machine_id) and current_telemetry is None:
            return self._build_cold_start_response(machine_id, now, curr_health, horizon_minutes)

        feat_dict, x_vector = self.feature_extractor.extract_features(
            machine_id=machine_id,
            current_telemetry=current_telemetry,
            current_health=current_health
        )

        if x_vector is None or feat_dict is None:
            return self._build_cold_start_response(machine_id, now, curr_health, horizon_minutes)

        # 2. ML Multi-Horizon Inference
        X_batch = np.array([x_vector])

        # A. Failure Probabilities
        prob_dict = self.suite.failure_classifier.predict_proba(X_batch)
        risk_horizons: List[RiskHorizonForecast] = []
        risk_forecast_map: Dict[str, float] = {}

        for h in DEFAULT_HORIZONS_MINUTES:
            prob = float(prob_dict[h][0])
            risk_level = classify_risk(prob)
            conf = 0.92 if prob < 0.2 or prob > 0.8 else 0.85
            risk_horizons.append(
                RiskHorizonForecast(
                    horizon_minutes=h,
                    horizon_hours=round(h / 60.0, 2),
                    failure_probability=round(prob, 4),
                    risk_level=risk_level,
                    confidence=conf,
                )
            )
            risk_forecast_map[str(h)] = round(prob, 4)

        # Primary horizon values
        primary_prob = risk_forecast_map.get(str(horizon_minutes), risk_forecast_map.get("120", 0.0))
        primary_risk = classify_risk(primary_prob)

        # B. Health Trajectory Forecast
        health_pred_dict = self.suite.health_forecaster.predict(X_batch)
        health_points: List[HealthTrajectoryPoint] = []
        health_trajectory_map: Dict[str, float] = {}

        for h in DEFAULT_HORIZONS_MINUTES:
            pred_h = float(health_pred_dict[h][0])
            h_status = "CRITICAL" if pred_h < 25.0 else ("DEGRADED" if pred_h < 70.0 else "OPERATING")
            health_points.append(
                HealthTrajectoryPoint(
                    horizon_minutes=h,
                    horizon_hours=round(h / 60.0, 2),
                    predicted_health_score=round(pred_h, 2),
                    health_status=h_status,
                    provenance=DataProvenance.PREDICTED,
                )
            )
            health_trajectory_map[str(h)] = round(pred_h, 2)

        primary_health = health_trajectory_map.get(str(horizon_minutes), health_trajectory_map.get("120", curr_health))

        # C. RUL Estimation with Uncertainty Bounds
        rul_pt, rul_low, rul_high = self.suite.rul_regressor.predict(X_batch)
        rul_val = float(rul_pt[0])
        rul_l = float(rul_low[0])
        rul_h = float(rul_high[0])

        status = PredictionStatus.ESTIMATED
        if curr_health <= CRITICAL_HEALTH_THRESHOLD:
            status = PredictionStatus.MAINTENANCE_REQUIRED
        elif primary_prob < 0.10 and curr_health > 85.0:
            status = PredictionStatus.HEALTHY

        # D. Contributing Factors
        raw_factors = self.suite.failure_classifier.explain_factors(x_vector, top_n=5)
        factors = [
            ContributingFactor(
                factor_name=f["factor_name"],
                metric_name=f["metric_name"],
                importance=f["importance"],
                impact_direction=f["impact_direction"],
                description=f["description"]
            )
            for f in raw_factors
        ]

        # Assemble Schema
        prediction_schema = PredictionSchema(
            machine_id=machine_id,
            timestamp=now,
            horizon_minutes=horizon_minutes,
            predicted_failure_probability=round(primary_prob, 4),
            predicted_health_score=round(primary_health, 2),
            remaining_useful_life_hours=round(rul_val, 2),
            rul_lower_hours=round(rul_l, 2),
            rul_upper_hours=round(rul_h, 2),
            risk_level=primary_risk,
            confidence=0.90,
            prediction_status=status,
            model_version=self.suite.model_version,
            feature_version=self.suite.feature_version,
            health_trajectory=health_trajectory_map,
            risk_forecast=risk_forecast_map,
            contributing_factors=[f.model_dump() for f in factors],
            provenance=DataProvenance.PREDICTED,
            created_at=now,
        )

        risk_response = RiskForecastResponse(
            machine_id=machine_id,
            timestamp=now,
            current_status=OperatingStatus.OPERATING if curr_health > 70.0 else OperatingStatus.DEGRADED,
            current_health_score=round(curr_health, 2),
            horizons=risk_horizons,
            provenance=DataProvenance.PREDICTED,
        )

        rul_response = RULResponse(
            machine_id=machine_id,
            timestamp=now,
            remaining_useful_life_hours=round(rul_val, 2),
            rul_lower_hours=round(rul_l, 2),
            rul_upper_hours=round(rul_h, 2),
            confidence_level=CONFIDENCE_LEVEL,
            prediction_status=status,
            model_version=self.suite.model_version,
            provenance=DataProvenance.PREDICTED,
        )

        self._latest_predictions[machine_id] = prediction_schema

        return PredictionAnalysisResponse(
            machine_id=machine_id,
            timestamp=now,
            prediction=prediction_schema,
            risk_forecast=risk_response,
            health_trajectory=health_points,
            rul=rul_response,
            contributing_factors=factors,
            baseline_comparison=self.suite.metrics or {},
        )

    def _build_cold_start_response(
        self,
        machine_id: str,
        timestamp: datetime,
        current_health: float,
        horizon_minutes: int
    ) -> PredictionAnalysisResponse:
        """Generates graceful fallback prediction during cold start (< 15 samples)."""
        sample_count = self.feature_extractor.get_sample_count(machine_id)
        desc_text = f"Insufficient historical telemetry frames ({sample_count}/{COLD_START_MIN_SAMPLES} samples required)"

        factors = [
            ContributingFactor(
                factor_name="cold_start",
                metric_name="history",
                importance=1.0,
                impact_direction="stable",
                description=desc_text
            )
        ]

        horizons = [
            RiskHorizonForecast(
                horizon_minutes=h,
                horizon_hours=round(h / 60.0, 2),
                failure_probability=0.0,
                risk_level=SeverityLevel.LOW,
                confidence=0.50,
            )
            for h in DEFAULT_HORIZONS_MINUTES
        ]

        health_points = [
            HealthTrajectoryPoint(
                horizon_minutes=h,
                horizon_hours=round(h / 60.0, 2),
                predicted_health_score=round(current_health, 2),
                health_status="OPERATING",
                provenance=DataProvenance.PREDICTED,
            )
            for h in DEFAULT_HORIZONS_MINUTES
        ]

        pred_schema = PredictionSchema(
            machine_id=machine_id,
            timestamp=timestamp,
            horizon_minutes=horizon_minutes,
            predicted_failure_probability=0.0,
            predicted_health_score=round(current_health, 2),
            remaining_useful_life_hours=MAX_RUL_HOURS,
            rul_lower_hours=None,
            rul_upper_hours=None,
            risk_level=SeverityLevel.LOW,
            confidence=0.50,
            prediction_status=PredictionStatus.INSUFFICIENT_DATA,
            model_version=MODEL_VERSION,
            feature_version=FEATURE_VERSION,
            health_trajectory={str(h): round(current_health, 2) for h in DEFAULT_HORIZONS_MINUTES},
            risk_forecast={str(h): 0.0 for h in DEFAULT_HORIZONS_MINUTES},
            contributing_factors=[f.model_dump() for f in factors],
            provenance=DataProvenance.PREDICTED,
            created_at=timestamp,
        )

        risk_resp = RiskForecastResponse(
            machine_id=machine_id,
            timestamp=timestamp,
            current_status=OperatingStatus.OPERATING,
            current_health_score=round(current_health, 2),
            horizons=horizons,
            provenance=DataProvenance.PREDICTED,
        )

        rul_resp = RULResponse(
            machine_id=machine_id,
            timestamp=timestamp,
            remaining_useful_life_hours=MAX_RUL_HOURS,
            rul_lower_hours=None,
            rul_upper_hours=None,
            confidence_level=0.50,
            prediction_status=PredictionStatus.INSUFFICIENT_DATA,
            model_version=MODEL_VERSION,
            provenance=DataProvenance.PREDICTED,
        )

        return PredictionAnalysisResponse(
            machine_id=machine_id,
            timestamp=timestamp,
            prediction=pred_schema,
            risk_forecast=risk_resp,
            health_trajectory=health_points,
            rul=rul_resp,
            contributing_factors=factors,
            baseline_comparison=self.suite.metrics or {},
        )

    def persist_prediction(self, response: PredictionAnalysisResponse, db: Session) -> PredictionModel:
        """Persists a prediction record into the PostgreSQL database."""
        pred = response.prediction
        db_model = PredictionModel(
            machine_id=pred.machine_id,
            timestamp=pred.timestamp,
            horizon_minutes=pred.horizon_minutes,
            predicted_failure_probability=pred.predicted_failure_probability,
            predicted_health_score=pred.predicted_health_score,
            remaining_useful_life_hours=pred.remaining_useful_life_hours,
            rul_lower_hours=pred.rul_lower_hours,
            rul_upper_hours=pred.rul_upper_hours,
            risk_level=pred.risk_level.value,
            confidence=pred.confidence,
            prediction_status=pred.prediction_status.value,
            model_version=pred.model_version,
            feature_version=pred.feature_version,
            health_trajectory=pred.health_trajectory,
            risk_forecast=pred.risk_forecast,
            contributing_factors=pred.contributing_factors,
            provenance=pred.provenance.value,
            created_at=pred.created_at or datetime.now(timezone.utc),
        )
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        pred.id = db_model.id
        return db_model

    def get_latest_prediction(self, machine_id: str, db: Optional[Session] = None) -> Optional[PredictionSchema]:
        """Retrieves latest cached or persisted prediction for a machine."""
        if machine_id in self._latest_predictions:
            return self._latest_predictions[machine_id]

        if db is not None:
            record = (
                db.query(PredictionModel)
                .filter(PredictionModel.machine_id == machine_id)
                .order_by(desc(PredictionModel.created_at))
                .first()
            )
            if record:
                return PredictionSchema.model_validate(record)
        return None


_engine_instance: Optional[PredictiveIntelligenceEngine] = None


def get_prediction_engine() -> PredictiveIntelligenceEngine:
    """Returns singleton instance of PredictiveIntelligenceEngine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PredictiveIntelligenceEngine(auto_train=True)
    return _engine_instance
