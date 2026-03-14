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


def _parse_prefixed_data(data: str | None, prefix: str) -> str | None:
    if not data or not data.startswith(prefix):
        return None
    value = data[len(prefix) :].strip()
    return value or None
