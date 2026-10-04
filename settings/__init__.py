from functools import lru_cache

from settings.app import AppSettings
from settings.auth import AuthSettings
from settings.booking import BookingSettings
from settings.db import DatabaseSettings
from settings.logging import LoggingSettings


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()


@lru_cache
def get_booking_settings() -> BookingSettings:
    return BookingSettings()


@lru_cache
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()


__all__ = [
    "AppSettings",
    "AuthSettings",
    "BookingSettings",
    "DatabaseSettings",
    "LoggingSettings",
    "get_app_settings",
    "get_auth_settings",
    "get_booking_settings",
    "get_db_settings",
    "get_logging_settings",
]
