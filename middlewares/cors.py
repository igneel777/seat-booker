from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings import get_logging_settings


def add_cors_middleware(app: FastAPI) -> None:
    # Allow-all for now; tighten origins before going to production.
    # Note: browsers reject "*" origins with credentials, so credentials stay off.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        # Let browser clients read the correlation id off the response.
        expose_headers=[get_logging_settings().correlation_id_header],
    )
