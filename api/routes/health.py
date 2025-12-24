"""Health check endpoints."""

import time
from typing import Optional

from fastapi import APIRouter, Depends

from api.schemas import DetailedHealthResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])

# Track start time for uptime calculation
_start_time: Optional[float] = None


def get_start_time() -> float:
    """Get or initialize the start time."""
    global _start_time
    if _start_time is None:
        _start_time = time.time()
    return _start_time


@router.get("", response_model=HealthResponse)
async def health_check(
    start_time: float = Depends(get_start_time),
) -> HealthResponse:
    """Basic health check endpoint.

    Returns:
        Basic health status.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        database="connected",  # TODO: Actually check DB connection
        uptime_seconds=time.time() - start_time,
    )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    start_time: float = Depends(get_start_time),
) -> DetailedHealthResponse:
    """Detailed health check endpoint.

    Returns:
        Detailed health status including metrics.
    """
    # TODO: Add actual database latency check
    # TODO: Add active projects count from DB
    # TODO: Add running agents count
    # TODO: Add memory usage

    return DetailedHealthResponse(
        status="healthy",
        version="1.0.0",
        database="connected",
        uptime_seconds=time.time() - start_time,
        database_latency_ms=None,
        active_projects=0,
        running_agents=0,
        memory_usage_mb=None,
    )


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check for Kubernetes.

    Returns:
        Ready status.
    """
    # TODO: Check if all required services are available
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Liveness check for Kubernetes.

    Returns:
        Alive status.
    """
    return {"status": "alive"}
