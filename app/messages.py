from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from aiogram.types import BotCommand

LOGGER = logging.getLogger(__name__)
DEFAULT_MESSAGES_PATH = Path("config/messages.ru.json")


def _messages_path_from_env() -> Path:
    raw_path = os.getenv("MESSAGES_PATH", str(DEFAULT_MESSAGES_PATH)).strip()
    return Path(raw_path or str(DEFAULT_MESSAGES_PATH))


@dataclass
class _CatalogBundle:
    messages: dict[str, str]
    bot_commands: dict[str, str]


@lru_cache(maxsize=8)
def _load_catalog_bundle(path_str: str) -> _CatalogBundle:
    path = Path(path_str)
    with path.open("r", encoding="utf-8") as source:
        data = json.load(source)

    if not isinstance(data, dict):
        raise ValueError(f"Messages catalog must be an object, got: {type(data).__name__}")

    messages: dict[str, str] = {}
    for key, value in data.items():
        if key == "bot_commands":
            continue
        if isinstance(value, str):
            messages[key] = value
        else:
            LOGGER.warning("Message value for key '%s' is not a string", key)
            messages[key] = str(value)

    raw_commands = data.get("bot_commands")
    bot_commands: dict[str, str] = {}

    if raw_commands is None:
        LOGGER.warning("Missing bot_commands section in messages catalog: %s", path)
    elif not isinstance(raw_commands, dict):
        LOGGER.warning("bot_commands must be an object in messages catalog: %s", path)
    else:
        for raw_command, raw_description in raw_commands.items():
            if not isinstance(raw_command, str) or not raw_command.strip():
                LOGGER.warning("Skipping invalid bot command key: %r", raw_command)
                continue
            if not isinstance(raw_description, str) or not raw_description.strip():
                LOGGER.warning("Skipping invalid bot command description for key '%s'", raw_command)
                continue

            command = raw_command.strip().lstrip("/")
            if not command:
                LOGGER.warning("Skipping empty bot command key after normalization: %r", raw_command)
                continue

            bot_commands[command] = raw_description.strip()

    return _CatalogBundle(messages=messages, bot_commands=bot_commands)


def load_catalog(messages_path: Path | None = None) -> dict[str, str]:
    path = messages_path or _messages_path_from_env()
    return _load_catalog_bundle(str(path)).messages


def get_bot_commands(messages_path: Path | None = None) -> list[BotCommand]:
    path = messages_path or _messages_path_from_env()
    bundle = _load_catalog_bundle(str(path))
    return [BotCommand(command=command, description=description) for command, description in bundle.bot_commands.items()]


def clear_catalog_cache() -> None:
    _load_catalog_bundle.cache_clear()


def msg(key: str, **kwargs: Any) -> str:
    template = load_catalog().get(key)
    if template is None:
        LOGGER.warning("Missing message key: %s", key)
        return f"[missing:{key}]"

    try:
        return template.format(**kwargs)
    except KeyError as exc:
        LOGGER.warning("Missing formatting argument for key '%s': %s", key, exc)
        return template
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.warning("Formatting error for key '%s': %s", key, exc)
        return f"[format_error:{key}]"
