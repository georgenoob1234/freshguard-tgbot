from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.callbacks import (
    DEVICE_BACK,
    DEVICE_LAST_PREFIX,
    DEVICE_PHOTO_PREFIX,
    DEVICE_SELECT_PREFIX,
    DEVICE_STATUS_PREFIX,
    DEVICE_TARE_CANCEL_PREFIX,
    DEVICE_TARE_CONFIRM_PREFIX,
    DEVICE_TARE_MENU_PREFIX,
    DEVICE_TARE_RESET_PREFIX,
    STORE_SWITCH_PREFIX,
    UNLINK_CANCEL,
    UNLINK_CONFIRM_PREFIX,
    UNLINK_PICK_PREFIX,
    parse_device_last_callback,
    parse_device_photo_callback,
    parse_device_select_callback,
    parse_device_status_callback,
    parse_device_tare_cancel_callback,
    parse_device_tare_confirm_callback,
    parse_device_tare_menu_callback,
    parse_device_tare_reset_callback,
    parse_store_switch_callback,
    parse_unlink_confirm_callback,
    parse_unlink_pick_callback,
)
from app.config import load_settings
from app.keyboards import (
    build_device_list_keyboard,
    build_device_tare_keyboard,
    build_selected_device_keyboard,
    build_store_switch_keyboard,
    build_unlink_confirmation_keyboard,
    build_unlink_pick_keyboard,
)
from app.messages import clear_catalog_cache, get_bot_commands, load_catalog, msg
from app.oms import (
    ERROR_ALREADY_LINKED,
    ERROR_DEVICE_NOT_IN_ACTIVE_STORE,
    ERROR_EXHAUSTED,
    ERROR_EXPIRED,
    ERROR_INVALID_CODE,
    ERROR_NO_ACTIVE_STORE,
    ERROR_NOT_LINKED,
    ERROR_PERMISSION_DENIED,
    ERROR_RESULT_NOT_FOUND,
    ERROR_REVOKED,
    ERROR_STORE_INACTIVE,
    ERROR_STORE_HAS_NO_DEVICES,
    ERROR_STORE_NOT_FOUND,
    ERROR_UNAVAILABLE,
    DeviceStatusSummary,
    EnsureSessionResult,
    InviteSummary,
    LatestResultSummary,
    OmsClient,
    StoreSummary,
    StoresResult,
)
from app.private_session_middleware import PrivateSessionMiddleware

LOGGER = logging.getLogger(__name__)
router = Router(name="tgbot-router")
INVITE_CODE_PATTERN = re.compile(r"^\d{6}$")
MSK_TIMEZONE = timezone(timedelta(hours=3), name="MSK")
LINK_ERROR_MESSAGES = {
    ERROR_ALREADY_LINKED: "link.already_linked",
    ERROR_INVALID_CODE: "link.invalid",
    ERROR_EXPIRED: "link.expired",
    ERROR_REVOKED: "link.revoked",
    ERROR_EXHAUSTED: "link.exhausted",
    ERROR_STORE_INACTIVE: "link.store_inactive",
}


def setup_logging(log_level: str) -> None:
    resolved_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _get_store_name(store: StoreSummary | None) -> str:
    if store is None:
        return msg("common.active_store_unknown")
    return store.name


def _join_parts(*parts: str) -> str:
    return "\n\n".join(part for part in parts if part)


def _format_store_list(stores: tuple[StoreSummary, ...]) -> str:
    return "\n".join(f"- {store.name}" for store in stores)


def _build_start_text(session_state: EnsureSessionResult) -> str:
    if not session_state.is_linked:
        return msg("start.unlinked")

    if session_state.has_multiple_stores:
        return msg(
            "start.linked_multi_store",
            memberships_count=session_state.memberships_count,
            store_name=_get_store_name(session_state.active_store),
        )

    active_store = session_state.active_store or StoreSummary(id="single-store", name=msg("common.active_store_unknown"))
    return msg("start.linked_single_store", store_name=active_store.name)


