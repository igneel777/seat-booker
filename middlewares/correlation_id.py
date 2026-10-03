from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send

from settings import get_logging_settings


class DiscardIncomingCorrelationIdMiddleware:
    def __init__(self, app: ASGIApp, header_name: str) -> None:
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = MutableHeaders(scope=scope)
            if self.header_name in headers:
                del headers[self.header_name]
        await self.app(scope, receive, send)


def add_correlation_id_middleware(app: FastAPI) -> None:
    header_name = get_logging_settings().correlation_id_header
    app.add_middleware(CorrelationIdMiddleware, header_name=header_name)
    # We discard all incoming request ids and always assign our own.
    app.add_middleware(DiscardIncomingCorrelationIdMiddleware, header_name=header_name)
