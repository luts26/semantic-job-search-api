from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Semantic Job Search API"
    app_env: str = "development"
    app_debug: bool = False

    postgres_db: str = "semantic_jobs"
    postgres_user: str = "semantic_jobs_app"
    postgres_password: str = "change_me"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "job_vacancies"

    scraper_mode: Literal["live", "fixture"] = "fixture"

    workua_request_timeout: float = 20.0
    workua_min_delay_seconds: float = 0.6
    workua_max_delay_seconds: float = 1.5

    embedding_provider: str = "hash"
    embedding_model: str = "text-embedding-3-small"
    embedding_vector_size: int = 384
    embedding_timeout_seconds: float = 30.0
    embedding_max_attempts: int = 5

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