def _build_stores_text(stores_result: StoresResult) -> str:
    if not stores_result.stores:
        return msg("stores.empty")

    if len(stores_result.stores) == 1:
        store = stores_result.active_store or stores_result.stores[0]
        return msg("stores.single", store_name=store.name)

    return msg(
        "stores.choose_active",
        stores_list=_format_store_list(stores_result.stores),
        active_store_name=_get_store_name(stores_result.active_store),
    )


def _extract_command_arg(message: Message, command: CommandObject | None = None) -> str | None:
    if command is not None and command.args:
        return command.args.strip() or None

    raw_text = getattr(message, "text", None) or ""
    parts = raw_text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    return parts[1].strip() or None


def _is_valid_invite_code(code: str | None) -> bool:
    return bool(code and INVITE_CODE_PATTERN.fullmatch(code))


def _find_store(stores_result: StoresResult, store_id: str) -> StoreSummary | None:
    for store in stores_result.stores:
        if store.id == store_id:
            return store
    return None


def _parse_datetime_string(raw_value: str) -> datetime | None:
    normalized = raw_value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_invite_expiry(expires_at: str) -> str:
    parsed = _parse_datetime_string(expires_at)
    if parsed is None:
        return expires_at
    return parsed.astimezone(MSK_TIMEZONE).strftime("%d.%m.%Y, %H:%M")


def _resolve_invite_store(invite: InviteSummary, session_state: EnsureSessionResult | None) -> StoreSummary | None:
    if invite.store is not None:
        return invite.store
    if session_state is None or session_state.active_store is None:
        return None
    if invite.store_id is None or invite.store_id == session_state.active_store.id:
        return session_state.active_store
    return None


def _format_timestamp(value: str | None) -> str:
    if not value:
        return msg("common.not_available")

    parsed = _parse_datetime_string(value)
    if parsed is None:
        return value
    return parsed.astimezone(MSK_TIMEZONE).strftime("%d.%m.%Y, %H:%M")


def _format_yes_no(value: bool | None) -> str:
    if value is None:
        return msg("common.not_available")
    return msg("common.yes") if value else msg("common.no")


def _format_online_state(value: bool | None) -> str:
    if value is None:
        return msg("common.not_available")
    return msg("common.online") if value else msg("common.offline")


def _format_weight_grams(value: Any) -> str:
    if value is None:
        return msg("common.not_available")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value} g"


def _format_fruits_summary(result: LatestResultSummary) -> str:
    if not result.fruits:
        return msg("results.no_fruits")

    formatted_items: list[str] = []
    for fruit in result.fruits:
        fruit_name = fruit.name or msg("common.unknown")
        if fruit.weight_grams is None:
            formatted_items.append(fruit_name)
            continue
        formatted_items.append(f"{fruit_name} ({_format_weight_grams(fruit.weight_grams)})")
    return ", ".join(formatted_items)


def _format_defect_summary(result: LatestResultSummary) -> str:
    if not result.defect.value:
        return msg("common.no")
    if result.defect.type:
        return f"{msg('common.yes')} ({result.defect.type})"
    return msg("common.yes")


def _build_devices_text(store: StoreSummary) -> str:
    return msg("devices.choose", store_name=store.name)


def _build_selected_device_card_text(
    session_state: EnsureSessionResult | None,
    device_id: str,
    status: DeviceStatusSummary | None = None,
) -> str:
    device_name = status.display_name if status is not None else device_id
    lines = [
        msg("devices.selected", device_name=device_name),
        f"{msg('labels.store')}: {_get_store_name(session_state.active_store if session_state else None)}",
        f"{msg('labels.online')}: {_format_online_state(status.online if status is not None else None)}",
        f"{msg('labels.connected')}: {_format_yes_no(status.connected if status is not None else None)}",
    ]
    return "\n".join(lines)


def _build_device_status_text(status: DeviceStatusSummary) -> str:
    lines = [
        msg("devices.status_heading", device_name=status.display_name),
        f"{msg('labels.connected')}: {_format_yes_no(status.connected)}",
        f"{msg('labels.online')}: {_format_online_state(status.online)}",
        f"{msg('labels.last_seen')}: {_format_timestamp(status.last_seen_at)}",
    ]
    return "\n".join(lines)


