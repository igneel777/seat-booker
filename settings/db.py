from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    user: str = "seatbooker"
    # Default mirrors docker-compose so local/PoC startup works with no .env.
    # Deliberate for this PoC only — never ship a default password in production.
    password: SecretStr = SecretStr("seatbooker")
    name: str = "seatbooker"
    pool_size: int = 10
    max_overflow: int = 5
    pool_timeout_seconds: float = 10.0
    echo: bool = False

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.name}"
        )
