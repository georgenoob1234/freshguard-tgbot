from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import load_settings
from app.messages import clear_catalog_cache, get_bot_commands, load_catalog, msg
from app.oms import EnsureSessionResult, OmsClient
from app.private_session_middleware import PrivateSessionMiddleware

LOGGER = logging.getLogger(__name__)
router = Router(name="tgbot-router")


def setup_logging(log_level: str) -> None:
    resolved_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@router.message(Command("start"))
async def start_handler(message: Message, session_state: EnsureSessionResult | None = None) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /start from user_id=%s", user_id)

    if session_state is None:
        # Direct unit tests may call handlers without middleware injection.
        session_state = EnsureSessionResult(ok=True, degraded=False, is_banned=False)

    if session_state.degraded:
        await message.answer(msg("errors.oms_unavailable"))
        return

    if session_state.is_banned:
        await message.answer(msg("errors.banned"))
        return

    await message.answer(msg("start.body"))


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /help from user_id=%s", user_id)
    await message.answer(msg("help.body"))


@router.message(Command("ping"))
async def ping_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /ping from user_id=%s", user_id)
    await message.answer(msg("ping.reply"))


def build_dispatcher(oms_client: OmsClient) -> Dispatcher:
    dispatcher = Dispatcher()
    private_session_middleware = PrivateSessionMiddleware(oms_client)
    dispatcher.update.outer_middleware(private_session_middleware)
    dispatcher.include_router(router)
    return dispatcher


async def run_bot() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    LOGGER.info("Starting tgbot service")
    LOGGER.info(
        "Config loaded: messages_path=%s, log_level=%s, oms_base_url=%s, http_timeout_seconds=%s",
        settings.messages_path,
        settings.log_level,
        settings.oms_base_url,
        settings.http_timeout_seconds,
    )

    clear_catalog_cache()
    load_catalog(settings.messages_path)

    bot = Bot(token=settings.telegram_bot_token)
    oms_client = OmsClient(
        base_url=settings.oms_base_url,
        bot_token=settings.oms_bot_token,
        timeout_seconds=settings.http_timeout_seconds,
    )
    dispatcher = build_dispatcher(oms_client)

    try:
        commands = get_bot_commands(settings.messages_path)
        if commands:
            await bot.set_my_commands(commands)
            LOGGER.info("Bot command menu configured with %s commands", len(commands))
        else:
            LOGGER.warning("No bot commands configured; skipping set_my_commands")

        await dispatcher.start_polling(bot)
    finally:
        await oms_client.close()
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        LOGGER.info("Bot stopped by user")
    except Exception:
        LOGGER.exception("Bot crashed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
