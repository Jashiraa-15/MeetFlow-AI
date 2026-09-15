import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str = "MeetFlow AI"
    DATABASE_URL: str = Field(default="sqlite:///./meeting_clarifier.db")
    JWT_SECRET: str = Field(default="super-secret-jwt-key-for-meeting-action-clarifier-2026")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = "gpt-4o-mini"
    WHISPER_USE_LOCAL: bool = False
    
    # SMTP Settings for Background Notification Jobs
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@meetingclarifier.local"
    SMTP_USE_TLS: bool = True

    @property
    def effective_smtp_user(self) -> Optional[str]:
        return self.SMTP_USERNAME or self.SMTP_USER

    @property
    def effective_smtp_from(self) -> str:
        return self.SMTP_FROM or self.SMTP_FROM_EMAIL

    # Rate Limiting & Caching
    MAX_MEETING_SUBMISSIONS_PER_HOUR: int = 10
    CACHE_EXPIRY_SECONDS: int = 3600  # 1 hour

    # n8n Workflow Webhook Integration
    N8N_WEBHOOK_SECRET: str = Field(default="n8n-webhook-secret-meeting-clarifier-2026")
    N8N_CLARIFICATION_WEBHOOK_URL: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

