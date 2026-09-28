"""
NEXUS Health & Observability Endpoints
Provides system liveness, readiness, and subsystem connectivity status.
"""

from datetime import datetime, timezone
import time
from fastapi import APIRouter, status
from apps.api.config import get_settings
from database.session import check_db_connection

router = APIRouter(tags=["Health & Diagnostics"])
settings = get_settings()

START_TIME = time.time()


@router.get("/health", status_code=status.HTTP_200_OK)
def get_health():
    """
    Returns system liveness, environment, uptime, and underlying database status.
    """
    db_status = check_db_connection()
    uptime_seconds = round(time.time() - START_TIME, 2)

    return {
        "status": "healthy" if db_status.get("connected", False) else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": uptime_seconds,
        "subsystems": {
            "database": db_status,
            "api_gateway": {"status": "healthy", "port": settings.API_PORT}
        }
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
def get_readiness():
    """
    Kubernetes/container readiness probe checking critical dependencies.
    """
    db_status = check_db_connection()
    is_ready = db_status.get("connected", False)
    return {
        "ready": is_ready,
        "database_connected": is_ready,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/metrics", status_code=status.HTTP_200_OK)
def get_metrics():
    """
    Exposes high-level telemetry and pipeline health metrics.
    """
    uptime_seconds = round(time.time() - START_TIME, 2)
    return {
        "uptime_seconds": uptime_seconds,
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
