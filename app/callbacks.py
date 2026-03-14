from __future__ import annotations

STORE_SWITCH_PREFIX = "store:switch:"
UNLINK_PICK_PREFIX = "unlink:pick:"
UNLINK_CONFIRM_PREFIX = "unlink:confirm:"
UNLINK_CANCEL = "unlink:cancel"
DEVICE_SELECT_PREFIX = "device:select:"
DEVICE_STATUS_PREFIX = "device:status:"
DEVICE_LAST_PREFIX = "device:last:"
DEVICE_PHOTO_PREFIX = "device:photo:"
DEVICE_TARE_MENU_PREFIX = "device:tare:menu:"
DEVICE_TARE_CONFIRM_PREFIX = "device:tare:confirm:"
DEVICE_TARE_RESET_PREFIX = "device:tare:reset:"
DEVICE_TARE_CANCEL_PREFIX = "device:tare:cancel:"
DEVICE_BACK = "device:back"
NOTIFICATION_IMAGE_PREFIX = "notification:image:"

# Telegram enforces a hard 64-byte limit on callback_data.
# Store IDs look like "st_ab0c4d3281984770b99e299be3960e5e" (35 chars), so every
# settings prefix that carries a store_id must stay ≤ 29 chars to fit in 64 bytes.
# Readable long names → short wire tokens:
#   s:n       = settings : notifications
#   s:n:st:   = settings : notifications : store        (open store settings view)
#   s:n:tm:   = settings : notifications : toggle master
#   s:n:td:   = settings : notifications : toggle device_status
#   s:n:tf:   = settings : notifications : toggle defect
#   s:n:bs    = settings : notifications : back  → settings menu
#   s:n:bp    = settings : notifications : back  → store picker
SETTINGS_NOTIFICATIONS_OPEN = "s:n"                           # 3 bytes
SETTINGS_NOTIFICATIONS_STORE_PREFIX = "s:n:st:"               # 7 bytes  + 35 store_id = 42
SETTINGS_NOTIFICATIONS_TOGGLE_MASTER_PREFIX = "s:n:tm:"       # 7 bytes  + 35 store_id = 42
SETTINGS_NOTIFICATIONS_TOGGLE_DEVICE_STATUS_PREFIX = "s:n:td:"  # 7 bytes  + 35 store_id = 42
SETTINGS_NOTIFICATIONS_TOGGLE_DEFECT_PREFIX = "s:n:tf:"       # 7 bytes  + 35 store_id = 42
SETTINGS_NOTIFICATIONS_BACK_TO_SETTINGS = "s:n:bs"            # 6 bytes  (no store_id)
SETTINGS_NOTIFICATIONS_BACK_TO_PICKER = "s:n:bp"              # 6 bytes  (no store_id)


def build_store_switch_callback(store_id: str) -> str:
    return f"{STORE_SWITCH_PREFIX}{store_id}"


def build_unlink_pick_callback(store_id: str) -> str:
    return f"{UNLINK_PICK_PREFIX}{store_id}"


def build_unlink_confirm_callback(store_id: str) -> str:
    return f"{UNLINK_CONFIRM_PREFIX}{store_id}"


def build_device_select_callback(device_id: str) -> str:
    return f"{DEVICE_SELECT_PREFIX}{device_id}"


def build_device_status_callback(device_id: str) -> str:
    return f"{DEVICE_STATUS_PREFIX}{device_id}"


def build_device_last_callback(device_id: str) -> str:
    return f"{DEVICE_LAST_PREFIX}{device_id}"


def build_device_photo_callback(device_id: str) -> str:
    return f"{DEVICE_PHOTO_PREFIX}{device_id}"


def build_device_tare_menu_callback(device_id: str) -> str:
    return f"{DEVICE_TARE_MENU_PREFIX}{device_id}"


def build_device_tare_confirm_callback(device_id: str) -> str:
    return f"{DEVICE_TARE_CONFIRM_PREFIX}{device_id}"


def build_device_tare_reset_callback(device_id: str) -> str:
    return f"{DEVICE_TARE_RESET_PREFIX}{device_id}"


def build_device_tare_cancel_callback(device_id: str) -> str:
    return f"{DEVICE_TARE_CANCEL_PREFIX}{device_id}"


def build_device_back_callback() -> str:
    return DEVICE_BACK


def build_notification_image_callback(result_id: str) -> str:
    return f"{NOTIFICATION_IMAGE_PREFIX}{result_id}"


def build_settings_notifications_open_callback() -> str:
    return SETTINGS_NOTIFICATIONS_OPEN


def build_settings_notifications_store_callback(store_id: str) -> str:
    return f"{SETTINGS_NOTIFICATIONS_STORE_PREFIX}{store_id}"


def build_settings_notifications_toggle_master_callback(store_id: str) -> str:
    return f"{SETTINGS_NOTIFICATIONS_TOGGLE_MASTER_PREFIX}{store_id}"


def build_settings_notifications_toggle_device_status_callback(store_id: str) -> str:
    return f"{SETTINGS_NOTIFICATIONS_TOGGLE_DEVICE_STATUS_PREFIX}{store_id}"


def build_settings_notifications_toggle_defect_callback(store_id: str) -> str:
    return f"{SETTINGS_NOTIFICATIONS_TOGGLE_DEFECT_PREFIX}{store_id}"


def build_settings_notifications_back_to_settings_callback() -> str:
    return SETTINGS_NOTIFICATIONS_BACK_TO_SETTINGS


def build_settings_notifications_back_to_picker_callback() -> str:
    return SETTINGS_NOTIFICATIONS_BACK_TO_PICKER


def parse_store_switch_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, STORE_SWITCH_PREFIX)


def parse_unlink_pick_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, UNLINK_PICK_PREFIX)


def parse_unlink_confirm_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, UNLINK_CONFIRM_PREFIX)


def parse_device_select_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, DEVICE_SELECT_PREFIX)


def parse_device_status_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, DEVICE_STATUS_PREFIX)


def parse_device_last_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, DEVICE_LAST_PREFIX)


def parse_device_photo_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, DEVICE_PHOTO_PREFIX)


def parse_device_tare_menu_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, DEVICE_TARE_MENU_PREFIX)


def parse_device_tare_confirm_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, DEVICE_TARE_CONFIRM_PREFIX)


def parse_device_tare_reset_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, DEVICE_TARE_RESET_PREFIX)


def parse_device_tare_cancel_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, DEVICE_TARE_CANCEL_PREFIX)


def parse_notification_image_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, NOTIFICATION_IMAGE_PREFIX)


def parse_settings_notifications_store_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, SETTINGS_NOTIFICATIONS_STORE_PREFIX)


def parse_settings_notifications_toggle_master_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, SETTINGS_NOTIFICATIONS_TOGGLE_MASTER_PREFIX)


def parse_settings_notifications_toggle_device_status_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, SETTINGS_NOTIFICATIONS_TOGGLE_DEVICE_STATUS_PREFIX)


def parse_settings_notifications_toggle_defect_callback(data: str | None) -> str | None:
    return _parse_prefixed_data(data, SETTINGS_NOTIFICATIONS_TOGGLE_DEFECT_PREFIX)


def _parse_prefixed_data(data: str | None, prefix: str) -> str | None:
    if not data or not data.startswith(prefix):
        return None
    value = data[len(prefix) :].strip()
    return value or None
