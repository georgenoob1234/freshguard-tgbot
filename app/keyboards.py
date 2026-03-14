from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import (
    build_device_back_callback,
    build_device_last_callback,
    build_notification_image_callback,
    build_settings_notifications_back_to_picker_callback,
    build_settings_notifications_back_to_settings_callback,
    build_settings_notifications_open_callback,
    build_settings_notifications_store_callback,
    build_settings_notifications_toggle_defect_callback,
    build_settings_notifications_toggle_device_status_callback,
    build_settings_notifications_toggle_master_callback,
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
from app.oms import (
    DeviceActionVisibility,
    DeviceSummary,
    NotificationSettingsStoreSummary,
    StoreNotificationSettings,
    StoreSummary,
)


def build_store_switch_keyboard(stores: Sequence[StoreSummary]) -> InlineKeyboardMarkup | None:
    if not stores:
        return None

    builder = InlineKeyboardBuilder()
    for store in stores:
        builder.button(text=store.name, callback_data=build_store_switch_callback(store.id))
    builder.adjust(1)
    return builder.as_markup()


def _on_off_label(value: bool) -> str:
    return msg("settings.state.on") if value else msg("settings.state.off")


def build_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=msg("buttons.notification_settings"),
        callback_data=build_settings_notifications_open_callback(),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_notification_settings_store_picker_keyboard(
    stores: Sequence[NotificationSettingsStoreSummary],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for store in stores:
        builder.button(text=store.store_name, callback_data=build_settings_notifications_store_callback(store.store_id))
    builder.button(
        text=msg("buttons.back"),
        callback_data=build_settings_notifications_back_to_settings_callback(),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_store_notification_settings_keyboard(settings: StoreNotificationSettings) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{msg('settings.notifications.all')}: {_on_off_label(settings.preferences.notifications_enabled)}",
        callback_data=build_settings_notifications_toggle_master_callback(settings.store_id),
    )
    if settings.preferences.notifications_enabled and settings.capabilities.can_subscribe_device_status:
        builder.button(
            text=f"{msg('settings.notifications.device_status')}: {_on_off_label(settings.preferences.device_status_enabled)}",
            callback_data=build_settings_notifications_toggle_device_status_callback(settings.store_id),
        )
    if settings.preferences.notifications_enabled and settings.capabilities.can_subscribe_defect_detected:
        builder.button(
            text=f"{msg('settings.notifications.defect_detected')}: {_on_off_label(settings.preferences.defect_detected_enabled)}",
            callback_data=build_settings_notifications_toggle_defect_callback(settings.store_id),
        )
    builder.button(
        text=msg("buttons.back"),
        callback_data=build_settings_notifications_back_to_picker_callback(),
    )
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


def build_selected_device_keyboard(
    device_id: str,
    actions: DeviceActionVisibility | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=msg("buttons.status"), callback_data=build_device_status_callback(device_id))
    builder.button(text=msg("buttons.last_detection"), callback_data=build_device_last_callback(device_id))

    show_photo = actions.show_photo if actions is not None else False
    show_tare = actions.show_tare if actions is not None else False
    if show_photo:
        builder.button(text=msg("buttons.photo"), callback_data=build_device_photo_callback(device_id))
    if show_tare:
        builder.button(text=msg("buttons.tare"), callback_data=build_device_tare_menu_callback(device_id))

    builder.button(text=msg("buttons.back"), callback_data=build_device_back_callback())
    if show_photo and show_tare:
        builder.adjust(2, 2, 1)
    elif show_photo or show_tare:
        builder.adjust(2, 1, 1)
    else:
        builder.adjust(2, 1)
    return builder.as_markup()


def build_device_tare_keyboard(
    device_id: str,
    actions: DeviceActionVisibility | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    show_tare_set = actions.show_tare_set if actions is not None else False
    show_tare_reset = actions.show_tare_reset if actions is not None else False
    action_count = 0
    if show_tare_set:
        builder.button(text=msg("buttons.confirm_tare"), callback_data=build_device_tare_confirm_callback(device_id))
        action_count += 1
    if show_tare_reset:
        builder.button(text=msg("buttons.reset_tare"), callback_data=build_device_tare_reset_callback(device_id))
        action_count += 1
    builder.button(text=msg("buttons.cancel"), callback_data=build_device_tare_cancel_callback(device_id))
    if action_count >= 2:
        builder.adjust(2, 1)
    elif action_count == 1:
        builder.adjust(1, 1)
    else:
        builder.adjust(1)
    return builder.as_markup()


def build_notification_image_keyboard(result_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=msg("buttons.show_image"), callback_data=build_notification_image_callback(result_id))
    builder.adjust(1)
    return builder.as_markup()