def _build_latest_result_text(latest_result: LatestResultSummary, *, store_name: str | None = None) -> str:
    lines = [
        msg("results.store_heading", store_name=store_name)
        if store_name is not None
        else msg("results.device_heading", device_name=latest_result.device_display_name),
    ]
    if store_name is not None:
        lines.append(f"{msg('labels.device')}: {latest_result.device_display_name}")
    lines.append(f"{msg('labels.received_at')}: {_format_timestamp(latest_result.received_at)}")
    if latest_result.sent_at:
        lines.append(f"{msg('labels.sent_at')}: {_format_timestamp(latest_result.sent_at)}")
    if latest_result.weight_grams is not None:
        lines.append(f"{msg('labels.weight_grams')}: {_format_weight_grams(latest_result.weight_grams)}")
    if latest_result.image_id:
        lines.append(f"{msg('labels.image_id')}: {latest_result.image_id}")
    lines.append(f"{msg('labels.defect')}: {_format_defect_summary(latest_result)}")
    lines.append(f"{msg('labels.fruits')}: {_format_fruits_summary(latest_result)}")
    return "\n".join(lines)


def _build_error_text(
    error_code: str | None,
    *,
    store_name: str | None = None,
    device_name: str | None = None,
    result_scope: str | None = None,
) -> str:
    if error_code == ERROR_UNAVAILABLE:
        return msg("errors.oms_unavailable")
    if error_code == ERROR_PERMISSION_DENIED:
        return msg("errors.permission_denied")
    if error_code == ERROR_NO_ACTIVE_STORE:
        return msg("errors.no_active_store")
    if error_code == ERROR_NOT_LINKED:
        return msg("errors.not_linked")
    if error_code == ERROR_STORE_NOT_FOUND:
        return msg("errors.store_not_found")
    if error_code == ERROR_DEVICE_NOT_IN_ACTIVE_STORE:
        return msg("devices.not_in_active_store")
    if error_code == ERROR_STORE_HAS_NO_DEVICES:
        return msg("devices.empty", store_name=store_name or msg("common.active_store_unknown"))
    if error_code == ERROR_RESULT_NOT_FOUND and result_scope == "store":
        return msg("results.store_last_not_found", store_name=store_name or msg("common.active_store_unknown"))
    if error_code == ERROR_RESULT_NOT_FOUND and result_scope == "device":
        return msg("results.device_last_not_found", device_name=device_name or msg("common.unknown"))
    return msg("errors.generic")


def _callback_chat(callback_query: CallbackQuery):
    return callback_query.message.chat if callback_query.message else None


async def _require_active_store_for_message(
    message: Message,
    session_state: EnsureSessionResult | None,
) -> StoreSummary | None:
    active_store = session_state.active_store if session_state is not None else None
    if active_store is not None:
        return active_store
    await _send_message(message, msg("errors.no_active_store"))
    return None


async def _require_active_store_for_callback(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None,
) -> StoreSummary | None:
    active_store = session_state.active_store if session_state is not None else None
    if active_store is not None:
        return active_store
    await _edit_callback_message(callback_query, msg("errors.no_active_store"))
    await callback_query.answer()
    return None


async def _require_selected_device_for_callback(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None,
    device_id: str,
) -> bool:
    active_device_id = session_state.active_device_id if session_state is not None else None
    if active_device_id is None or active_device_id != device_id:
        await callback_query.answer(msg("devices.no_active_device"), show_alert=True)
        return False
    return True


async def _load_selected_device_card_text(
    oms_client: OmsClient,
    from_user,
    chat,
    session_state: EnsureSessionResult | None,
    device_id: str,
    *,
    notice_text: str | None = None,
) -> str:
    status_result = await oms_client.get_device_status(from_user, chat, device_id=device_id)
    status = status_result.status if status_result.ok else None
    card_text = _build_selected_device_card_text(session_state, device_id, status=status)
    return _join_parts(notice_text or "", card_text)


async def _send_message(message: Message, text: str, *, reply_markup: object | None = None) -> None:
    if reply_markup is None:
        await message.answer(text)
        return
    await message.answer(text, reply_markup=reply_markup)


