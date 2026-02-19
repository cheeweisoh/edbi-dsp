from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./edbi_dsp.db"
    SECRET_KEY: str = "changeme-replace-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATA_DIR: str = "../data"
    FILE_BASE_DIR: str = ".."
    BOOTSTRAP_USER_EMAIL: str = "system@edbi-dsp.local"
    BOOTSTRAP_USER_PASSWORD: str = "changeme"
    BOOTSTRAP_USER2_EMAIL: str = "analyst@edbi-dsp.local"
    BOOTSTRAP_USER2_PASSWORD: str = "changeme2"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
