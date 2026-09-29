"""
API Routers Package
"""

from apps.api.routers.health import router as health_router
from apps.api.routers.machines import router as machines_router
from apps.api.routers.telemetry import router as telemetry_router
from apps.api.routers.audit import router as audit_router
from apps.api.routers.simulator import router as simulator_router
from apps.api.routers.digital_twin import router as factory_router
from apps.api.routers.anomalies import router as anomalies_router
from apps.api.routers.predictions import router as predictions_router

__all__ = [
    "health_router",
    "machines_router",
    "telemetry_router",
    "audit_router",
    "simulator_router",
    "factory_router",
    "anomalies_router",
    "predictions_router",
]
