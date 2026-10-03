import logging

from asgi_correlation_id import CorrelationIdFilter

from settings import LoggingSettings

NO_CORRELATION_ID = "-"


def setup_logging(settings: LoggingSettings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(settings.format))
    # Stamps record.correlation_id from the middleware's ContextVar on every record.
    handler.addFilter(CorrelationIdFilter(default_value=NO_CORRELATION_ID))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.level)

    # Route uvicorn's loggers through our handler so they share the format.
    # uvicorn.access is left alone: our middleware already logs each request.
    for name in ("uvicorn", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
