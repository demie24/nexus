"""
NEXUS API Gateway & Main Application Entrypoint
AI-Orchestrated Decision Intelligence & Digital Twin Platform
"""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from apps.api.config import get_settings
from apps.api.routers import (
    health_router,
    machines_router,
    telemetry_router,
    audit_router,
    simulator_router,
    factory_router,
    anomalies_router,
    predictions_router,
    diagnostics_router,
    simulation_router,
    decisions_router,
)

from database.base import Base
from database.session import engine

# Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nexus.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    Initializes database tables on startup if not present.
    """
    logger.info("Initializing NEXUS API Gateway...")
    try:
        # Create database tables if not existing
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema verified successfully.")
    except Exception as exc:
        logger.error(f"Database initialization warning: {exc}")

    yield

    logger.info("Shutting down NEXUS API Gateway...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="NEXUS — AI-Orchestrated Decision Intelligence & Digital Twin Platform API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Validation Error Handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "path": request.url.path
        }
    )


# Mount Routers
# Root liveness/readiness
app.include_router(health_router)

# Versioned API routes under /api/v1
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(machines_router, prefix=settings.API_V1_PREFIX)
app.include_router(telemetry_router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_router, prefix=settings.API_V1_PREFIX)
app.include_router(simulator_router, prefix=settings.API_V1_PREFIX)
app.include_router(factory_router, prefix=settings.API_V1_PREFIX)
app.include_router(anomalies_router, prefix=settings.API_V1_PREFIX)
app.include_router(predictions_router, prefix=settings.API_V1_PREFIX)
app.include_router(diagnostics_router, prefix=settings.API_V1_PREFIX)
app.include_router(simulation_router, prefix=settings.API_V1_PREFIX)
app.include_router(decisions_router, prefix=settings.API_V1_PREFIX)



@app.get("/", tags=["Root"])
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "tagline": "AI-Orchestrated Decision Intelligence & Digital Twin Platform",
        "docs": "/docs",
        "health": "/health",
        "api_v1": settings.API_V1_PREFIX
    }
