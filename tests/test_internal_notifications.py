from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
)

from app import messages as messages_module
from app.callbacks import build_notification_image_callback
from app.internal_notifications import (
    DELIVERY_STATUS_FAILED,
    DELIVERY_STATUS_SENT,
    FAILURE_INTERNAL_ERROR,
    FAILURE_TELEGRAM_BAD_REQUEST,
    FAILURE_TELEGRAM_CHAT_NOT_FOUND,
    FAILURE_TELEGRAM_FORBIDDEN,
    FAILURE_TRANSPORT_TIMEOUT,
    InternalNotificationsServer,
    _build_notification_content,
    _normalize_delivery_failure,
)


class DummyRequest:
    def __init__(self, payload, headers: dict[str, str] | None = None) -> None:
        self._payload = payload
        self.headers = headers or {}

    async def json(self):
        return self._payload


class FakeBot:
    def __init__(self, *, side_effect=None) -> None:
        self.send_message = AsyncMock(side_effect=side_effect)


def _response_json(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


def _fake_method():
    return SimpleNamespace(chat_id=123)


def _prepare_catalog(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGES_PATH", "config/messages.en.json")
    messages_module.clear_catalog_cache()


def test_internal_push_accepts_valid_batch_and_returns_success(monkeypatch) -> None:
    _prepare_catalog(monkeypatch)
    bot = FakeBot()
    server = InternalNotificationsServer(
        bot=bot,
        host="127.0.0.1",
        port=8081,
        push_path="/internal/notifications/push",
    )
    payload = {
        "batch_id": "batch-1",
        "deliveries": [
            {
                "notification_delivery_id": "d-1",
                "provider_user_id": "100",
                "payload": {
                    "event_type": "device_offline",
                    "store_name": "Main Store",
                    "device_display_name": "Scale A",
                    "occurred_at": "2026-03-14T12:00:00Z",
                },
            }
        ],
    }

    response = asyncio.run(server._handle_push(DummyRequest(payload)))
    response_payload = _response_json(response)

    assert response.status == 200
    assert response_payload["batch_id"] == "batch-1"
    assert response_payload["results"] == [
        {
            "notification_delivery_id": "d-1",
            "status": DELIVERY_STATUS_SENT,
        }
    ]
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs["chat_id"] == 100
    assert bot.send_message.await_args.kwargs["reply_markup"] is None


def test_internal_push_mixed_success_and_failure(monkeypatch) -> None:
    _prepare_catalog(monkeypatch)
    bot = FakeBot(side_effect=[None, RuntimeError("boom")])
    server = InternalNotificationsServer(
        bot=bot,
        host="127.0.0.1",
        port=8081,
        push_path="/internal/notifications/push",
    )
    payload = {
        "batch_id": "batch-2",
        "deliveries": [
            {
                "notification_delivery_id": "d-1",
                "provider_user_id": "101",
                "payload": {
                    "event_type": "device_online",
                    "store_name": "Main Store",
                    "device_display_name": "Scale A",
                    "occurred_at": "2026-03-14T12:01:00Z",
                },
            },
            {
                "notification_delivery_id": "d-2",
                "provider_user_id": "102",
                "payload": {
                    "event_type": "device_online",
                    "store_name": "Main Store",
                    "device_display_name": "Scale B",
                    "occurred_at": "2026-03-14T12:02:00Z",
                },
            },
        ],
    }

    response = asyncio.run(server._handle_push(DummyRequest(payload)))
    response_payload = _response_json(response)

    assert response.status == 200
    assert response_payload["results"][0] == {
        "notification_delivery_id": "d-1",
        "status": DELIVERY_STATUS_SENT,
    }
    assert response_payload["results"][1] == {
        "notification_delivery_id": "d-2",
        "status": DELIVERY_STATUS_FAILED,
        "failure_reason": FAILURE_INTERNAL_ERROR,
    }


def test_delivery_failure_normalization_representative_errors() -> None:
    assert (
        _normalize_delivery_failure(TelegramForbiddenError(_fake_method(), "forbidden"))
        == FAILURE_TELEGRAM_FORBIDDEN
    )
    assert (
        _normalize_delivery_failure(TelegramNotFound(_fake_method(), "chat not found"))
        == FAILURE_TELEGRAM_CHAT_NOT_FOUND
    )
    assert (
        _normalize_delivery_failure(TelegramBadRequest(_fake_method(), "chat not found"))
        == FAILURE_TELEGRAM_CHAT_NOT_FOUND
    )
    assert (
        _normalize_delivery_failure(TelegramBadRequest(_fake_method(), "message is too long"))
        == FAILURE_TELEGRAM_BAD_REQUEST
    )
    assert (
        _normalize_delivery_failure(TelegramNetworkError(_fake_method(), "Request timeout"))
        == FAILURE_TRANSPORT_TIMEOUT
    )
    assert _normalize_delivery_failure(asyncio.TimeoutError()) == FAILURE_TRANSPORT_TIMEOUT
    assert _normalize_delivery_failure(RuntimeError("boom")) == FAILURE_INTERNAL_ERROR


def test_defect_notification_has_show_image_button_only_when_allowed(monkeypatch) -> None:
    _prepare_catalog(monkeypatch)
    text_with_button, markup_with_button = _build_notification_content(
        {
            "event_type": "defect_detected",
            "store_name": "Main Store",
            "device_display_name": "Scale A",
            "occurred_at": "2026-03-14T12:00:00Z",
            "fruit_name": "banana",
            "defect_type": "bruise",
            "result_id": "res-1",
            "can_show_image": True,
        }
    )
    assert text_with_button is not None
    assert markup_with_button is not None
    callback_data = [button.callback_data for row in markup_with_button.inline_keyboard for button in row]
    assert callback_data == [build_notification_image_callback("res-1")]

    text_without_button, markup_without_button = _build_notification_content(
        {
            "event_type": "defect_detected",
            "store_name": "Main Store",
            "device_display_name": "Scale A",
            "occurred_at": "2026-03-14T12:00:00Z",
            "fruit_name": "banana",
            "defect_type": "bruise",
            "result_id": "res-1",
            "can_show_image": False,
        }
    )
    assert text_without_button is not None
    assert markup_without_button is None


def test_status_notifications_render_without_buttons(monkeypatch) -> None:
    _prepare_catalog(monkeypatch)
    offline_text, offline_markup = _build_notification_content(
        {
            "event_type": "device_offline",
            "store_name": "Main Store",
            "device_display_name": "Scale A",
            "occurred_at": "2026-03-14T12:00:00Z",
        }
    )
    online_text, online_markup = _build_notification_content(
        {
            "event_type": "device_online",
            "store_name": "Main Store",
            "device_display_name": "Scale A",
            "occurred_at": "2026-03-14T12:00:00Z",
        }
    )

    assert offline_text is not None
    assert online_text is not None
    assert offline_markup is None
    assert online_markup is None
