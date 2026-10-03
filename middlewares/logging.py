import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from utils.logging import get_logger

logger = get_logger("seat_booker.access")


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    client = request.client.host if request.client else "-"
    logger.info("--> %s %s from %s", request.method, request.url.path, client)
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "<-- %s %s 500 %.2fms", request.method, request.url.path, elapsed_ms
        )
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    logger.info(
        "<-- %s %s %d %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


def add_logging_middleware(app: FastAPI) -> None:
    app.middleware("http")(log_requests)
