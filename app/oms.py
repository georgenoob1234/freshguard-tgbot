from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from aiogram.types import Chat, User

LOGGER = logging.getLogger(__name__)

ERROR_ALREADY_LINKED = "already_linked"
ERROR_DEVICE_NOT_IN_ACTIVE_STORE = "device_not_in_active_store"
ERROR_EXHAUSTED = "exhausted"
ERROR_EXPIRED = "expired"
ERROR_INVALID_CODE = "invalid_code"
ERROR_NO_ACTIVE_STORE = "no_active_store"
ERROR_NOT_LINKED = "not_linked"
ERROR_PERMISSION_DENIED = "permission_denied"
ERROR_RESULT_NOT_FOUND = "result_not_found"
ERROR_REVOKED = "revoked"
ERROR_STORE_INACTIVE = "store_inactive"
ERROR_STORE_HAS_NO_DEVICES = "store_has_no_devices"
ERROR_STORE_NOT_FOUND = "store_not_found"
ERROR_UNAVAILABLE = "unavailable"
ERROR_UNKNOWN = "unknown"


@dataclass(frozen=True)
class StoreSummary:
    id: str
    name: str
    is_active: bool = False
    role: str | None = None
    store_is_active: bool = True


@dataclass(frozen=True)
class EnsureSessionResult:
    ok: bool
    degraded: bool
    is_banned: bool = False
    linked: bool | None = None
    memberships_count: int = 0
    active_store: StoreSummary | None = None
    active_device_id: str | None = None

    @property
    def is_linked(self) -> bool:
        if self.linked is not None:
            return self.linked
        return self.memberships_count > 0 or self.active_store is not None

    @property
    def has_multiple_stores(self) -> bool:
        return self.memberships_count > 1


@dataclass(frozen=True)
class StoresResult:
    ok: bool
    stores: tuple[StoreSummary, ...] = ()
    active_store: StoreSummary | None = None
    error_code: str | None = None

    @property
    def has_multiple_stores(self) -> bool:
        return len(self.stores) > 1


@dataclass(frozen=True)
class RedeemInviteResult:
    ok: bool
    error_code: str | None = None
    active_store: StoreSummary | None = None
    memberships_count: int = 0
    already_linked: bool = False
    role: str | None = None


@dataclass(frozen=True)
class InviteSummary:
    code: str
    store: StoreSummary | None = None
    store_id: str | None = None
    role: str | None = None
    expires_at: str | None = None
    max_uses: int | None = None


@dataclass(frozen=True)
class CreateInviteResult:
    ok: bool
    invite: InviteSummary | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class SetActiveStoreResult:
    ok: bool
    active_store_id: str | None = None
    active_device_id: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class RevokeMembershipResult:
    ok: bool
    revoked_store_id: str | None = None
    active_store_id: str | None = None
    active_device_id: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class DeviceSummary:
    id: str
    display_name: str
    online: bool = False


@dataclass(frozen=True)
class StoreDevicesResult:
    ok: bool
    store_id: str | None = None
    devices: tuple[DeviceSummary, ...] = ()
    error_code: str | None = None


@dataclass(frozen=True)
class SetActiveDeviceResult:
    ok: bool
    active_store_id: str | None = None
    active_device_id: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class DeviceStatusSummary:
    device_id: str
    display_name: str
    connected: bool = False
    last_seen_at: str | None = None
    online: bool = False


@dataclass(frozen=True)
class DeviceStatusResult:
    ok: bool
    status: DeviceStatusSummary | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class LatestFruitSummary:
    name: str | None = None
    weight_grams: int | float | None = None


@dataclass(frozen=True)
class LatestDefectSummary:
    value: bool = False
    type: str | None = None


@dataclass(frozen=True)
class LatestResultSummary:
    device_id: str
    device_display_name: str
    image_id: str | None = None
    sent_at: str | None = None
    received_at: str | None = None
    weight_grams: int | float | None = None
    fruits: tuple[LatestFruitSummary, ...] = ()
    defect: LatestDefectSummary = field(default_factory=LatestDefectSummary)


@dataclass(frozen=True)
class LatestResultReadResult:
    ok: bool
    result: LatestResultSummary | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class _RawOmsResponse:
    status: int
    payload: Any


