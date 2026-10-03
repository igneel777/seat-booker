from fastapi import APIRouter

router = APIRouter(tags=["probes"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Readiness-style check: the app is up and able to serve traffic."""
    return {"status": "ok"}


@router.get("/liveness")
async def liveness() -> dict[str, str]:
    """Liveness check: the process is alive and the event loop is responsive."""
    return {"status": "alive"}
