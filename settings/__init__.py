from functools import lru_cache

from settings.app import AppSettings
from settings.db import DatabaseSettings
from settings.logging import LoggingSettings


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()


@lru_cache
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()


__all__ = [
    "AppSettings",
    "DatabaseSettings",
    "LoggingSettings",
    "get_app_settings",
    "get_db_settings",
    "get_logging_settings",
]
