from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    session_secret: str
    session_max_age_seconds: int = 86400
    database_url: str = "sqlite:///./pyweb.db"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Filesystem root for job-attachment uploads. The job ID is appended
    # to scope each job's files into its own subdirectory. Container
    # builds override this via the UPLOADS_DIR env var so the data lands
    # on the same bind-mounted volume as the SQLite file.
    uploads_dir: str = "./data/uploads"

    # OnlyOffice Document Server endpoints. Empty string disables the
    # Office-preview pipeline (the upload handler then leaves
    # preview_available=False instead of crashing). Compose populates
    # these so the backend never has to know about the public host.
    onlyoffice_internal_url: str = ""
    backend_internal_url: str = ""
    onlyoffice_jwt_secret: str = ""
    onlyoffice_convert_timeout_seconds: float = 240.0

    # Discord OAuth (optional — password login coexists during the
    # migration). Empty values keep the Discord login endpoints inert
    # (they return 400 "not configured") so the app still boots and
    # password login is unaffected. Set all three to enable Discord login.
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = ""

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

    @property
    def discord_oauth_configured(self) -> bool:
        return bool(
            self.discord_client_id
            and self.discord_client_secret
            and self.discord_redirect_uri
        )


settings = Settings()
