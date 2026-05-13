from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_service_account_file: Path = Path("./service-account.json")
    google_sheet_id: str = ""
    google_sheet_tab: str = "HotProducts"
    custom_json_endpoint: str = ""
    custom_json_auth_header: str = ""
    request_timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
