from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    name: str = "Seat Booker API"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
