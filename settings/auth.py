from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_", env_file=".env", extra="ignore"
    )

    # Dev default so the PoC starts with no .env.
    # Deliberate for this PoC only — never ship a default secret in production.
    jwt_secret: SecretStr = SecretStr("seat-booker-jwt-secret")
    jwt_algorithm: str = "HS256"
