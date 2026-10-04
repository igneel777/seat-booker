from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from core.incoming_ports import HealthPort
from routes.dependencies import get_health_facade

router = APIRouter(tags=["probes"])


@router.get("/health")
async def health(
    facade: Annotated[HealthPort, Depends(get_health_facade)],
) -> JSONResponse:
    """Readiness-style check: the app is up and its DB answers a ping."""
    if not await facade.is_db_alive():
        return JSONResponse(
            {"status": "unavailable", "db": "down"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return JSONResponse({"status": "ok", "db": "ok"})


@router.get("/liveness")
async def liveness() -> dict[str, str]:
    """Liveness check: the process is alive and the event loop is responsive."""
    return {"status": "alive"}
