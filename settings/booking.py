from datetime import timedelta

from pydantic_settings import BaseSettings, SettingsConfigDict


class BookingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOOKING_", env_file=".env", extra="ignore"
    )

    per_hold_limit: int = 4
    # Env accepts ISO-8601 ("PT10M") or "HH:MM:SS" ("00:10:00").
    hold_ttl: timedelta = timedelta(minutes=10)
