from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app import messages as messages_module
from app.main import help_handler, ping_handler, start_handler
from app.oms import EnsureSessionResult


class DummyMessage:
    def __init__(self, user_id: int = 100) -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.answer = AsyncMock()


def _write_catalog(path: str, payload: dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as target:
        json.dump(payload, target, ensure_ascii=False)


def test_start_handler_replies_from_catalog(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(
        str(catalog_path),
        {
            "start.title": "FreshGuard",
            "start.body": "Тестовый запуск.",
            "help.body": "Справка",
            "ping.reply": "Pong!",
            "errors.oms_unavailable": "OMS недоступна.",
            "errors.banned": "Доступ ограничен.",
        },
    )
    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    message = DummyMessage()
    asyncio.run(start_handler(message, session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False)))

    message.answer.assert_awaited_once_with("Тестовый запуск.")


def test_start_handler_replies_when_oms_unavailable(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(
        str(catalog_path),
        {
            "start.body": "Тестовый запуск.",
            "help.body": "Справка",
            "ping.reply": "Pong!",
            "errors.oms_unavailable": "OMS недоступна.",
            "errors.banned": "Доступ ограничен.",
        },
    )
    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    message = DummyMessage()
    asyncio.run(start_handler(message, session_state=EnsureSessionResult(ok=False, degraded=True, is_banned=False)))

    message.answer.assert_awaited_once_with("OMS недоступна.")


def test_start_handler_replies_when_user_banned(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(
        str(catalog_path),
        {
            "start.body": "Тестовый запуск.",
            "help.body": "Справка",
            "ping.reply": "Pong!",
            "errors.oms_unavailable": "OMS недоступна.",
            "errors.banned": "Доступ ограничен.",
        },
    )
    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    message = DummyMessage()
    asyncio.run(start_handler(message, session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=True)))

    message.answer.assert_awaited_once_with("Доступ ограничен.")


def test_help_handler_replies_from_catalog(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(
        str(catalog_path),
        {
            "start.title": "FreshGuard",
            "start.body": "Тестовый запуск.",
            "help.body": "Справка",
            "ping.reply": "Pong!",
        },
    )
    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    message = DummyMessage()
    asyncio.run(help_handler(message))

    message.answer.assert_awaited_once_with("Справка")


def test_ping_handler_replies_from_catalog(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(
        str(catalog_path),
        {
            "start.title": "FreshGuard",
            "start.body": "Тестовый запуск.",
            "help.body": "Справка",
            "ping.reply": "Pong!",
        },
    )
    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    message = DummyMessage()
    asyncio.run(ping_handler(message))

    message.answer.assert_awaited_once_with("Pong!")
