from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from aiohttp import web
from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
)
from aiogram.types import InlineKeyboardMarkup

from app.keyboards import build_notification_image_keyboard
from app.messages import msg

LOGGER = logging.getLogger(__name__)

EVENT_DEVICE_OFFLINE = "device_offline"
EVENT_DEVICE_ONLINE = "device_online"
EVENT_DEFECT_DETECTED = "defect_detected"

DELIVERY_STATUS_SENT = "sent"
DELIVERY_STATUS_FAILED = "failed"

FAILURE_TELEGRAM_FORBIDDEN = "telegram_forbidden"
FAILURE_TELEGRAM_CHAT_NOT_FOUND = "telegram_chat_not_found"
FAILURE_TELEGRAM_BAD_REQUEST = "telegram_bad_request"
FAILURE_TRANSPORT_TIMEOUT = "transport_timeout"
FAILURE_TRANSPORT_ERROR = "transport_error"
FAILURE_INTERNAL_ERROR = "internal_error"

MSK_TIMEZONE = timezone(timedelta(hours=3), name="MSK")


@dataclass(frozen=True)
class NotificationDelivery:
    notification_delivery_id: str
    provider_user_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class NotificationBatch:
    batch_id: str
    deliveries: tuple[NotificationDelivery, ...]


class InternalNotificationsServer:
    def __init__(
        self,
        *,
        bot: Bot,
        host: str,
        port: int,
        push_path: str,
        auth_token: str | None = None,
    ) -> None:
        self._bot = bot
        self._host = host
        self._port = port
        self._push_path = push_path if push_path.startswith("/") else f"/{push_path}"
        self._auth_token = auth_token.strip() if auth_token else None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_post(self._push_path, self._handle_push)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self._host, port=self._port)
        await self._site.start()
        LOGGER.info(
            "Internal notifications endpoint started host=%s port=%s path=%s auth_enabled=%s",
            self._host,
            self._port,
            self._push_path,
            bool(self._auth_token),
        )

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    async def _handle_push(self, request: web.Request) -> web.Response:
        if not self._is_authorized_request(request):
            return web.json_response({"detail": "unauthorized"}, status=401)

        payload = await self._read_json_body(request)
        batch = _parse_batch_payload(payload)
        LOGGER.info(
            "notification_batch_received batch_id=%s delivery_count=%s",
            batch.batch_id,
            len(batch.deliveries),
        )

        results: list[dict[str, str]] = []
        for delivery in batch.deliveries:
            results.append(await self._process_delivery(batch.batch_id, delivery))

        return web.json_response({"batch_id": batch.batch_id, "results": results})

    async def _process_delivery(
        self,
        batch_id: str,
        delivery: NotificationDelivery,
    ) -> dict[str, str]:
        delivery_id = delivery.notification_delivery_id
        provider_user_id = delivery.provider_user_id
        LOGGER.info(
            "notification_delivery_send_started batch_id=%s notification_delivery_id=%s provider_user_id=%s",
            batch_id,
            delivery_id,
            provider_user_id,
        )

        text, reply_markup = _build_notification_content(delivery.payload)
        if text is None:
            LOGGER.warning(
                "notification_delivery_send_failed batch_id=%s notification_delivery_id=%s provider_user_id=%s failure_reason=%s",
                batch_id,
                delivery_id,
                provider_user_id,
                FAILURE_INTERNAL_ERROR,
            )
            return {
                "notification_delivery_id": delivery_id,
                "status": DELIVERY_STATUS_FAILED,
                "failure_reason": FAILURE_INTERNAL_ERROR,
            }

        try:
            await self._bot.send_message(
                chat_id=_parse_chat_id(provider_user_id),
                text=text,
                reply_markup=reply_markup,
            )
            LOGGER.info(
                "notification_delivery_send_succeeded batch_id=%s notification_delivery_id=%s provider_user_id=%s",
                batch_id,
                delivery_id,
                provider_user_id,
            )
            return {
                "notification_delivery_id": delivery_id,
                "status": DELIVERY_STATUS_SENT,
            }
        except Exception as exc:
            failure_reason = _normalize_delivery_failure(exc)
            LOGGER.warning(
                "notification_delivery_send_failed batch_id=%s notification_delivery_id=%s provider_user_id=%s failure_reason=%s error=%s",
                batch_id,
                delivery_id,
                provider_user_id,
                failure_reason,
                exc,
            )
            return {
                "notification_delivery_id": delivery_id,
                "status": DELIVERY_STATUS_FAILED,
                "failure_reason": failure_reason,
            }

    async def _read_json_body(self, request: web.Request) -> Any:
        try:
            return await request.json()
        except Exception:
            return {}

    def _is_authorized_request(self, request: web.Request) -> bool:
        if not self._auth_token:
            return True

        auth_header = request.headers.get("Authorization", "")
        expected_bearer = f"Bearer {self._auth_token}"
        if auth_header == expected_bearer:
            return True
        token_header = request.headers.get("X-Internal-Token", "")
        return token_header == self._auth_token


