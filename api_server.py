from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

import models.db  # noqa: F401  registers tables on SQLModel.metadata
from infra.db_client import DBClient
from middlewares import (
    add_correlation_id_middleware,
    add_cors_middleware,
    add_logging_middleware,
)
from routes.admin import router as admin_router
from routes.authenticated_users import router as users_router
from routes.dependencies import init_facades
from routes.probes import router as probes_router
from settings import get_app_settings, get_db_settings, get_logging_settings
from utils.logging import setup_logging

setup_logging(get_logging_settings())


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db_client = DBClient(get_db_settings())
    # No migrations: the DB is ephemeral in this PoC, so create tables on boot.
    async with db_client.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    init_facades(db_client)
    yield
    await db_client.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=get_app_settings().name, lifespan=lifespan)
    # Middleware added last runs outermost. Order (outer -> inner):
    # correlation id -> logging -> CORS, so every log line carries the id
    # and the timing covers everything below it.
    add_cors_middleware(app)
    add_logging_middleware(app)
    add_correlation_id_middleware(app)
    app.include_router(probes_router)
    app.include_router(admin_router)
    app.include_router(users_router)
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