def _build_display_name(user: User) -> str:
    parts = [getattr(user, "first_name", "") or "", getattr(user, "last_name", "") or ""]
    return " ".join(part for part in parts if part).strip()


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _bool_from_any(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _number_or_none(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            parsed = float(cleaned)
        except ValueError:
            return None
        if parsed.is_integer():
            return int(parsed)
        return parsed
    return None


def _parse_store_summary(raw_store: Any, *, fallback_active: bool | None = None) -> StoreSummary | None:
    store_data = _as_dict(raw_store)
    if not store_data:
        return None

    store_id = _string_or_none(store_data.get("id") or store_data.get("store_id"))
    if store_id is None:
        return None

    store_name = _string_or_none(
        store_data.get("name") or store_data.get("store_name") or store_data.get("display_name")
    ) or store_id
    if fallback_active is None:
        is_active = _bool_from_any(
            store_data.get("is_active_store")
            if "is_active_store" in store_data
            else store_data.get("is_active")
            or store_data.get("active")
            or store_data.get("is_current")
            or store_data.get("current"),
            default=False,
        )
    else:
        is_active = fallback_active

    store_is_active = _bool_from_any(store_data.get("store_is_active"), default=True)
    return StoreSummary(
        id=store_id,
        name=store_name,
        is_active=is_active,
        role=_string_or_none(store_data.get("role")),
        store_is_active=store_is_active,
    )


def _extract_error_tokens(payload: Any) -> list[str]:
    tokens: list[str] = []
    payload_dict = _as_dict(payload)
    if not payload_dict:
        return tokens

    nested_error = payload_dict.get("error")
    for key in ("error_code", "code", "reason", "detail", "message"):
        raw_value = payload_dict.get(key)
        if isinstance(raw_value, str):
            tokens.append(_normalize_token(raw_value))

    if isinstance(nested_error, str):
        tokens.append(_normalize_token(nested_error))
    elif isinstance(nested_error, dict):
        for key in ("error_code", "code", "reason", "detail", "message"):
            raw_value = nested_error.get(key)
            if isinstance(raw_value, str):
                tokens.append(_normalize_token(raw_value))

    return [token for token in tokens if token]


def _extract_memberships_count(payload: Any, stores: tuple[StoreSummary, ...] = ()) -> int:
    payload_dict = _as_dict(payload)
    for key in ("memberships_count", "membership_count", "stores_count", "store_count"):
        numeric_value = _int_or_none(payload_dict.get(key))
        if numeric_value is not None:
            return numeric_value
    return len(stores)


def _parse_store_list(payload: Any) -> tuple[StoreSummary, ...]:
    if isinstance(payload, list):
        raw_stores = payload
    else:
        payload_dict = _as_dict(payload)
        raw_stores = _as_list(payload_dict.get("items") or payload_dict.get("stores") or payload_dict.get("memberships"))

    stores: list[StoreSummary] = []
    for raw_item in raw_stores:
        item_dict = _as_dict(raw_item)
        if "store" in item_dict:
            store = _parse_store_summary(
                item_dict.get("store"),
                fallback_active=_bool_from_any(item_dict.get("is_active_store") or item_dict.get("is_active")),
            )
        else:
            store = _parse_store_summary(raw_item)
        if store is not None:
            stores.append(store)
    return tuple(stores)


def _extract_flat_active_store(payload: Any) -> StoreSummary | None:
    payload_dict = _as_dict(payload)
    store_id = _string_or_none(payload_dict.get("active_store_id"))
    if store_id is None:
        return None

    store_name = _string_or_none(payload_dict.get("active_store_display_name")) or store_id
    return StoreSummary(id=store_id, name=store_name, is_active=True)


def _extract_active_store(payload: Any, stores: tuple[StoreSummary, ...]) -> StoreSummary | None:
    payload_dict = _as_dict(payload)

    active_store = _extract_flat_active_store(payload_dict)
    if active_store is None:
        active_store = _parse_store_summary(payload_dict.get("active_store"), fallback_active=True)
    if active_store is None:
        active_store = _parse_store_summary(payload_dict.get("store"), fallback_active=True)

    if active_store is not None:
        for store in stores:
            if store.id == active_store.id:
                return StoreSummary(
                    id=store.id,
                    name=store.name,
                    is_active=True,
                    role=store.role,
                    store_is_active=store.store_is_active,
                )
        return active_store

    for store in stores:
        if store.is_active:
            return store

    if len(stores) == 1:
        store = stores[0]
        return StoreSummary(
            id=store.id,
            name=store.name,
            is_active=True,
            role=store.role,
            store_is_active=store.store_is_active,
        )

    return None


def _sync_active_store(
    stores: tuple[StoreSummary, ...],
    active_store: StoreSummary | None,
) -> tuple[tuple[StoreSummary, ...], StoreSummary | None]:
    if not stores:
        return stores, active_store

    if active_store is None and len(stores) == 1:
        store = stores[0]
        single_store = StoreSummary(
            id=store.id,
            name=store.name,
            is_active=True,
            role=store.role,
            store_is_active=store.store_is_active,
        )
        return (single_store,), single_store

    if active_store is None:
        return stores, None

    updated_stores: list[StoreSummary] = []
    matched_active_store: StoreSummary | None = None
    for store in stores:
        is_active = store.id == active_store.id
        updated_store = StoreSummary(
            id=store.id,
            name=store.name,
            is_active=is_active,
            role=store.role,
            store_is_active=store.store_is_active,
        )
        if is_active:
            matched_active_store = updated_store
        updated_stores.append(updated_store)

    return tuple(updated_stores), matched_active_store or active_store


def _parse_device_summary(raw_device: Any) -> DeviceSummary | None:
    device_data = _as_dict(raw_device)
    if not device_data:
        return None

    device_id = _string_or_none(device_data.get("device_id") or device_data.get("id"))
    if device_id is None:
        return None

    display_name = _string_or_none(
        device_data.get("display_name") or device_data.get("label") or device_data.get("hostname")
    ) or device_id
    return DeviceSummary(
        id=device_id,
        display_name=display_name,
        online=_bool_from_any(device_data.get("online"), default=False),
    )


def _parse_device_list(payload: Any) -> tuple[DeviceSummary, ...]:
    payload_dict = _as_dict(payload)
    raw_devices = _as_list(payload_dict.get("items") or payload_dict.get("devices"))
    devices: list[DeviceSummary] = []
    for raw_device in raw_devices:
        device = _parse_device_summary(raw_device)
        if device is not None:
            devices.append(device)
    return tuple(devices)


def _parse_device_status(payload: Any) -> DeviceStatusSummary | None:
    payload_dict = _as_dict(payload)
    if not payload_dict:
        return None

    device_id = _string_or_none(payload_dict.get("device_id") or payload_dict.get("id"))
    if device_id is None:
        return None

    display_name = _string_or_none(payload_dict.get("display_name")) or device_id
    return DeviceStatusSummary(
        device_id=device_id,
        display_name=display_name,
        connected=_bool_from_any(payload_dict.get("connected"), default=False),
        last_seen_at=_string_or_none(payload_dict.get("last_seen_at")),
        online=_bool_from_any(payload_dict.get("online"), default=False),
    )


def _parse_latest_fruit(raw_fruit: Any) -> LatestFruitSummary | None:
    fruit_data = _as_dict(raw_fruit)
    if not fruit_data:
        return None

    name = _string_or_none(
        fruit_data.get("name") or fruit_data.get("fruit_class") or fruit_data.get("fruit_class_name")
    )
    weight_grams = _number_or_none(fruit_data.get("weight_grams"))
    if name is None and weight_grams is None:
        return None
    return LatestFruitSummary(name=name, weight_grams=weight_grams)


def _parse_latest_defect(raw_defect: Any) -> LatestDefectSummary:
    defect_data = _as_dict(raw_defect)
    if not defect_data:
        return LatestDefectSummary()

    return LatestDefectSummary(
        value=_bool_from_any(defect_data.get("value"), default=False),
        type=_string_or_none(defect_data.get("type")),
    )


def _parse_latest_result(payload: Any) -> LatestResultSummary | None:
    payload_dict = _as_dict(payload)
    if not payload_dict:
        return None

    device_id = _string_or_none(payload_dict.get("device_id") or payload_dict.get("id"))
    if device_id is None:
        return None

    fruits: list[LatestFruitSummary] = []
    for raw_fruit in _as_list(payload_dict.get("fruits")):
        fruit = _parse_latest_fruit(raw_fruit)
        if fruit is not None:
            fruits.append(fruit)

    device_display_name = _string_or_none(
        payload_dict.get("device_display_name") or payload_dict.get("display_name")
    ) or device_id
    return LatestResultSummary(
        device_id=device_id,
        device_display_name=device_display_name,
        image_id=_string_or_none(payload_dict.get("image_id")),
        sent_at=_string_or_none(payload_dict.get("sent_at")),
        received_at=_string_or_none(payload_dict.get("received_at")),
        weight_grams=_number_or_none(payload_dict.get("weight_grams")),
        fruits=tuple(fruits),
        defect=_parse_latest_defect(payload_dict.get("defect")),
    )


class OmsClient:
    def __init__(
        self,
        base_url: str,
        bot_token: str,
        timeout_seconds: float,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base_url = f"{base_url.rstrip('/')}/bot/v1"
        self._headers = {"Authorization": f"Bearer {bot_token}"}
        self._owns_session = session is None
        if session is None:
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        else:
            self._session = session

    async def close(self) -> None:
        if self._owns_session and not getattr(self._session, "closed", False):
            await self._session.close()

    def _build_session_payload(self, from_user: User | None, chat: Chat | None) -> dict[str, Any] | None:
        user_id = getattr(from_user, "id", None)
        chat_id = getattr(chat, "id", None)
        if user_id is None or chat_id is None:
            LOGGER.warning("OMS session ensure skipped: missing user or chat")
            return None

        payload: dict[str, Any] = {
            "provider": "telegram",
            "provider_user_id": str(user_id),
            "provider_chat_id": str(chat_id),
        }

        username = _string_or_none(getattr(from_user, "username", None))
        if username:
            payload["username"] = username

        display_name = _build_display_name(from_user)
        if display_name:
            payload["display_name"] = display_name

        return payload

    def _build_bot_actor_payload(self, from_user: User | None) -> dict[str, Any] | None:
        user_id = getattr(from_user, "id", None)
        if user_id is None:
            LOGGER.warning("OMS request skipped: missing user")
            return None

        return {
            "provider": "telegram",
            "provider_user_id": str(user_id),
        }

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        user_id: str | int | None,
        chat_id: str | int | None,
        json_payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> _RawOmsResponse | None:
        endpoint = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method,
                endpoint,
                json=json_payload,
                params=params,
                headers=self._headers,
            ) as response:
                if response.status == 204:
                    return _RawOmsResponse(status=response.status, payload={})

                try:
                    response_payload = await response.json(content_type=None)
                except Exception as exc:  # pragma: no cover - defensive fallback
                    LOGGER.warning(
                        "OMS invalid JSON method=%s path=%s status=%s user_id=%s chat_id=%s error=%s",
                        method,
                        path,
                        response.status,
                        user_id,
                        chat_id,
                        exc,
                    )
                    response_payload = None

                return _RawOmsResponse(status=response.status, payload=response_payload)
        except asyncio.TimeoutError:
            LOGGER.warning("OMS timeout method=%s path=%s user_id=%s chat_id=%s", method, path, user_id, chat_id)
            return None
        except aiohttp.ClientError as exc:
            LOGGER.warning(
                "OMS request failed method=%s path=%s user_id=%s chat_id=%s error=%s",
                method,
                path,
                user_id,
                chat_id,
                exc,
            )
            return None

    def _map_redeem_error(self, status: int, payload: Any) -> str:
        tokens = set(_extract_error_tokens(payload))
        if status == 409 or {"already_linked", "invite_already_redeemed"} & tokens:
            return ERROR_ALREADY_LINKED
        if {"invite_not_found", "invalid_code", "invite_invalid", "invalid_invite", "code_invalid"} & tokens:
            return ERROR_INVALID_CODE
        if {"invite_expired", "expired", "code_expired"} & tokens:
            return ERROR_EXPIRED
        if {"invite_revoked", "revoked", "code_revoked"} & tokens:
            return ERROR_REVOKED
        if {"invite_exhausted", "exhausted", "usage_limit_reached", "uses_exhausted"} & tokens:
            return ERROR_EXHAUSTED
        if {"store_inactive"} & tokens:
            return ERROR_STORE_INACTIVE
        if status == 422:
            return ERROR_INVALID_CODE
        return ERROR_UNKNOWN

    def _map_invite_create_error(self, status: int, payload: Any) -> str:
        tokens = set(_extract_error_tokens(payload))
        if status == 403 or {"permission_denied", "forbidden"} & tokens:
            return ERROR_PERMISSION_DENIED
        if {"no_active_store", "active_store_required"} & tokens:
            return ERROR_NO_ACTIVE_STORE
        if {"membership_not_found", "membership_missing", "not_linked"} & tokens:
            return ERROR_NOT_LINKED
        if {"store_inactive"} & tokens:
            return ERROR_STORE_INACTIVE
        if {"store_not_found"} & tokens:
            return ERROR_STORE_NOT_FOUND
        return ERROR_UNKNOWN

    def _map_store_error(self, status: int, payload: Any) -> str:
        tokens = set(_extract_error_tokens(payload))
        if {"membership_not_found", "membership_missing", "not_linked"} & tokens:
            return ERROR_NOT_LINKED
        if {"store_not_found"} & tokens:
            return ERROR_STORE_NOT_FOUND
        if status == 403 or {"permission_denied", "forbidden"} & tokens:
            return ERROR_PERMISSION_DENIED
        if status == 404:
            return ERROR_NOT_LINKED
        return ERROR_UNKNOWN

    def _map_revoke_error(self, status: int, payload: Any) -> str:
        tokens = set(_extract_error_tokens(payload))
        if {"membership_not_found", "membership_missing", "not_linked"} & tokens:
            return ERROR_NOT_LINKED
        if {"store_not_found"} & tokens:
            return ERROR_STORE_NOT_FOUND
        if status == 404:
            return ERROR_NOT_LINKED
        return ERROR_UNKNOWN

    def _map_active_device_error(self, status: int, payload: Any) -> str:
        tokens = set(_extract_error_tokens(payload))
        if {"no_active_store", "active_store_required"} & tokens:
            return ERROR_NO_ACTIVE_STORE
        if {"device_not_in_active_store"} & tokens:
            return ERROR_DEVICE_NOT_IN_ACTIVE_STORE
        if {"membership_not_found", "membership_missing", "not_linked"} & tokens:
            return ERROR_NOT_LINKED
        if status == 403 or {"permission_denied", "forbidden"} & tokens:
            return ERROR_PERMISSION_DENIED
        if status == 404:
            return ERROR_DEVICE_NOT_IN_ACTIVE_STORE
        return ERROR_UNKNOWN

    def _map_store_last_error(self, status: int, payload: Any) -> str:
        tokens = set(_extract_error_tokens(payload))
        if {"no_active_store", "active_store_required"} & tokens:
            return ERROR_NO_ACTIVE_STORE
        if {"store_has_no_devices"} & tokens:
            return ERROR_STORE_HAS_NO_DEVICES
        if {"result_not_found"} & tokens:
            return ERROR_RESULT_NOT_FOUND
        if {"membership_not_found", "membership_missing", "not_linked"} & tokens:
            return ERROR_NOT_LINKED
        if status == 403 or {"permission_denied", "forbidden"} & tokens:
            return ERROR_PERMISSION_DENIED
        return ERROR_UNKNOWN

    def _map_device_result_error(self, status: int, payload: Any) -> str:
        tokens = set(_extract_error_tokens(payload))
        if {"result_not_found"} & tokens:
            return ERROR_RESULT_NOT_FOUND
        return self._map_active_device_error(status, payload)

    async def ensure_session(self, from_user: User | None, chat: Chat | None) -> EnsureSessionResult:
        payload = self._build_session_payload(from_user, chat)
        if payload is None:
            return EnsureSessionResult(ok=False, degraded=True, is_banned=False)

        raw_response = await self._request_json(
            "POST",
            "/session/ensure",
            user_id=payload.get("provider_user_id"),
            chat_id=payload.get("provider_chat_id"),
            json_payload=payload,
        )
        if raw_response is None or raw_response.status >= 500:
            return EnsureSessionResult(ok=False, degraded=True, is_banned=False)

        response_data = _as_dict(raw_response.payload)
        if raw_response.status >= 400 or not response_data:
            return EnsureSessionResult(ok=False, degraded=True, is_banned=False)

        return EnsureSessionResult(
            ok=True,
            degraded=False,
            is_banned=_bool_from_any(response_data.get("is_banned"), default=False),
            linked=_bool_from_any(response_data.get("is_linked"), default=False),
            memberships_count=_extract_memberships_count(response_data),
            active_store=_extract_active_store(response_data, ()),
            active_device_id=_string_or_none(response_data.get("active_device_id")),
        )

    async def list_stores(self, from_user: User | None, chat: Chat | None) -> StoresResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return StoresResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "GET",
            "/stores",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            params=payload,
        )
        if raw_response is None or raw_response.status >= 500:
            return StoresResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return StoresResult(ok=False, error_code=self._map_store_error(raw_response.status, raw_response.payload))

        stores = _parse_store_list(raw_response.payload)
        active_store = _extract_active_store(raw_response.payload, stores)
        stores, active_store = _sync_active_store(stores, active_store)
        return StoresResult(ok=True, stores=stores, active_store=active_store)

    async def list_store_devices(
        self,
        from_user: User | None,
        chat: Chat | None,
        *,
        store_id: str,
    ) -> StoreDevicesResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return StoreDevicesResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "GET",
            f"/stores/{store_id}/devices",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            params=payload,
        )
        if raw_response is None or raw_response.status >= 500:
            return StoreDevicesResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return StoreDevicesResult(ok=False, error_code=self._map_store_error(raw_response.status, raw_response.payload))

        response_data = _as_dict(raw_response.payload)
        return StoreDevicesResult(
            ok=True,
            store_id=_string_or_none(response_data.get("store_id")) or store_id,
            devices=_parse_device_list(response_data),
        )

    async def redeem_invite(self, from_user: User | None, chat: Chat | None, code: str) -> RedeemInviteResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return RedeemInviteResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "POST",
            "/invites/redeem",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            json_payload={**payload, "invite_code": code},
        )
        if raw_response is None or raw_response.status >= 500:
            return RedeemInviteResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return RedeemInviteResult(ok=False, error_code=self._map_redeem_error(raw_response.status, raw_response.payload))

        response_data = _as_dict(raw_response.payload)
        active_store = _parse_store_summary(response_data.get("store"), fallback_active=True)
        return RedeemInviteResult(
            ok=True,
            active_store=active_store,
            already_linked=_bool_from_any(response_data.get("already_linked"), default=False),
            role=_string_or_none(response_data.get("role")),
        )

    async def create_invite(
        self,
        from_user: User | None,
        chat: Chat | None,
        *,
        role: str = "operator",
    ) -> CreateInviteResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return CreateInviteResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "POST",
            "/invites/create",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            json_payload={**payload, "role": role},
        )
        if raw_response is None or raw_response.status >= 500:
            return CreateInviteResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return CreateInviteResult(ok=False, error_code=self._map_invite_create_error(raw_response.status, raw_response.payload))

        response_data = _as_dict(raw_response.payload)
        code = _string_or_none(response_data.get("invite_code"))
        if code is None:
            return CreateInviteResult(ok=False, error_code=ERROR_UNKNOWN)

        invite = InviteSummary(
            code=code,
            store_id=_string_or_none(response_data.get("store_id")),
            role=_string_or_none(response_data.get("role")),
            expires_at=_string_or_none(response_data.get("expires_at")),
            max_uses=_int_or_none(response_data.get("max_uses")),
        )
        return CreateInviteResult(ok=True, invite=invite)

    async def set_active_store(
        self,
        from_user: User | None,
        chat: Chat | None,
        *,
        store_id: str,
    ) -> SetActiveStoreResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return SetActiveStoreResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "POST",
            "/context/active_store",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            json_payload={**payload, "store_id": store_id},
        )
        if raw_response is None or raw_response.status >= 500:
            return SetActiveStoreResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return SetActiveStoreResult(ok=False, error_code=self._map_store_error(raw_response.status, raw_response.payload))

        response_data = _as_dict(raw_response.payload)
        return SetActiveStoreResult(
            ok=True,
            active_store_id=_string_or_none(response_data.get("active_store_id")),
            active_device_id=_string_or_none(response_data.get("active_device_id")),
        )

    async def set_active_device(
        self,
        from_user: User | None,
        chat: Chat | None,
        *,
        device_id: str,
    ) -> SetActiveDeviceResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return SetActiveDeviceResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "POST",
            "/context/active_device",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            json_payload={**payload, "device_id": device_id},
        )
        if raw_response is None or raw_response.status >= 500:
            return SetActiveDeviceResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return SetActiveDeviceResult(
                ok=False,
                error_code=self._map_active_device_error(raw_response.status, raw_response.payload),
            )

        response_data = _as_dict(raw_response.payload)
        return SetActiveDeviceResult(
            ok=True,
            active_store_id=_string_or_none(response_data.get("active_store_id")),
            active_device_id=_string_or_none(response_data.get("active_device_id")),
        )

    async def get_device_status(
        self,
        from_user: User | None,
        chat: Chat | None,
        *,
        device_id: str,
    ) -> DeviceStatusResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return DeviceStatusResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "GET",
            f"/devices/{device_id}/status",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            params=payload,
        )
        if raw_response is None or raw_response.status >= 500:
            return DeviceStatusResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return DeviceStatusResult(
                ok=False,
                error_code=self._map_active_device_error(raw_response.status, raw_response.payload),
            )

        status_summary = _parse_device_status(raw_response.payload)
        if status_summary is None:
            return DeviceStatusResult(ok=False, error_code=ERROR_UNKNOWN)
        return DeviceStatusResult(ok=True, status=status_summary)

    async def get_latest_result(self, from_user: User | None, chat: Chat | None) -> LatestResultReadResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return LatestResultReadResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "GET",
            "/results/last",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            params=payload,
        )
        if raw_response is None or raw_response.status >= 500:
            return LatestResultReadResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return LatestResultReadResult(
                ok=False,
                error_code=self._map_store_last_error(raw_response.status, raw_response.payload),
            )

        latest_result = _parse_latest_result(raw_response.payload)
        if latest_result is None:
            return LatestResultReadResult(ok=False, error_code=ERROR_UNKNOWN)
        return LatestResultReadResult(ok=True, result=latest_result)

    async def get_device_latest_result(
        self,
        from_user: User | None,
        chat: Chat | None,
        *,
        device_id: str,
    ) -> LatestResultReadResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return LatestResultReadResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "GET",
            f"/devices/{device_id}/results/last",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            params=payload,
        )
        if raw_response is None or raw_response.status >= 500:
            return LatestResultReadResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return LatestResultReadResult(
                ok=False,
                error_code=self._map_device_result_error(raw_response.status, raw_response.payload),
            )

        latest_result = _parse_latest_result(raw_response.payload)
        if latest_result is None:
            return LatestResultReadResult(ok=False, error_code=ERROR_UNKNOWN)
        return LatestResultReadResult(ok=True, result=latest_result)

    async def revoke_self_membership(
        self,
        from_user: User | None,
        chat: Chat | None,
        *,
        store_id: str,
    ) -> RevokeMembershipResult:
        payload = self._build_bot_actor_payload(from_user)
        if payload is None:
            return RevokeMembershipResult(ok=False, error_code=ERROR_UNAVAILABLE)

        raw_response = await self._request_json(
            "POST",
            "/memberships/revoke_self",
            user_id=payload.get("provider_user_id"),
            chat_id=getattr(chat, "id", None),
            json_payload={**payload, "store_id": store_id},
        )
        if raw_response is None or raw_response.status >= 500:
            return RevokeMembershipResult(ok=False, error_code=ERROR_UNAVAILABLE)

        if raw_response.status >= 400:
            return RevokeMembershipResult(ok=False, error_code=self._map_revoke_error(raw_response.status, raw_response.payload))

        response_data = _as_dict(raw_response.payload)
        return RevokeMembershipResult(
            ok=True,
            revoked_store_id=_string_or_none(response_data.get("revoked_store_id")),
            active_store_id=_string_or_none(response_data.get("active_store_id")),
            active_device_id=_string_or_none(response_data.get("active_device_id")),
        )
