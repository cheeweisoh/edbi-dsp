from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATA_DIR: str
    FILE_BASE_DIR: str
    BOOTSTRAP_USER_EMAIL: str
    BOOTSTRAP_USER_PASSWORD: str
    BOOTSTRAP_USER2_EMAIL: str
    BOOTSTRAP_USER2_PASSWORD: str
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "mistral-large-3:675b-cloud"
    OLLAMA_TIMEOUT_SECONDS: int = 120
    DATABRICKS_HOST: str | None = None
    DATABRICKS_TOKEN: str | None = None
    DATABRICKS_SQL_WAREHOUSE_HTTP_PATH: str | None = None
    DATABRICKS_UC_CATALOG: str | None = None
    DATABRICKS_UC_SCHEMA: str | None = None

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")


settings = Settings()
