from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import (
    build_device_back_callback,
    build_device_last_callback,
    build_device_photo_callback,
    build_device_select_callback,
    build_device_status_callback,
    build_device_tare_cancel_callback,
    build_device_tare_confirm_callback,
    build_device_tare_menu_callback,
    build_device_tare_reset_callback,
    UNLINK_CANCEL,
    build_store_switch_callback,
    build_unlink_confirm_callback,
    build_unlink_pick_callback,
)
from app.messages import msg
from app.oms import DeviceSummary, StoreSummary


def build_store_switch_keyboard(stores: Sequence[StoreSummary]) -> InlineKeyboardMarkup | None:
    if not stores:
        return None

    builder = InlineKeyboardBuilder()
    for store in stores:
        builder.button(text=store.name, callback_data=build_store_switch_callback(store.id))
    builder.adjust(1)
    return builder.as_markup()


def build_unlink_pick_keyboard(stores: Sequence[StoreSummary]) -> InlineKeyboardMarkup | None:
    if not stores:
        return None

    builder = InlineKeyboardBuilder()
    for store in stores:
        builder.button(text=store.name, callback_data=build_unlink_pick_callback(store.id))
    builder.adjust(1)
    return builder.as_markup()


def build_unlink_confirmation_keyboard(store_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=msg("buttons.confirm"), callback_data=build_unlink_confirm_callback(store_id))
    builder.button(text=msg("buttons.cancel"), callback_data=UNLINK_CANCEL)
    builder.adjust(2)
    return builder.as_markup()


def build_device_list_keyboard(devices: Sequence[DeviceSummary]) -> InlineKeyboardMarkup | None:
    if not devices:
        return None

    builder = InlineKeyboardBuilder()
    for device in devices:
        availability = msg("devices.online_short") if device.online else msg("devices.offline_short")
        builder.button(
            text=f"{device.display_name} • {availability}",
            callback_data=build_device_select_callback(device.id),
        )
    builder.adjust(1)
    return builder.as_markup()


def build_selected_device_keyboard(device_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=msg("buttons.status"), callback_data=build_device_status_callback(device_id))
    builder.button(text=msg("buttons.last_detection"), callback_data=build_device_last_callback(device_id))
    builder.button(text=msg("buttons.photo"), callback_data=build_device_photo_callback(device_id))
    builder.button(text=msg("buttons.tare"), callback_data=build_device_tare_menu_callback(device_id))
    builder.button(text=msg("buttons.back"), callback_data=build_device_back_callback())
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def build_device_tare_keyboard(device_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=msg("buttons.confirm_tare"), callback_data=build_device_tare_confirm_callback(device_id))
    builder.button(text=msg("buttons.reset_tare"), callback_data=build_device_tare_reset_callback(device_id))
    builder.button(text=msg("buttons.cancel"), callback_data=build_device_tare_cancel_callback(device_id))
    builder.adjust(2, 1)
    return builder.as_markup()