async def _edit_callback_message(
    callback_query: CallbackQuery,
    text: str,
    *,
    reply_markup: object | None = None,
) -> None:
    if callback_query.message is None:
        return
    if reply_markup is None:
        await callback_query.message.edit_text(text)
        return
    await callback_query.message.edit_text(text, reply_markup=reply_markup)


async def _reply_blocked_message(message: Message, session_state: EnsureSessionResult | None) -> bool:
    if session_state is None:
        return False
    if session_state.degraded:
        await _send_message(message, msg("errors.oms_unavailable"))
        return True
    if session_state.is_banned:
        await _send_message(message, msg("errors.banned"))
        return True
    return False


async def _reply_blocked_callback(callback_query: CallbackQuery, session_state: EnsureSessionResult | None) -> bool:
    if session_state is None:
        return False
    if session_state.degraded:
        await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
        return True
    if session_state.is_banned:
        await callback_query.answer(msg("errors.banned"), show_alert=True)
        return True
    return False


async def _require_oms_client_for_message(message: Message, oms_client: OmsClient | None) -> OmsClient | None:
    if oms_client is not None:
        return oms_client
    await _send_message(message, msg("errors.oms_unavailable"))
    return None


async def _require_oms_client_for_callback(
    callback_query: CallbackQuery,
    oms_client: OmsClient | None,
) -> OmsClient | None:
    if oms_client is not None:
        return oms_client
    await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
    return None


@router.message(Command("start"))
async def start_handler(message: Message, session_state: EnsureSessionResult | None = None) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /start from user_id=%s", user_id)

    if session_state is None:
        # Direct unit tests may call handlers without middleware injection.
        session_state = EnsureSessionResult(ok=True, degraded=False, is_banned=False)

    if session_state.degraded:
        await _send_message(message, msg("errors.oms_unavailable"))
        return

    if session_state.is_banned:
        await _send_message(message, msg("errors.banned"))
        return

    await _send_message(message, _build_start_text(session_state))


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /help from user_id=%s", user_id)
    await _send_message(message, msg("help.body"))


@router.message(Command("ping"))
async def ping_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /ping from user_id=%s", user_id)
    await _send_message(message, msg("ping.reply"))


