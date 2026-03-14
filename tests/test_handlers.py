from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app import messages as messages_module
from app.callbacks import (
    build_device_back_callback,
    build_device_last_callback,
    build_notification_image_callback,
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
from app.main import (
    device_back_callback_handler,
    device_last_callback_handler,
    device_photo_callback_handler,
    notification_image_callback_handler,
    device_select_callback_handler,
    device_status_callback_handler,
    device_tare_cancel_callback_handler,
    device_tare_confirm_callback_handler,
    device_tare_menu_callback_handler,
    devices_handler,
    help_handler,
    invite_handler,
    last_handler,
    link_handler,
    ping_handler,
    start_handler,
    store_switch_callback_handler,
    stores_handler,
    unlink_cancel_callback_handler,
    unlink_confirm_callback_handler,
    unlink_handler,
    unlink_pick_callback_handler,
)
from app.oms import (
    ERROR_DEVICE_NOT_IN_ACTIVE_STORE,
    ERROR_NO_ACTIVE_STORE,
    ERROR_NOTIFICATION_IMAGE_UNAVAILABLE,
    ERROR_NOT_LINKED,
    ERROR_PERMISSION_DENIED,
    ERROR_RESULT_NOT_FOUND,
    ERROR_STORE_INACTIVE,
    ERROR_UNAVAILABLE,
    CreateInviteResult,
    DeviceActionVisibility,
    DeviceStatusResult,
    DeviceStatusSummary,
    DeviceSummary,
    EnsureSessionResult,
    InviteSummary,
    DeviceCommandResponse,
    DeviceCommandSubmitResult,
    DeviceCommandStatusResult,
    CommandPhotoResult,
    LatestDefectSummary,
    LatestFruitSummary,
    LatestResultReadResult,
    LatestResultSummary,
    NotificationImageResult,
    RedeemInviteResult,
    RevokeMembershipResult,
    SetActiveDeviceResult,
    SetActiveStoreResult,
    StoreDevicesResult,
    StoreSummary,
    StoresResult,
)


class DummyMessage:
    def __init__(self, text: str = "/start", user_id: int = 100, chat_id: int = 200) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id, username="tester", first_name="Test", last_name="User")
        self.chat = SimpleNamespace(id=chat_id, type="private")
        self.answer = AsyncMock()


class DummyCallbackMessage:
    def __init__(self, chat_id: int = 200) -> None:
        self.chat = SimpleNamespace(id=chat_id, type="private")
        self.edit_text = AsyncMock()
        self.answer_photo = AsyncMock()


class DummyCallbackQuery:
    def __init__(self, data: str, user_id: int = 100, chat_id: int = 200) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id, username="tester", first_name="Test", last_name="User")
        self.message = DummyCallbackMessage(chat_id=chat_id)
        self.answer = AsyncMock()


