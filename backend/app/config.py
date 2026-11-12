"""Application configuration loaded from the local environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with safe local-development defaults."""

    database_url: str = "postgresql+psycopg://splitbill:splitbill@localhost:5432/splitbill"
    test_database_url: str = "postgresql+psycopg://splitbill:splitbill@localhost:5432/splitbill_test"
    cors_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
