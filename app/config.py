from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    messages_path: Path
    log_level: str
    oms_base_url: str
    oms_bot_token: str
    http_timeout_seconds: float


def load_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    oms_base_url = os.getenv("OMS_BASE_URL", "").strip()
    if not oms_base_url:
        raise ValueError("OMS_BASE_URL is required")

    oms_bot_token = os.getenv("OMS_BOT_TOKEN", "").strip()
    if not oms_bot_token:
        raise ValueError("OMS_BOT_TOKEN is required")

    raw_messages_path = os.getenv("MESSAGES_PATH", "config/messages.ru.json").strip()
    messages_path = Path(raw_messages_path or "config/messages.ru.json")

    raw_log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    log_level = raw_log_level or "INFO"

    raw_timeout = os.getenv("HTTP_TIMEOUT_SECONDS", "5").strip()
    try:
        http_timeout_seconds = float(raw_timeout)
    except ValueError as exc:
        raise ValueError("HTTP_TIMEOUT_SECONDS must be a positive number") from exc
    if http_timeout_seconds <= 0:
        raise ValueError("HTTP_TIMEOUT_SECONDS must be a positive number")

    return Settings(
        telegram_bot_token=token,
        messages_path=messages_path,
        log_level=log_level,
        oms_base_url=oms_base_url,
        oms_bot_token=oms_bot_token,
        http_timeout_seconds=http_timeout_seconds,
    )
