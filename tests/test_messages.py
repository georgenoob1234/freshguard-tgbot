from __future__ import annotations

import json

from app import messages as messages_module


def _write_catalog(path: str, payload: dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as target:
        json.dump(payload, target, ensure_ascii=False)


def test_msg_returns_known_key(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(str(catalog_path), {"plain.key": "Привет"})

    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    assert messages_module.msg("plain.key") == "Привет"


def test_msg_missing_key_fallback(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(str(catalog_path), {"known.key": "Значение"})

    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    assert messages_module.msg("unknown.key") == "[missing:unknown.key]"


def test_msg_formatting_works(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(str(catalog_path), {"greet.key": "Привет, {name}!"})

    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    assert messages_module.msg("greet.key", name="Алиса") == "Привет, Алиса!"


def test_msg_missing_format_arg_does_not_crash(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    template = "Привет, {name}!"
    _write_catalog(str(catalog_path), {"greet.key": template})

    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    assert messages_module.msg("greet.key", wrong_arg="Боб") == template


def test_catalog_cache_can_be_cleared(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(str(catalog_path), {"cache.key": "Версия 1"})

    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    assert messages_module.msg("cache.key") == "Версия 1"

    _write_catalog(str(catalog_path), {"cache.key": "Версия 2"})
    assert messages_module.msg("cache.key") == "Версия 1"

    messages_module.clear_catalog_cache()
    assert messages_module.msg("cache.key") == "Версия 2"


def test_get_bot_commands_loads_mapping(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(
        str(catalog_path),
        {
            "help.body": "Справка",
            "bot_commands": {
                "start": "Подключение или переподключение к магазину",
                "help": "Справка",
            },
        },
    )

    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    commands = messages_module.get_bot_commands()
    assert [command.command for command in commands] == ["start", "help"]
    assert [command.description for command in commands] == [
        "Подключение или переподключение к магазину",
        "Справка",
    ]


def test_get_bot_commands_missing_mapping_returns_empty(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(str(catalog_path), {"help.body": "Справка"})

    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()

    assert messages_module.get_bot_commands() == []
