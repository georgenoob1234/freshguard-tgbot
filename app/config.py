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
    admin_ui_webapp_url: str
    oms_bot_token: str
    http_timeout_seconds: float
    internal_api_host: str
    internal_api_port: int
    internal_notifications_push_path: str
    internal_notifications_auth_token: str


def load_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    oms_base_url = os.getenv("OMS_BASE_URL", "").strip()
    if not oms_base_url:
        raise ValueError("OMS_BASE_URL is required")

    admin_ui_webapp_url = os.getenv("ADMIN_UI_WEBAPP_URL", "").strip()

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

    internal_api_host = os.getenv("INTERNAL_API_HOST", "0.0.0.0").strip() or "0.0.0.0"

    raw_internal_api_port = os.getenv("INTERNAL_API_PORT", "8081").strip()
    try:
        internal_api_port = int(raw_internal_api_port)
    except ValueError as exc:
        raise ValueError("INTERNAL_API_PORT must be an integer between 1 and 65535") from exc
    if internal_api_port <= 0 or internal_api_port > 65535:
        raise ValueError("INTERNAL_API_PORT must be an integer between 1 and 65535")

    internal_notifications_push_path = (
        os.getenv("INTERNAL_NOTIFICATIONS_PUSH_PATH", "/internal/notifications/push").strip()
        or "/internal/notifications/push"
    )
    if not internal_notifications_push_path.startswith("/"):
        internal_notifications_push_path = f"/{internal_notifications_push_path}"

    internal_notifications_auth_token = os.getenv("INTERNAL_NOTIFICATIONS_AUTH_TOKEN", "").strip()

    return Settings(
        telegram_bot_token=token,
        messages_path=messages_path,
        log_level=log_level,
        oms_base_url=oms_base_url,
        admin_ui_webapp_url=admin_ui_webapp_url,
        oms_bot_token=oms_bot_token,
        http_timeout_seconds=http_timeout_seconds,
        internal_api_host=internal_api_host,
        internal_api_port=internal_api_port,
        internal_notifications_push_path=internal_notifications_push_path,
        internal_notifications_auth_token=internal_notifications_auth_token,
    )
