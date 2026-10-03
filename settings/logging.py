from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOG_", env_file=".env", extra="ignore"
    )

    level: LogLevel = "INFO"
    format: str = "%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s: %(message)s"
    correlation_id_header: str = "X-Request-ID"
