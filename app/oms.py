from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp
from aiogram.types import Chat, User

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnsureSessionResult:
    ok: bool
    degraded: bool
    is_banned: bool = False


def _build_display_name(user: User) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    return " ".join(part for part in parts if part).strip()


class OmsClient:
    def __init__(self, base_url: str, bot_token: str, timeout_seconds: float) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/bot/v1/session/ensure"
        self._headers = {"Authorization": f"Bearer {bot_token}"}
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        await self._session.close()

    async def ensure_session(self, from_user: User | None, chat: Chat | None) -> EnsureSessionResult:
        if from_user is None or chat is None:
            LOGGER.warning("OMS ensure skipped: missing user or chat")
            return EnsureSessionResult(ok=False, degraded=True, is_banned=False)

        payload: dict[str, Any] = {
            "provider": "telegram",
            "provider_user_id": str(from_user.id),
            "provider_chat_id": str(chat.id),
        }

        if from_user.username:
            payload["username"] = from_user.username

        display_name = _build_display_name(from_user)
        if display_name:
            payload["display_name"] = display_name

        try:
            async with self._session.post(self._endpoint, json=payload, headers=self._headers) as response:
                if response.status >= 500:
                    LOGGER.warning(
                        "OMS ensure server error status=%s user_id=%s chat_id=%s",
                        response.status,
                        from_user.id,
                        chat.id,
                    )
                    return EnsureSessionResult(ok=False, degraded=True, is_banned=False)

                if response.status >= 400:
                    LOGGER.warning(
                        "OMS ensure rejected status=%s user_id=%s chat_id=%s",
                        response.status,
                        from_user.id,
                        chat.id,
                    )
                    return EnsureSessionResult(ok=False, degraded=True, is_banned=False)

                try:
                    response_data = await response.json(content_type=None)
                except Exception as exc:  # pragma: no cover - defensive fallback
                    LOGGER.warning(
                        "OMS ensure invalid response user_id=%s chat_id=%s error=%s",
                        from_user.id,
                        chat.id,
                        exc,
                    )
                    return EnsureSessionResult(ok=False, degraded=True, is_banned=False)
        except asyncio.TimeoutError:
            LOGGER.warning("OMS ensure timeout user_id=%s chat_id=%s", from_user.id, chat.id)
            return EnsureSessionResult(ok=False, degraded=True, is_banned=False)
        except aiohttp.ClientError as exc:
            LOGGER.warning(
                "OMS ensure request failed user_id=%s chat_id=%s error=%s",
                from_user.id,
                chat.id,
                exc,
            )
            return EnsureSessionResult(ok=False, degraded=True, is_banned=False)

        if not isinstance(response_data, dict):
            LOGGER.warning(
                "OMS ensure payload is not object type=%s user_id=%s chat_id=%s",
                type(response_data).__name__,
                from_user.id,
                chat.id,
            )
            return EnsureSessionResult(ok=False, degraded=True, is_banned=False)

        is_banned = bool(response_data.get("is_banned", False))
        return EnsureSessionResult(ok=True, degraded=False, is_banned=is_banned)