class FakeOmsClient:
    def __init__(
        self,
        *,
        ensure_results: list[EnsureSessionResult] | None = None,
        list_stores_results: list[StoresResult] | None = None,
        store_devices_results: list[StoreDevicesResult] | None = None,
        redeem_results: list[RedeemInviteResult] | None = None,
        create_invite_results: list[CreateInviteResult] | None = None,
        set_active_results: list[SetActiveStoreResult] | None = None,
        set_active_device_results: list[SetActiveDeviceResult] | None = None,
        device_status_results: list[DeviceStatusResult] | None = None,
        latest_result_results: list[LatestResultReadResult] | None = None,
        device_latest_result_results: list[LatestResultReadResult] | None = None,
        revoke_results: list[RevokeMembershipResult] | None = None,
        command_submit_results: list[object] | None = None,
        command_status_results: list[object] | None = None,
        command_photo_results: list[object] | None = None,
        notification_image_results: list[object] | None = None,
    ) -> None:
        self.calls: list[tuple[str, object | None]] = []
        self._ensure_results = ensure_results or [EnsureSessionResult(ok=True, degraded=False, is_banned=False)]
        self._list_stores_results = list_stores_results or [StoresResult(ok=True)]
        self._store_devices_results = store_devices_results or [StoreDevicesResult(ok=True)]
        self._redeem_results = redeem_results or [RedeemInviteResult(ok=True)]
        self._create_invite_results = create_invite_results or [CreateInviteResult(ok=True)]
        self._set_active_results = set_active_results or [SetActiveStoreResult(ok=True)]
        self._set_active_device_results = set_active_device_results or [SetActiveDeviceResult(ok=True)]
        self._device_status_results = device_status_results or [DeviceStatusResult(ok=True)]
        self._latest_result_results = latest_result_results or [LatestResultReadResult(ok=True)]
        self._device_latest_result_results = device_latest_result_results or [LatestResultReadResult(ok=True)]
        self._revoke_results = revoke_results or [RevokeMembershipResult(ok=True)]
        self._command_submit_results = command_submit_results or []
        self._command_status_results = command_status_results or []
        self._command_photo_results = command_photo_results or []
        self._notification_image_results = notification_image_results or []

    def _next(self, queue: list[object]) -> object:
        if not queue:
            raise AssertionError("Missing fake OMS result")
        if len(queue) == 1:
            return queue[0]
        return queue.pop(0)

    async def ensure_session(self, from_user, chat) -> EnsureSessionResult:
        self.calls.append(("ensure_session", None))
        return self._next(self._ensure_results)

    async def list_stores(self, from_user, chat) -> StoresResult:
        self.calls.append(("list_stores", None))
        return self._next(self._list_stores_results)

    async def list_store_devices(self, from_user, chat, *, store_id: str) -> StoreDevicesResult:
        self.calls.append(("list_store_devices", store_id))
        return self._next(self._store_devices_results)

    async def redeem_invite(self, from_user, chat, code: str) -> RedeemInviteResult:
        self.calls.append(("redeem_invite", code))
        return self._next(self._redeem_results)

    async def create_invite(self, from_user, chat, *, role: str = "operator") -> CreateInviteResult:
        self.calls.append(("create_invite", role))
        return self._next(self._create_invite_results)

    async def set_active_store(self, from_user, chat, *, store_id: str) -> SetActiveStoreResult:
        self.calls.append(("set_active_store", store_id))
        return self._next(self._set_active_results)

    async def set_active_device(self, from_user, chat, *, device_id: str) -> SetActiveDeviceResult:
        self.calls.append(("set_active_device", device_id))
        return self._next(self._set_active_device_results)

    async def get_device_status(self, from_user, chat, *, device_id: str) -> DeviceStatusResult:
        self.calls.append(("get_device_status", device_id))
        return self._next(self._device_status_results)

    async def get_latest_result(self, from_user, chat) -> LatestResultReadResult:
        self.calls.append(("get_latest_result", None))
        return self._next(self._latest_result_results)

    async def get_device_latest_result(self, from_user, chat, *, device_id: str) -> LatestResultReadResult:
        self.calls.append(("get_device_latest_result", device_id))
        return self._next(self._device_latest_result_results)

    async def revoke_self_membership(self, from_user, chat, *, store_id: str) -> RevokeMembershipResult:
        self.calls.append(("revoke_self_membership", store_id))
        return self._next(self._revoke_results)

    async def submit_device_command(self, from_user, chat, *, device_id: str, request_type: str, params=None, wait_timeout_ms=None):
        self.calls.append(("submit_device_command", request_type))
        return self._next(self._command_submit_results)

    async def get_command_status(self, from_user, chat, *, command_id: str):
        self.calls.append(("get_command_status", command_id))
        return self._next(self._command_status_results)

    async def fetch_command_photo(self, from_user, chat, *, command_id: str):
        self.calls.append(("fetch_command_photo", command_id))
        return self._next(self._command_photo_results)

    async def fetch_notification_result_image(self, from_user, chat, *, result_id: str):
        self.calls.append(("fetch_notification_result_image", result_id))
        return self._next(self._notification_image_results)


