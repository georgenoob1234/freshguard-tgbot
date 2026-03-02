from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from app.oms import OmsClient

LOGGER = logging.getLogger(__name__)


class PrivateSessionMiddleware(BaseMiddleware):
    def __init__(self, oms_client: OmsClient) -> None:
        self._oms_client = oms_client

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = None
        chat = None

        if isinstance(event, Update):
            message: Message | None = event.message
            callback_query: CallbackQuery | None = event.callback_query
            if message is not None:
                from_user = message.from_user
                chat = message.chat
            elif callback_query is not None:
                from_user = callback_query.from_user
                if callback_query.message is None:
                    return None
                chat = callback_query.message.chat
            else:
                return await handler(event, data)
        elif isinstance(event, Message):
            from_user = event.from_user
            chat = event.chat
        elif isinstance(event, CallbackQuery):
            from_user = event.from_user
            if event.message is None:
                return None
            chat = event.message.chat
        else:
            return await handler(event, data)

        if chat is None or chat.type != "private":
            LOGGER.debug("Ignoring non-private update chat_type=%s", getattr(chat, "type", None))
            return None

        data["session_state"] = await self._oms_client.ensure_session(from_user=from_user, chat=chat)
        return await handler(event, data)
