from __future__ import annotations

from functools import lru_cache
from typing import List

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

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: str | List[int] | None) -> List[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        return [int(item.strip()) for item in str(value).split(",") if item.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
