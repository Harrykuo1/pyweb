from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    session_secret: str
    session_max_age_seconds: int = 86400
    database_url: str = "sqlite:///./pyweb.db"

    seed_admin_username: str
    seed_admin_password: str
    seed_viewer_username: str
    seed_viewer_password: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
