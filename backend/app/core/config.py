from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    session_secret: str
    session_max_age_seconds: int = 86400
    database_url: str = "sqlite:///./pyweb.db"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    seed_admin_username: str
    seed_admin_password: str
    seed_viewer_username: str
    seed_viewer_password: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