@router.message(Command("link"))
async def link_handler(
    message: Message,
    command: CommandObject | None = None,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /link from user_id=%s", user_id)

    if await _reply_blocked_message(message, session_state):
        return

    oms_client = await _require_oms_client_for_message(message, oms_client)
    if oms_client is None:
        return

    invite_code = _extract_command_arg(message, command)
    if invite_code is None:
        await _send_message(message, msg("link.usage_hint"))
        return
    if not _is_valid_invite_code(invite_code):
        await _send_message(message, msg("link.invalid_code"))
        return

    redeem_result = await oms_client.redeem_invite(message.from_user, message.chat, invite_code)
    if not redeem_result.ok:
        if redeem_result.error_code == ERROR_UNAVAILABLE:
            await _send_message(message, msg("errors.oms_unavailable"))
            return
        await _send_message(message, msg(LINK_ERROR_MESSAGES.get(redeem_result.error_code, "errors.generic")))
        return

    refreshed_session = await oms_client.ensure_session(message.from_user, message.chat)
    success_state = refreshed_session if not refreshed_session.degraded else session_state
    if redeem_result.already_linked:
        success_message = msg("link.already_linked")
    else:
        store_name = _get_store_name(
            (success_state.active_store if success_state is not None else None) or redeem_result.active_store
        )
        success_message = msg("link.success", store_name=store_name)
    if success_state is not None and not success_state.degraded and not success_state.is_banned:
        success_message = _join_parts(success_message, _build_start_text(success_state))

    await _send_message(message, success_message)


@router.message(Command("stores"))
async def stores_handler(
    message: Message,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /stores from user_id=%s", user_id)

    if await _reply_blocked_message(message, session_state):
        return

    oms_client = await _require_oms_client_for_message(message, oms_client)
    if oms_client is None:
        return

    stores_result = await oms_client.list_stores(message.from_user, message.chat)
    if not stores_result.ok:
        if stores_result.error_code == ERROR_UNAVAILABLE:
            await _send_message(message, msg("errors.oms_unavailable"))
            return
        if stores_result.error_code == ERROR_NOT_LINKED:
            await _send_message(message, msg("stores.empty"))
            return
        await _send_message(message, msg("errors.generic"))
        return

    reply_markup = build_store_switch_keyboard(stores_result.stores) if stores_result.has_multiple_stores else None
    await _send_message(message, _build_stores_text(stores_result), reply_markup=reply_markup)


@router.message(Command("devices"))
async def devices_handler(
    message: Message,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /devices from user_id=%s", user_id)

    if await _reply_blocked_message(message, session_state):
        return

    oms_client = await _require_oms_client_for_message(message, oms_client)
    if oms_client is None:
        return

    active_store = await _require_active_store_for_message(message, session_state)
    if active_store is None:
        return

    devices_result = await oms_client.list_store_devices(message.from_user, message.chat, store_id=active_store.id)
    if not devices_result.ok:
        await _send_message(message, _build_error_text(devices_result.error_code, store_name=active_store.name))
        return

    if not devices_result.devices:
        await _send_message(message, msg("devices.empty", store_name=active_store.name))
        return

    await _send_message(
        message,
        _build_devices_text(active_store),
        reply_markup=build_device_list_keyboard(devices_result.devices),
    )


@router.message(Command("last"))
async def last_handler(
    message: Message,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /last from user_id=%s", user_id)

    if await _reply_blocked_message(message, session_state):
        return

    oms_client = await _require_oms_client_for_message(message, oms_client)
    if oms_client is None:
        return

    active_store = await _require_active_store_for_message(message, session_state)
    if active_store is None:
        return

    latest_result = await oms_client.get_latest_result(message.from_user, message.chat)
    if not latest_result.ok:
        await _send_message(
            message,
            _build_error_text(
                latest_result.error_code,
                store_name=active_store.name,
                result_scope="store",
            ),
        )
        return

    if latest_result.result is None:
        await _send_message(message, msg("errors.generic"))
        return

    await _send_message(message, _build_latest_result_text(latest_result.result, store_name=active_store.name))


@router.message(Command("invite"))
async def invite_handler(
    message: Message,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /invite from user_id=%s", user_id)

    if await _reply_blocked_message(message, session_state):
        return

    oms_client = await _require_oms_client_for_message(message, oms_client)
    if oms_client is None:
        return

    invite_result = await oms_client.create_invite(message.from_user, message.chat, role="operator")
    if not invite_result.ok:
        if invite_result.error_code == ERROR_UNAVAILABLE:
            await _send_message(message, msg("errors.oms_unavailable"))
            return
        if invite_result.error_code == ERROR_PERMISSION_DENIED:
            await _send_message(message, msg("invite.permission_denied"))
            return
        if invite_result.error_code == ERROR_STORE_INACTIVE:
            await _send_message(message, msg("invite.store_inactive"))
            return
        if invite_result.error_code in {ERROR_NO_ACTIVE_STORE, ERROR_NOT_LINKED, ERROR_STORE_NOT_FOUND}:
            await _send_message(message, msg("invite.no_active_store"))
            return
        await _send_message(message, msg("errors.generic"))
        return

    if invite_result.invite is None:
        await _send_message(message, msg("errors.generic"))
        return

    active_store = _resolve_invite_store(invite_result.invite, session_state)
    store_name = _get_store_name(active_store)
    if invite_result.invite.expires_at:
        invite_text = msg(
            "invite.created_with_expiry",
            store_name=store_name,
            code=invite_result.invite.code,
            expiry=_format_invite_expiry(invite_result.invite.expires_at),
        )
    else:
        invite_text = msg("invite.created", store_name=store_name, code=invite_result.invite.code)

    await _send_message(message, invite_text)


@router.message(Command("unlink"))
async def unlink_handler(
    message: Message,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    LOGGER.info("Handling /unlink from user_id=%s", user_id)

    if await _reply_blocked_message(message, session_state):
        return

    oms_client = await _require_oms_client_for_message(message, oms_client)
    if oms_client is None:
        return

    stores_result = await oms_client.list_stores(message.from_user, message.chat)
    if not stores_result.ok:
        if stores_result.error_code == ERROR_UNAVAILABLE:
            await _send_message(message, msg("errors.oms_unavailable"))
            return
        if stores_result.error_code == ERROR_NOT_LINKED:
            await _send_message(message, msg("unlink.no_memberships"))
            return
        await _send_message(message, msg("errors.generic"))
        return

    if not stores_result.stores:
        await _send_message(message, msg("unlink.no_memberships"))
        return

    if len(stores_result.stores) == 1:
        store = stores_result.stores[0]
        await _send_message(
            message,
            msg("unlink.confirm", store_name=store.name),
            reply_markup=build_unlink_confirmation_keyboard(store.id),
        )
        return

    await _send_message(
        message,
        msg("unlink.choose_store"),
        reply_markup=build_unlink_pick_keyboard(stores_result.stores),
    )


@router.callback_query(F.data.startswith(STORE_SWITCH_PREFIX))
async def store_switch_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    store_id = parse_store_switch_callback(callback_query.data)
    if store_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    set_result = await oms_client.set_active_store(
        callback_query.from_user,
        callback_query.message.chat if callback_query.message else None,
        store_id=store_id,
    )
    if not set_result.ok:
        if set_result.error_code == ERROR_UNAVAILABLE:
            await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
            return
        if set_result.error_code == ERROR_STORE_NOT_FOUND:
            await _edit_callback_message(callback_query, msg("errors.store_not_found"))
            await callback_query.answer()
            return
        if set_result.error_code == ERROR_NOT_LINKED:
            await _edit_callback_message(callback_query, msg("errors.not_linked"))
            await callback_query.answer()
            return
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    stores_result = await oms_client.list_stores(
        callback_query.from_user,
        callback_query.message.chat if callback_query.message else None,
    )
    if not stores_result.ok:
        await _edit_callback_message(callback_query, msg("stores.active_updated_generic"))
        await callback_query.answer()
        return

    current_store = stores_result.active_store
    if current_store is None and set_result.active_store_id is not None:
        current_store = _find_store(stores_result, set_result.active_store_id)
    callback_text = _join_parts(
        msg("stores.active_updated", store_name=_get_store_name(current_store)),
        _build_stores_text(stores_result),
    )
    reply_markup = build_store_switch_keyboard(stores_result.stores) if stores_result.has_multiple_stores else None
    await _edit_callback_message(callback_query, callback_text, reply_markup=reply_markup)
    await callback_query.answer()


@router.callback_query(F.data.startswith(DEVICE_SELECT_PREFIX))
async def device_select_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    active_store = await _require_active_store_for_callback(callback_query, session_state)
    if active_store is None:
        return

    device_id = parse_device_select_callback(callback_query.data)
    if device_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    set_result = await oms_client.set_active_device(
        callback_query.from_user,
        _callback_chat(callback_query),
        device_id=device_id,
    )
    if not set_result.ok:
        if set_result.error_code == ERROR_UNAVAILABLE:
            await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
            return
        await _edit_callback_message(
            callback_query,
            _build_error_text(set_result.error_code, store_name=active_store.name, device_name=device_id),
        )
        await callback_query.answer()
        return

    card_text = await _load_selected_device_card_text(
        oms_client,
        callback_query.from_user,
        _callback_chat(callback_query),
        session_state,
        device_id,
    )
    await _edit_callback_message(
        callback_query,
        card_text,
        reply_markup=build_selected_device_keyboard(device_id),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(DEVICE_STATUS_PREFIX))
async def device_status_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    device_id = parse_device_status_callback(callback_query.data)
    if device_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    if not await _require_selected_device_for_callback(callback_query, session_state, device_id):
        return

    status_result = await oms_client.get_device_status(
        callback_query.from_user,
        _callback_chat(callback_query),
        device_id=device_id,
    )
    if not status_result.ok:
        if status_result.error_code == ERROR_UNAVAILABLE:
            await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
            return
        await _edit_callback_message(
            callback_query,
            _build_error_text(status_result.error_code, device_name=device_id),
        )
        await callback_query.answer()
        return

    if status_result.status is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    await _edit_callback_message(
        callback_query,
        _build_device_status_text(status_result.status),
        reply_markup=build_selected_device_keyboard(device_id),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(DEVICE_LAST_PREFIX))
async def device_last_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    device_id = parse_device_last_callback(callback_query.data)
    if device_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    if not await _require_selected_device_for_callback(callback_query, session_state, device_id):
        return

    latest_result = await oms_client.get_device_latest_result(
        callback_query.from_user,
        _callback_chat(callback_query),
        device_id=device_id,
    )
    if not latest_result.ok:
        if latest_result.error_code == ERROR_UNAVAILABLE:
            await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
            return
        await _edit_callback_message(
            callback_query,
            _build_error_text(latest_result.error_code, device_name=device_id, result_scope="device"),
        )
        await callback_query.answer()
        return

    if latest_result.result is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    await _edit_callback_message(
        callback_query,
        _build_latest_result_text(latest_result.result),
        reply_markup=build_selected_device_keyboard(device_id),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(DEVICE_PHOTO_PREFIX))
async def device_photo_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    device_id = parse_device_photo_callback(callback_query.data)
    if device_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    if not await _require_selected_device_for_callback(callback_query, session_state, device_id):
        return

    card_text = await _load_selected_device_card_text(
        oms_client,
        callback_query.from_user,
        _callback_chat(callback_query),
        session_state,
        device_id,
        notice_text=msg("devices.photo_unavailable"),
    )
    await _edit_callback_message(
        callback_query,
        card_text,
        reply_markup=build_selected_device_keyboard(device_id),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(DEVICE_TARE_MENU_PREFIX))
async def device_tare_menu_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    device_id = parse_device_tare_menu_callback(callback_query.data)
    if device_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    if not await _require_selected_device_for_callback(callback_query, session_state, device_id):
        return

    card_text = await _load_selected_device_card_text(
        oms_client,
        callback_query.from_user,
        _callback_chat(callback_query),
        session_state,
        device_id,
    )
    await _edit_callback_message(
        callback_query,
        _join_parts(card_text, msg("tare.menu")),
        reply_markup=build_device_tare_keyboard(device_id),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(DEVICE_TARE_CONFIRM_PREFIX))
async def device_tare_confirm_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    device_id = parse_device_tare_confirm_callback(callback_query.data)
    if device_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    if not await _require_selected_device_for_callback(callback_query, session_state, device_id):
        return

    card_text = await _load_selected_device_card_text(
        oms_client,
        callback_query.from_user,
        _callback_chat(callback_query),
        session_state,
        device_id,
        notice_text=msg("tare.confirm_unavailable"),
    )
    await _edit_callback_message(
        callback_query,
        card_text,
        reply_markup=build_selected_device_keyboard(device_id),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(DEVICE_TARE_RESET_PREFIX))
async def device_tare_reset_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    device_id = parse_device_tare_reset_callback(callback_query.data)
    if device_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    if not await _require_selected_device_for_callback(callback_query, session_state, device_id):
        return

    card_text = await _load_selected_device_card_text(
        oms_client,
        callback_query.from_user,
        _callback_chat(callback_query),
        session_state,
        device_id,
        notice_text=msg("tare.reset_unavailable"),
    )
    await _edit_callback_message(
        callback_query,
        card_text,
        reply_markup=build_selected_device_keyboard(device_id),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(DEVICE_TARE_CANCEL_PREFIX))
async def device_tare_cancel_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    device_id = parse_device_tare_cancel_callback(callback_query.data)
    if device_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    if not await _require_selected_device_for_callback(callback_query, session_state, device_id):
        return

    card_text = await _load_selected_device_card_text(
        oms_client,
        callback_query.from_user,
        _callback_chat(callback_query),
        session_state,
        device_id,
        notice_text=msg("tare.cancelled"),
    )
    await _edit_callback_message(
        callback_query,
        card_text,
        reply_markup=build_selected_device_keyboard(device_id),
    )
    await callback_query.answer()


@router.callback_query(F.data == DEVICE_BACK)
async def device_back_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    active_store = await _require_active_store_for_callback(callback_query, session_state)
    if active_store is None:
        return

    devices_result = await oms_client.list_store_devices(
        callback_query.from_user,
        _callback_chat(callback_query),
        store_id=active_store.id,
    )
    if not devices_result.ok:
        if devices_result.error_code == ERROR_UNAVAILABLE:
            await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
            return
        await _edit_callback_message(
            callback_query,
            _build_error_text(devices_result.error_code, store_name=active_store.name),
        )
        await callback_query.answer()
        return

    if not devices_result.devices:
        await _edit_callback_message(callback_query, msg("devices.empty", store_name=active_store.name))
        await callback_query.answer()
        return

    await _edit_callback_message(
        callback_query,
        _build_devices_text(active_store),
        reply_markup=build_device_list_keyboard(devices_result.devices),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(UNLINK_PICK_PREFIX))
async def unlink_pick_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    store_id = parse_unlink_pick_callback(callback_query.data)
    if store_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    stores_result = await oms_client.list_stores(
        callback_query.from_user,
        callback_query.message.chat if callback_query.message else None,
    )
    if not stores_result.ok:
        if stores_result.error_code == ERROR_UNAVAILABLE:
            await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
            return
        await _edit_callback_message(callback_query, msg("unlink.no_memberships"))
        await callback_query.answer()
        return

    target_store = _find_store(stores_result, store_id)
    if target_store is None:
        await _edit_callback_message(callback_query, msg("errors.not_linked"))
        await callback_query.answer()
        return

    await _edit_callback_message(
        callback_query,
        msg("unlink.confirm", store_name=target_store.name),
        reply_markup=build_unlink_confirmation_keyboard(target_store.id),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith(UNLINK_CONFIRM_PREFIX))
async def unlink_confirm_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
    oms_client: OmsClient | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    oms_client = await _require_oms_client_for_callback(callback_query, oms_client)
    if oms_client is None:
        return

    store_id = parse_unlink_confirm_callback(callback_query.data)
    if store_id is None:
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    stores_result = await oms_client.list_stores(
        callback_query.from_user,
        callback_query.message.chat if callback_query.message else None,
    )
    if not stores_result.ok:
        if stores_result.error_code == ERROR_UNAVAILABLE:
            await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
            return
        await _edit_callback_message(callback_query, msg("unlink.no_memberships"))
        await callback_query.answer()
        return

    target_store = _find_store(stores_result, store_id)
    if target_store is None:
        await _edit_callback_message(callback_query, msg("errors.not_linked"))
        await callback_query.answer()
        return

    revoke_result = await oms_client.revoke_self_membership(
        callback_query.from_user,
        callback_query.message.chat if callback_query.message else None,
        store_id=store_id,
    )
    if not revoke_result.ok:
        if revoke_result.error_code == ERROR_UNAVAILABLE:
            await callback_query.answer(msg("errors.oms_unavailable"), show_alert=True)
            return
        if revoke_result.error_code == ERROR_STORE_NOT_FOUND:
            await _edit_callback_message(callback_query, msg("errors.store_not_found"))
            await callback_query.answer()
            return
        if revoke_result.error_code == ERROR_NOT_LINKED:
            await _edit_callback_message(callback_query, msg("errors.not_linked"))
            await callback_query.answer()
            return
        await callback_query.answer(msg("errors.generic"), show_alert=True)
        return

    refreshed_session = await oms_client.ensure_session(
        callback_query.from_user,
        callback_query.message.chat if callback_query.message else None,
    )
    result_text = msg("unlink.success", store_name=target_store.name)
    if not refreshed_session.degraded and not refreshed_session.is_banned:
        result_text = _join_parts(result_text, _build_start_text(refreshed_session))

    await _edit_callback_message(callback_query, result_text)
    await callback_query.answer()


@router.callback_query(F.data == UNLINK_CANCEL)
async def unlink_cancel_callback_handler(
    callback_query: CallbackQuery,
    session_state: EnsureSessionResult | None = None,
) -> None:
    if await _reply_blocked_callback(callback_query, session_state):
        return

    await _edit_callback_message(callback_query, msg("unlink.cancelled"))
    await callback_query.answer()


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
