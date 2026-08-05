from __future__ import annotations

from functools import lru_cache
from typing import List, Set

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: str = Field(default="", description="Telegram Bot API token")
    admin_ids: List[int] = Field(default_factory=list, description="List of admin Telegram user IDs")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/bot.db",
        description="SQLAlchemy async database URL",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    ai_model: str = Field(default="gpt-4o-mini", description="Default g4f model for AI agents")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: str | List[int] | None) -> List[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value if str(v).strip()]
        return [int(item.strip()) for item in str(value).split(",") if item.strip()]

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            return "INFO"
        return upper

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def admin_ids_set(self) -> Set[int]:
        """O(1) membership checks for hot paths (filters, auth)."""
        return set(self.admin_ids)


@lru_cache
def get_settings() -> Settings:
    return Settings()
