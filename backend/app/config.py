from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = ""
    ai_timeout_seconds: int = 180
    github_client_id: str = ""
    github_client_secret: str = ""
    github_callback_url: str = "http://localhost:8000/api/github/callback"
    frontend_origin: str = "http://localhost:5173"
    session_secret: str = "development-only-change-me"
    max_upload_mb: int = 12
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()
