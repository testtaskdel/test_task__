from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "payment-service"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://payments:payments@postgres:5432/payments"
    rabbitmq_url: str = "amqp://payments:payments@rabbitmq:5672/"
    api_key: str = "dev-api-key"

    outbox_poll_interval: float = 1.0
    outbox_batch_size: int = 50
    webhook_timeout: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
