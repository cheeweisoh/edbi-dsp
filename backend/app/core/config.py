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

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")


settings = Settings()
