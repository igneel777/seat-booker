from fastapi import FastAPI

from middlewares import (
    add_correlation_id_middleware,
    add_cors_middleware,
    add_logging_middleware,
)
from routes.probes import router as probes_router
from settings import get_app_settings, get_logging_settings
from utils.logging import setup_logging

setup_logging(get_logging_settings())


def create_app() -> FastAPI:
    app = FastAPI(title=get_app_settings().name)
    # Middleware added last runs outermost. Order (outer -> inner):
    # correlation id -> logging -> CORS, so every log line carries the id
    # and the timing covers everything below it.
    add_cors_middleware(app)
    add_logging_middleware(app)
    add_correlation_id_middleware(app)
    app.include_router(probes_router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_app_settings()
    uvicorn.run(
        "api_server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        access_log=False,
    )
