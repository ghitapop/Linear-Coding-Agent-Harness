"""API routes for the Autonomous Orchestrator Framework."""

from api.routes.health import router as health_router
from api.routes.projects import router as projects_router

__all__ = ["health_router", "projects_router"]