def _parse_batch_payload(payload: Any) -> NotificationBatch:
    payload_dict = payload if isinstance(payload, dict) else {}
    batch_id = _string_or_none(payload_dict.get("batch_id")) or "unknown_batch"

    parsed_deliveries: list[NotificationDelivery] = []
    raw_deliveries = payload_dict.get("deliveries")
    if isinstance(raw_deliveries, list):
        for raw_item in raw_deliveries:
            item_dict = raw_item if isinstance(raw_item, dict) else {}
            delivery_id = _string_or_none(item_dict.get("notification_delivery_id"))
            provider_user_id = _string_or_none(item_dict.get("provider_user_id"))
            event_payload = item_dict.get("payload") if isinstance(item_dict.get("payload"), dict) else {}
            if delivery_id is None or provider_user_id is None:
                continue
            parsed_deliveries.append(
                NotificationDelivery(
                    notification_delivery_id=delivery_id,
                    provider_user_id=provider_user_id,
                    payload=event_payload,
                )
            )

    return NotificationBatch(batch_id=batch_id, deliveries=tuple(parsed_deliveries))


def _build_notification_content(payload: dict[str, Any]) -> tuple[str | None, InlineKeyboardMarkup | None]:
    event_type = (_string_or_none(payload.get("event_type")) or "").lower()
    store_name = _string_or_none(payload.get("store_name")) or msg("common.unknown")
    device_name = _string_or_none(payload.get("device_display_name")) or msg("common.unknown")
    occurred_at = _format_notification_timestamp(_string_or_none(payload.get("occurred_at")))

    if event_type == EVENT_DEVICE_OFFLINE:
        return (
            msg(
                "notifications.device_offline",
                store_name=store_name,
                device_name=device_name,
                occurred_at=occurred_at,
            ),
            None,
        )
    if event_type == EVENT_DEVICE_ONLINE:
        return (
            msg(
                "notifications.device_online",
                store_name=store_name,
                device_name=device_name,
                occurred_at=occurred_at,
            ),
            None,
        )
    if event_type != EVENT_DEFECT_DETECTED:
        return None, None

    fruit_name = _string_or_none(payload.get("fruit_name")) or msg("common.unknown")
    defect_type = _string_or_none(payload.get("defect_type")) or msg("common.unknown")
    can_show_image = _bool_from_any(payload.get("can_show_image"), default=False)
    result_id = _string_or_none(payload.get("result_id"))
    reply_markup = (
        build_notification_image_keyboard(result_id)
        if can_show_image and result_id is not None
        else None
    )
    return (
        msg(
            "notifications.defect_detected",
            store_name=store_name,
            device_name=device_name,
            occurred_at=occurred_at,
            fruit_name=fruit_name,
            defect_type=defect_type,
        ),
        reply_markup,
    )


def _format_notification_timestamp(value: str | None) -> str:
    if not value:
        return msg("common.not_available")

    normalized = value
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MSK_TIMEZONE).strftime("%d.%m.%Y, %H:%M")


def _normalize_delivery_failure(exc: Exception) -> str:
    if isinstance(exc, TelegramForbiddenError):
        return FAILURE_TELEGRAM_FORBIDDEN
    if isinstance(exc, TelegramNotFound):
        return FAILURE_TELEGRAM_CHAT_NOT_FOUND
    if isinstance(exc, TelegramBadRequest):
        message = str(exc).lower()
        if "chat not found" in message:
            return FAILURE_TELEGRAM_CHAT_NOT_FOUND
        return FAILURE_TELEGRAM_BAD_REQUEST
    if isinstance(exc, TelegramNetworkError):
        message = str(exc).lower()
        if "timeout" in message or "timed out" in message:
            return FAILURE_TRANSPORT_TIMEOUT
        return FAILURE_TRANSPORT_ERROR
    if isinstance(exc, asyncio.TimeoutError):
        return FAILURE_TRANSPORT_TIMEOUT
    return FAILURE_INTERNAL_ERROR


def _parse_chat_id(provider_user_id: str) -> int | str:
    normalized = provider_user_id.strip()
    if normalized.lstrip("-").isdigit():
        return int(normalized)
    return normalized


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    normalized = str(value).strip()
    return normalized or None


def _bool_from_any(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)