def _write_catalog(path: str, payload: dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as target:
        json.dump(payload, target, ensure_ascii=False)


def _catalog_payload() -> dict[str, object]:
    return {
        "start.title": "FreshGuard",
        "start.unlinked": "START UNLINKED",
        "start.linked_single_store": "START SINGLE {store_name}",
        "start.linked_multi_store": "START MULTI {memberships_count} {store_name}",
        "help.body": "HELP",
        "ping.reply": "PONG",
        "link.usage_hint": "LINK USAGE",
        "link.invalid_code": "LINK INVALID FORMAT",
        "link.success": "LINK OK {store_name}",
        "link.already_linked": "LINK ALREADY",
        "link.invalid": "LINK INVALID",
        "link.expired": "LINK EXPIRED",
        "link.revoked": "LINK REVOKED",
        "link.exhausted": "LINK EXHAUSTED",
        "link.store_inactive": "LINK STORE INACTIVE",
        "stores.empty": "STORES EMPTY",
        "stores.single": "STORES SINGLE {store_name}",
        "stores.choose_active": "STORES CHOOSE {active_store_name} :: {stores_list}",
        "stores.active_updated": "STORE UPDATED {store_name}",
        "stores.active_updated_generic": "STORE UPDATED GENERIC",
        "invite.created": "INVITE OK {store_name} {code}",
        "invite.created_with_expiry": "INVITE OK EXP {store_name} {code} {expiry}",
        "invite.permission_denied": "INVITE DENIED",
        "invite.no_active_store": "INVITE NO ACTIVE",
        "invite.store_inactive": "INVITE STORE INACTIVE",
        "unlink.choose_store": "UNLINK CHOOSE",
        "unlink.confirm": "UNLINK CONFIRM {store_name}",
        "unlink.success": "UNLINK OK {store_name}",
        "unlink.cancelled": "UNLINK CANCEL",
        "unlink.no_memberships": "UNLINK EMPTY",
        "errors.generic": "GENERIC",
        "errors.oms_unavailable": "OMS DOWN",
        "errors.banned": "BANNED",
        "errors.permission_denied": "DENIED",
        "errors.no_active_store": "NO ACTIVE STORE",
        "errors.store_not_found": "STORE MISSING",
        "errors.not_linked": "NOT LINKED",
        "common.active_store_unknown": "UNKNOWN STORE",
        "common.not_available": "N/A",
        "common.yes": "YES",
        "common.no": "NO",
        "common.online": "ONLINE",
        "common.offline": "OFFLINE",
        "common.unknown": "UNKNOWN",
        "devices.choose": "DEVICES {store_name}",
        "devices.empty": "DEVICES EMPTY {store_name}",
        "devices.selected": "DEVICE SELECTED {device_name}",
        "devices.status_heading": "DEVICE STATUS {device_name}",
        "devices.no_active_device": "NO ACTIVE DEVICE",
        "devices.not_in_active_store": "DEVICE NOT IN STORE",
        "devices.photo_unavailable": "PHOTO UNAVAILABLE",
        "devices.online_short": "ON",
        "devices.offline_short": "OFF",
        "results.store_heading": "STORE LAST {store_name}",
        "results.device_heading": "DEVICE LAST {device_name}",
        "results.store_last_not_found": "STORE LAST EMPTY {store_name}",
        "results.device_last_not_found": "DEVICE LAST EMPTY {device_name}",
        "results.no_fruits": "NO FRUITS",
        "notifications.device_offline": "NOTIF OFFLINE {store_name} {device_name} {occurred_at}",
        "notifications.device_online": "NOTIF ONLINE {store_name} {device_name} {occurred_at}",
        "notifications.defect_detected": "NOTIF DEFECT {store_name} {device_name} {fruit_name} {defect_type} {occurred_at}",
        "notifications.image.caption": "NOTIF IMAGE CAPTION",
        "notifications.image.unavailable": "IMAGE UNAVAILABLE",
        "notifications.image.denied": "IMAGE DENIED",
        "notifications.image.failed": "IMAGE FAILED",
        "tare.menu": "TARE MENU",
        "tare.confirm_unavailable": "TARE CONFIRM UNAVAILABLE",
        "tare.reset_unavailable": "TARE RESET UNAVAILABLE",
        "tare.cancelled": "TARE CANCELLED",
        "commands.in_flight": "CMD IN FLIGHT",
        "commands.pending": "CMD PENDING",
        "commands.failed": "CMD FAILED",
        "commands.not_found": "CMD NOT FOUND",
        "commands.unsupported": "CMD UNSUPPORTED",
        "commands.connector_offline": "CMD OFFLINE",
        "commands.photo.requesting": "PHOTO REQUESTING",
        "commands.photo.success": "PHOTO SUCCESS",
        "commands.photo.ready": "PHOTO READY",
        "commands.photo.pending": "PHOTO PENDING",
        "commands.photo.not_found": "PHOTO NOT FOUND",
        "commands.tare.applying": "TARE APPLYING",
        "commands.tare.success": "TARE SUCCESS",
        "labels.store": "STORE",
        "labels.device": "DEVICE",
        "labels.online": "ONLINE",
        "labels.connected": "CONNECTED",
        "labels.last_seen": "LAST SEEN",
        "labels.received_at": "RECEIVED",
        "labels.sent_at": "SENT",
        "labels.weight_grams": "WEIGHT",
        "labels.image_id": "IMAGE",
        "labels.defect": "DEFECT",
        "labels.fruits": "FRUITS",
        "buttons.ok": "OK",
        "buttons.confirm": "YES",
        "buttons.cancel": "NO",
        "buttons.status": "STATUS",
        "buttons.last_detection": "LAST",
        "buttons.photo": "PHOTO",
        "buttons.show_image": "SHOW IMAGE",
        "buttons.tare": "TARE",
        "buttons.back": "BACK",
        "buttons.confirm_tare": "TARE YES",
        "buttons.reset_tare": "TARE RESET",
        "bot_commands": {
            "start": "start",
            "help": "help",
            "ping": "ping",
            "link": "link",
            "stores": "stores",
            "devices": "devices",
            "last": "last",
            "invite": "invite",
            "unlink": "unlink",
        },
    }


def _load_test_catalog(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "messages.json"
    _write_catalog(str(catalog_path), _catalog_payload())
    monkeypatch.setenv("MESSAGES_PATH", str(catalog_path))
    messages_module.clear_catalog_cache()


def test_start_handler_replies_with_unlinked_state(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage()
    asyncio.run(start_handler(message, session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False)))

    message.answer.assert_awaited_once_with("START UNLINKED")


def test_start_handler_replies_when_oms_unavailable(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage()
    asyncio.run(start_handler(message, session_state=EnsureSessionResult(ok=False, degraded=True, is_banned=False)))

    message.answer.assert_awaited_once_with("OMS DOWN")


def test_start_handler_replies_when_user_banned(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage()
    asyncio.run(start_handler(message, session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=True)))

    message.answer.assert_awaited_once_with("BANNED")


def test_help_handler_replies_from_catalog(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage()
    asyncio.run(help_handler(message))

    message.answer.assert_awaited_once_with("HELP")


def test_ping_handler_replies_from_catalog(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage()
    asyncio.run(ping_handler(message))

    message.answer.assert_awaited_once_with("PONG")


def test_link_handler_happy_path(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/link 123456")
    oms_client = FakeOmsClient(
        redeem_results=[RedeemInviteResult(ok=True, active_store=StoreSummary(id="s1", name="Shop 1"))],
        ensure_results=[
            EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            )
        ],
    )

    asyncio.run(
        link_handler(
            message,
            command=SimpleNamespace(args="123456"),
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("LINK OK Shop 1\n\nSTART SINGLE Shop 1")
    assert oms_client.calls == [("redeem_invite", "123456"), ("ensure_session", None)]


def test_link_handler_already_linked_path(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/link 123456")
    oms_client = FakeOmsClient(
        redeem_results=[RedeemInviteResult(ok=True, already_linked=True, active_store=StoreSummary(id="s1", name="Shop 1"))],
        ensure_results=[
            EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            )
        ],
    )

    asyncio.run(
        link_handler(
            message,
            command=SimpleNamespace(args="123456"),
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("LINK ALREADY\n\nSTART SINGLE Shop 1")


def test_link_handler_invalid_format(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/link 12ab")
    oms_client = FakeOmsClient()

    asyncio.run(
        link_handler(
            message,
            command=SimpleNamespace(args="12ab"),
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("LINK INVALID FORMAT")
    assert oms_client.calls == []


def test_link_handler_store_inactive_error(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/link 123456")
    oms_client = FakeOmsClient(
        redeem_results=[RedeemInviteResult(ok=False, error_code=ERROR_STORE_INACTIVE)]
    )

    asyncio.run(
        link_handler(
            message,
            command=SimpleNamespace(args="123456"),
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("LINK STORE INACTIVE")


def test_invite_handler_success_path(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/invite")
    oms_client = FakeOmsClient(
        create_invite_results=[
            CreateInviteResult(
                ok=True,
                invite=InviteSummary(code="654321", store_id="s1", expires_at=None),
            )
        ]
    )

    asyncio.run(
        invite_handler(
            message,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            ),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("INVITE OK Shop 1 654321")
    assert oms_client.calls == [("create_invite", "operator")]


def test_invite_handler_formats_expiry_timestamp(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/invite")
    oms_client = FakeOmsClient(
        create_invite_results=[
            CreateInviteResult(
                ok=True,
                invite=InviteSummary(code="654321", store_id="s1", expires_at="2026-03-07T14:05:59Z"),
            )
        ]
    )

    asyncio.run(
        invite_handler(
            message,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            ),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("INVITE OK EXP Shop 1 654321 07.03.2026, 17:05")


def test_invite_handler_permission_denied(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/invite")
    oms_client = FakeOmsClient(
        create_invite_results=[CreateInviteResult(ok=False, error_code=ERROR_PERMISSION_DENIED)]
    )

    asyncio.run(
        invite_handler(
            message,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("INVITE DENIED")


def test_invite_handler_store_inactive(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/invite")
    oms_client = FakeOmsClient(
        create_invite_results=[CreateInviteResult(ok=False, error_code=ERROR_STORE_INACTIVE)]
    )

    asyncio.run(
        invite_handler(
            message,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("INVITE STORE INACTIVE")


def test_unlink_handler_one_store_confirmation_flow(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/unlink")
    oms_client = FakeOmsClient(
        list_stores_results=[
            StoresResult(
                ok=True,
                stores=(StoreSummary(id="s1", name="Shop 1", is_active=True),),
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            )
        ]
    )

    asyncio.run(
        unlink_handler(
            message,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    assert message.answer.await_count == 1
    assert message.answer.await_args.args[0] == "UNLINK CONFIRM Shop 1"
    reply_markup = message.answer.await_args.kwargs["reply_markup"]
    callback_data = [button.callback_data for row in reply_markup.inline_keyboard for button in row]
    assert callback_data == [build_unlink_confirm_callback("s1"), UNLINK_CANCEL]


def test_unlink_multi_store_selection_and_confirmation_flow(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    initial_message = DummyMessage(text="/unlink")
    pick_client = FakeOmsClient(
        list_stores_results=[
            StoresResult(
                ok=True,
                stores=(
                    StoreSummary(id="s1", name="Shop 1", is_active=True),
                    StoreSummary(id="s2", name="Shop 2"),
                ),
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            )
        ]
    )

    asyncio.run(
        unlink_handler(
            initial_message,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=pick_client,
        )
    )

    assert initial_message.answer.await_args.args[0] == "UNLINK CHOOSE"
    picker_markup = initial_message.answer.await_args.kwargs["reply_markup"]
    picker_callbacks = [button.callback_data for row in picker_markup.inline_keyboard for button in row]
    assert picker_callbacks == [build_unlink_pick_callback("s1"), build_unlink_pick_callback("s2")]

    callback_query = DummyCallbackQuery(data=build_unlink_pick_callback("s2"))
    confirm_client = FakeOmsClient(
        list_stores_results=[
            StoresResult(
                ok=True,
                stores=(
                    StoreSummary(id="s1", name="Shop 1", is_active=True),
                    StoreSummary(id="s2", name="Shop 2"),
                ),
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            )
        ]
    )

    asyncio.run(
        unlink_pick_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=confirm_client,
        )
    )

    assert callback_query.message.edit_text.await_args.args[0] == "UNLINK CONFIRM Shop 2"
    confirm_markup = callback_query.message.edit_text.await_args.kwargs["reply_markup"]
    confirm_callbacks = [button.callback_data for row in confirm_markup.inline_keyboard for button in row]
    assert confirm_callbacks == [build_unlink_confirm_callback("s2"), UNLINK_CANCEL]
    callback_query.answer.assert_awaited_once_with()


def test_stores_switching_flow(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_store_switch_callback("s2"))
    oms_client = FakeOmsClient(
        set_active_results=[SetActiveStoreResult(ok=True, active_store_id="s2")],
        list_stores_results=[
            StoresResult(
                ok=True,
                stores=(
                    StoreSummary(id="s1", name="Shop 1"),
                    StoreSummary(id="s2", name="Shop 2", is_active=True),
                ),
                active_store=StoreSummary(id="s2", name="Shop 2", is_active=True),
            )
        ],
    )

    asyncio.run(
        store_switch_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    expected_text = "STORE UPDATED Shop 2\n\nSTORES CHOOSE Shop 2 :: - Shop 1\n- Shop 2"
    assert callback_query.message.edit_text.await_args.args[0] == expected_text
    markup = callback_query.message.edit_text.await_args.kwargs["reply_markup"]
    callback_data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert callback_data == [build_store_switch_callback("s1"), build_store_switch_callback("s2")]
    callback_query.answer.assert_awaited_once_with()


def test_store_switch_not_linked_error(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_store_switch_callback("s2"))
    oms_client = FakeOmsClient(
        set_active_results=[SetActiveStoreResult(ok=False, error_code=ERROR_NOT_LINKED)]
    )

    asyncio.run(
        store_switch_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    callback_query.message.edit_text.assert_awaited_once_with("NOT LINKED")
    callback_query.answer.assert_awaited_once_with()


def test_unlink_confirm_callback_refreshes_state(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_unlink_confirm_callback("s1"))
    oms_client = FakeOmsClient(
        list_stores_results=[
            StoresResult(
                ok=True,
                stores=(StoreSummary(id="s1", name="Shop 1", is_active=True),),
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            )
        ],
        revoke_results=[RevokeMembershipResult(ok=True)],
        ensure_results=[EnsureSessionResult(ok=True, degraded=False, is_banned=False, linked=False, memberships_count=0)],
    )

    asyncio.run(
        unlink_confirm_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    assert callback_query.message.edit_text.await_args.args[0] == "UNLINK OK Shop 1\n\nSTART UNLINKED"
    callback_query.answer.assert_awaited_once_with()


def test_unlink_cancel_callback_edits_message(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=UNLINK_CANCEL)

    asyncio.run(
        unlink_cancel_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
        )
    )

    callback_query.message.edit_text.assert_awaited_once_with("UNLINK CANCEL")
    callback_query.answer.assert_awaited_once_with()


def test_oms_unavailable_handling(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/stores")
    oms_client = FakeOmsClient(list_stores_results=[StoresResult(ok=False, error_code=ERROR_UNAVAILABLE)])

    asyncio.run(
        stores_handler(
            message,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("OMS DOWN")


def _device_status_result(
    *,
    device_id: str = "d1",
    display_name: str = "Scale A",
    connected: bool = False,
    last_seen_at: str | None = None,
    online: bool = True,
    actions: DeviceActionVisibility | None = None,
) -> DeviceStatusResult:
    actions = actions or DeviceActionVisibility(
        show_photo=True,
        show_tare=True,
        show_tare_set=True,
        show_tare_reset=True,
    )
    return DeviceStatusResult(
        ok=True,
        status=DeviceStatusSummary(
            device_id=device_id,
            display_name=display_name,
            connected=connected,
            last_seen_at=last_seen_at,
            online=online,
            actions=actions,
        ),
    )


def _latest_result(
    *,
    device_id: str = "d1",
    device_display_name: str = "Scale A",
    image_id: str = "image-1",
    sent_at: str | None = "2026-03-07T14:04:59Z",
    received_at: str | None = "2026-03-07T14:05:59Z",
    weight_grams: int | float | None = 222.0,
    fruits: tuple[LatestFruitSummary, ...] = (LatestFruitSummary(name="apple", weight_grams=111.0),),
    defect: LatestDefectSummary | None = None,
) -> LatestResultReadResult:
    return LatestResultReadResult(
        ok=True,
        result=LatestResultSummary(
            device_id=device_id,
            device_display_name=device_display_name,
            image_id=image_id,
            sent_at=sent_at,
            received_at=received_at,
            weight_grams=weight_grams,
            fruits=fruits,
            defect=defect or LatestDefectSummary(),
        ),
    )


def test_devices_handler_lists_active_store_devices(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/devices")
    oms_client = FakeOmsClient(
        store_devices_results=[
            StoreDevicesResult(
                ok=True,
                store_id="s1",
                devices=(
                    DeviceSummary(id="d1", display_name="Scale A", online=True),
                    DeviceSummary(id="d2", display_name="Scale B", online=False),
                ),
            )
        ]
    )

    asyncio.run(
        devices_handler(
            message,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            ),
            oms_client=oms_client,
        )
    )

    assert message.answer.await_args.args[0] == "DEVICES Shop 1"
    markup = message.answer.await_args.kwargs["reply_markup"]
    button_texts = [button.text for row in markup.inline_keyboard for button in row]
    callback_data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert button_texts == ["Scale A • ON", "Scale B • OFF"]
    assert callback_data == [build_device_select_callback("d1"), build_device_select_callback("d2")]
    assert oms_client.calls == [("list_store_devices", "s1")]


def test_devices_handler_requires_active_store(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/devices")
    oms_client = FakeOmsClient()

    asyncio.run(
        devices_handler(
            message,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False, linked=True, memberships_count=1),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("NO ACTIVE STORE")
    assert oms_client.calls == []


def test_device_selection_flow_renders_action_card(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_select_callback("d1"))
    oms_client = FakeOmsClient(
        set_active_device_results=[SetActiveDeviceResult(ok=True, active_store_id="s1", active_device_id="d1")],
        device_status_results=[
            _device_status_result(
                last_seen_at=None,
                actions=DeviceActionVisibility(
                    show_photo=True,
                    show_tare=True,
                    show_tare_set=True,
                    show_tare_reset=True,
                ),
            )
        ],
    )

    asyncio.run(
        device_select_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            ),
            oms_client=oms_client,
        )
    )

    expected_text = "DEVICE SELECTED Scale A\nSTORE: Shop 1\nONLINE: ONLINE\nCONNECTED: NO"
    assert callback_query.message.edit_text.await_args.args[0] == expected_text
    markup = callback_query.message.edit_text.await_args.kwargs["reply_markup"]
    callback_data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert callback_data == [
        build_device_status_callback("d1"),
        build_device_last_callback("d1"),
        build_device_photo_callback("d1"),
        build_device_tare_menu_callback("d1"),
        build_device_back_callback(),
    ]
    assert oms_client.calls == [("set_active_device", "d1"), ("get_device_status", "d1")]
    callback_query.answer.assert_awaited_once_with()


def test_last_handler_formats_store_wide_latest_result(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/last")
    oms_client = FakeOmsClient(
        latest_result_results=[
            _latest_result(defect=LatestDefectSummary(value=True, type="defect"))
        ]
    )

    asyncio.run(
        last_handler(
            message,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            ),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with(
        "STORE LAST Shop 1\n"
        "DEVICE: Scale A\n"
        "RECEIVED: 07.03.2026, 17:05\n"
        "SENT: 07.03.2026, 17:04\n"
        "WEIGHT: 222 g\n"
        "IMAGE: image-1\n"
        "DEFECT: YES (defect)\n"
        "FRUITS: apple (111 g)"
    )
    assert oms_client.calls == [("get_latest_result", None)]


def test_device_status_callback_renders_selected_device_status(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_status_callback("d1"))
    oms_client = FakeOmsClient(
        device_status_results=[
            _device_status_result(
                connected=True,
                last_seen_at="2026-03-07T14:05:59Z",
                online=True,
                actions=DeviceActionVisibility(
                    show_photo=True,
                    show_tare=True,
                    show_tare_set=True,
                    show_tare_reset=True,
                ),
            )
        ]
    )

    asyncio.run(
        device_status_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
                active_device_id="d1",
            ),
            oms_client=oms_client,
        )
    )

    assert callback_query.message.edit_text.await_args.args[0] == (
        "DEVICE STATUS Scale A\nCONNECTED: YES\nONLINE: ONLINE\nLAST SEEN: 07.03.2026, 17:05"
    )
    callback_query.answer.assert_awaited_once_with()


def test_device_last_callback_renders_latest_detection(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_last_callback("d1"))
    oms_client = FakeOmsClient(
        device_status_results=[_device_status_result(last_seen_at=None)],
        device_latest_result_results=[
            _latest_result(
                fruits=(LatestFruitSummary(name="banana", weight_grams=222.0),),
                defect=LatestDefectSummary(value=False, type=None),
            )
        ]
    )

    asyncio.run(
        device_last_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
                active_device_id="d1",
            ),
            oms_client=oms_client,
        )
    )

    assert callback_query.message.edit_text.await_args.args[0] == (
        "DEVICE LAST Scale A\n"
        "RECEIVED: 07.03.2026, 17:05\n"
        "SENT: 07.03.2026, 17:04\n"
        "WEIGHT: 222 g\n"
        "IMAGE: image-1\n"
        "DEFECT: NO\n"
        "FRUITS: banana (222 g)"
    )
    callback_query.answer.assert_awaited_once_with()
    assert oms_client.calls == [("get_device_latest_result", "d1"), ("get_device_status", "d1")]


def test_last_handler_renders_fruit_without_weight(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/last")
    oms_client = FakeOmsClient(
        latest_result_results=[
            _latest_result(
                fruits=(LatestFruitSummary(name="apple", weight_grams=None),),
                defect=LatestDefectSummary(value=False, type=None),
            )
        ]
    )

    asyncio.run(
        last_handler(
            message,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            ),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with(
        "STORE LAST Shop 1\n"
        "DEVICE: Scale A\n"
        "RECEIVED: 07.03.2026, 17:05\n"
        "SENT: 07.03.2026, 17:04\n"
        "WEIGHT: 222 g\n"
        "IMAGE: image-1\n"
        "DEFECT: NO\n"
        "FRUITS: apple"
    )


def test_last_handler_formats_missing_defect_as_no(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/last")
    oms_client = FakeOmsClient(latest_result_results=[_latest_result()])

    asyncio.run(
        last_handler(
            message,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            ),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with(
        "STORE LAST Shop 1\n"
        "DEVICE: Scale A\n"
        "RECEIVED: 07.03.2026, 17:05\n"
        "SENT: 07.03.2026, 17:04\n"
        "WEIGHT: 222 g\n"
        "IMAGE: image-1\n"
        "DEFECT: NO\n"
        "FRUITS: apple (111 g)"
    )


def test_tare_menu_open_and_cancel_flow(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    open_query = DummyCallbackQuery(data=build_device_tare_menu_callback("d1"))
    open_client = FakeOmsClient(
        device_status_results=[
            _device_status_result(
                last_seen_at=None,
                actions=DeviceActionVisibility(
                    show_photo=False,
                    show_tare=True,
                    show_tare_set=True,
                    show_tare_reset=True,
                ),
            )
        ]
    )

    asyncio.run(
        device_tare_menu_callback_handler(
            open_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True, role="operator"),
                active_device_id="d1",
            ),
            oms_client=open_client,
        )
    )

    assert open_query.message.edit_text.await_args.args[0] == (
        "DEVICE SELECTED Scale A\nSTORE: Shop 1\nONLINE: ONLINE\nCONNECTED: NO\n\nTARE MENU"
    )
    tare_markup = open_query.message.edit_text.await_args.kwargs["reply_markup"]
    tare_callbacks = [button.callback_data for row in tare_markup.inline_keyboard for button in row]
    assert tare_callbacks == [
        build_device_tare_confirm_callback("d1"),
        build_device_tare_reset_callback("d1"),
        build_device_tare_cancel_callback("d1"),
    ]
    open_query.answer.assert_awaited_once_with()

    cancel_query = DummyCallbackQuery(data=build_device_tare_cancel_callback("d1"))
    cancel_client = FakeOmsClient(device_status_results=[_device_status_result(last_seen_at=None)])

    asyncio.run(
        device_tare_cancel_callback_handler(
            cancel_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
                active_device_id="d1",
            ),
            oms_client=cancel_client,
        )
    )

    assert cancel_query.message.edit_text.await_args.args[0] == (
        "TARE CANCELLED\n\nDEVICE SELECTED Scale A\nSTORE: Shop 1\nONLINE: ONLINE\nCONNECTED: NO"
    )
    cancel_query.answer.assert_awaited_once_with()


def test_device_back_callback_returns_to_device_list(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_back_callback())
    oms_client = FakeOmsClient(
        store_devices_results=[
            StoreDevicesResult(
                ok=True,
                store_id="s1",
                devices=(DeviceSummary(id="d1", display_name="Scale A", online=True),),
            )
        ]
    )

    asyncio.run(
        device_back_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
                active_device_id="d1",
            ),
            oms_client=oms_client,
        )
    )

    assert callback_query.message.edit_text.await_args.args[0] == "DEVICES Shop 1"
    markup = callback_query.message.edit_text.await_args.kwargs["reply_markup"]
    callback_data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert callback_data == [build_device_select_callback("d1")]
    callback_query.answer.assert_awaited_once_with()


def test_last_handler_result_not_found_maps_to_catalog_message(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/last")
    oms_client = FakeOmsClient(
        latest_result_results=[LatestResultReadResult(ok=False, error_code=ERROR_RESULT_NOT_FOUND)]
    )

    asyncio.run(
        last_handler(
            message,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
            ),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("STORE LAST EMPTY Shop 1")


def test_device_status_callback_handles_device_not_in_active_store(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_status_callback("d1"))
    oms_client = FakeOmsClient(
        device_status_results=[DeviceStatusResult(ok=False, error_code=ERROR_DEVICE_NOT_IN_ACTIVE_STORE)]
    )

    asyncio.run(
        device_status_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
                active_device_id="d1",
            ),
            oms_client=oms_client,
        )
    )

    callback_query.message.edit_text.assert_awaited_once_with("DEVICE NOT IN STORE")
    callback_query.answer.assert_awaited_once_with()


def _command_response(
    *,
    command_id: str = "c1",
    device_id: str = "d1",
    store_id: str = "s1",
    request_type: str = "camera.capture",
    status: str = "succeeded",
    error_code: str | None = None,
) -> DeviceCommandResponse:
    return DeviceCommandResponse(
        command_id=command_id,
        device_id=device_id,
        store_id=store_id,
        request_type=request_type,
        status=status,
        result=None,
        error_code=error_code,
        created_at="2026-03-07T14:05:00Z",
        completed_at="2026-03-07T14:05:05Z",
    )


def test_photo_command_success_flow(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_photo_callback("d1"))
    oms_client = FakeOmsClient(
        device_status_results=[
            _device_status_result(
                last_seen_at=None,
                actions=DeviceActionVisibility(
                    show_photo=True,
                    show_tare=False,
                    show_tare_set=False,
                    show_tare_reset=False,
                ),
            )
        ],
        command_submit_results=[
            DeviceCommandSubmitResult(ok=True, command=_command_response())
        ],
        command_photo_results=[CommandPhotoResult(ok=True, payload=b"img", content_type="image/jpeg")],
    )

    asyncio.run(
        device_photo_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True, role="operator"),
                active_device_id="d1",
            ),
            oms_client=oms_client,
        )
    )

    assert callback_query.message.edit_text.await_args_list[0].args[0] == "PHOTO REQUESTING"
    assert callback_query.message.answer_photo.await_count == 1
    assert callback_query.message.answer_photo.await_args.kwargs["caption"] == "PHOTO READY"


def test_tare_command_pending_flow(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_tare_confirm_callback("d1"))
    oms_client = FakeOmsClient(
        device_status_results=[
            _device_status_result(
                last_seen_at=None,
                actions=DeviceActionVisibility(
                    show_photo=False,
                    show_tare=True,
                    show_tare_set=True,
                    show_tare_reset=False,
                ),
            )
        ],
        command_submit_results=[
            DeviceCommandSubmitResult(
                ok=True,
                command=_command_response(request_type="tare", status="running"),
            )
        ],
        command_status_results=[
            DeviceCommandStatusResult(
                ok=True,
                command=_command_response(request_type="tare", status="running"),
            )
        ],
    )

    asyncio.run(
        device_tare_confirm_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True, role="operator"),
                active_device_id="d1",
            ),
            oms_client=oms_client,
        )
    )

    assert callback_query.message.edit_text.await_args_list[0].args[0] == "TARE APPLYING"
    assert "CMD PENDING" in callback_query.message.edit_text.await_args_list[-1].args[0]


def test_photo_button_hidden_when_actions_false(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_select_callback("d1"))
    oms_client = FakeOmsClient(
        set_active_device_results=[SetActiveDeviceResult(ok=True, active_store_id="s1", active_device_id="d1")],
        device_status_results=[
            _device_status_result(
                last_seen_at=None,
                actions=DeviceActionVisibility(
                    show_photo=False,
                    show_tare=False,
                    show_tare_set=False,
                    show_tare_reset=False,
                ),
            )
        ],
    )

    asyncio.run(
        device_select_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True, role="viewer"),
                active_device_id="d1",
            ),
            oms_client=oms_client,
        )
    )

    markup = callback_query.message.edit_text.await_args.kwargs["reply_markup"]
    callback_data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert build_device_photo_callback("d1") not in callback_data
    assert build_device_tare_menu_callback("d1") not in callback_data


def test_device_last_callback_requires_selected_device_context(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_device_last_callback("d1"))
    oms_client = FakeOmsClient()

    asyncio.run(
        device_last_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(
                ok=True,
                degraded=False,
                is_banned=False,
                linked=True,
                memberships_count=1,
                active_store=StoreSummary(id="s1", name="Shop 1", is_active=True),
                active_device_id=None,
            ),
            oms_client=oms_client,
        )
    )

    callback_query.answer.assert_awaited_once_with("NO ACTIVE DEVICE", show_alert=True)
    assert oms_client.calls == []


def test_last_handler_no_active_store_message(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    message = DummyMessage(text="/last")
    oms_client = FakeOmsClient()

    asyncio.run(
        last_handler(
            message,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False, linked=True, memberships_count=1),
            oms_client=oms_client,
        )
    )

    message.answer.assert_awaited_once_with("NO ACTIVE STORE")
    assert oms_client.calls == []


def test_notification_image_callback_success_sends_new_photo(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_notification_image_callback("res-1"))
    oms_client = FakeOmsClient(
        notification_image_results=[
            NotificationImageResult(ok=True, payload=b"img", content_type="image/jpeg")
        ]
    )

    asyncio.run(
        notification_image_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    callback_query.message.answer_photo.assert_awaited_once()
    assert callback_query.message.answer_photo.await_args.kwargs["caption"] == "NOTIF IMAGE CAPTION"
    callback_query.answer.assert_awaited_once_with()
    assert oms_client.calls == [("fetch_notification_result_image", "res-1")]


def test_notification_image_callback_unavailable_shows_alert(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data=build_notification_image_callback("res-2"))
    oms_client = FakeOmsClient(
        notification_image_results=[
            NotificationImageResult(
                ok=False,
                error_code=ERROR_NOTIFICATION_IMAGE_UNAVAILABLE,
            )
        ]
    )

    asyncio.run(
        notification_image_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    callback_query.message.answer_photo.assert_not_awaited()
    callback_query.answer.assert_awaited_once_with("IMAGE UNAVAILABLE", show_alert=True)


def test_notification_image_callback_invalid_payload_is_safe(tmp_path, monkeypatch) -> None:
    _load_test_catalog(tmp_path, monkeypatch)

    callback_query = DummyCallbackQuery(data="notification:image:")
    oms_client = FakeOmsClient()

    asyncio.run(
        notification_image_callback_handler(
            callback_query,
            session_state=EnsureSessionResult(ok=True, degraded=False, is_banned=False),
            oms_client=oms_client,
        )
    )

    callback_query.message.answer_photo.assert_not_awaited()
    callback_query.answer.assert_awaited_once_with("IMAGE FAILED", show_alert=True)
    assert oms_client.calls == []
