from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.oms import (
    ERROR_DEVICE_NOT_IN_ACTIVE_STORE,
    ERROR_INVALID_CODE,
    ERROR_NO_ACTIVE_STORE,
    ERROR_NOT_LINKED,
    ERROR_PERMISSION_DENIED,
    ERROR_RESULT_NOT_FOUND,
    ERROR_STORE_INACTIVE,
    ERROR_STORE_HAS_NO_DEVICES,
    OmsClient,
)


class FakeResponse:
    def __init__(self, status: int, payload) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def json(self, content_type=None):
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, object]]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs):
        self.requests.append((method, url, kwargs))
        if not self._responses:
            raise AssertionError("No fake response configured")
        return self._responses.pop(0)

    async def close(self) -> None:
        self.closed = True


def _build_client(fake_session: FakeSession) -> OmsClient:
    return OmsClient(
        base_url="https://oms.example.com",
        bot_token="token",
        timeout_seconds=5,
        session=fake_session,
    )


def _dummy_user():
    return SimpleNamespace(id=100, username="tester", first_name="Test", last_name="User")


def _dummy_chat():
    return SimpleNamespace(id=200)


def test_ensure_session_extracts_flat_active_store_and_membership_count() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "user_id": "u1",
                    "is_banned": False,
                    "is_linked": True,
                    "memberships_count": 2,
                    "active_store_id": "s2",
                    "active_store_display_name": "Shop 2",
                    "active_device_id": "d7",
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.ensure_session(_dummy_user(), _dummy_chat()))

    assert result.ok is True
    assert result.degraded is False
    assert result.is_linked is True
    assert result.memberships_count == 2
    assert result.active_store is not None
    assert result.active_store.id == "s2"
    assert result.active_store.name == "Shop 2"
    assert result.active_device_id == "d7"
    method, _, kwargs = session.requests[0]
    assert method == "POST"
    assert kwargs["json"]["provider"] == "telegram"
    assert kwargs["json"]["provider_user_id"] == "100"
    assert kwargs["json"]["provider_chat_id"] == "200"
    assert "username" in kwargs["json"]
    assert "display_name" in kwargs["json"]


def test_list_stores_parses_items_and_active_store() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "items": [
                        {
                            "store_id": "s1",
                            "display_name": "Shop 1",
                            "role": "viewer",
                            "store_is_active": True,
                            "is_active_store": False,
                        },
                        {
                            "store_id": "s2",
                            "display_name": "Shop 2",
                            "role": "operator",
                            "store_is_active": False,
                            "is_active_store": True,
                        },
                    ]
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.list_stores(_dummy_user(), _dummy_chat()))

    assert result.ok is True
    assert [store.name for store in result.stores] == ["Shop 1", "Shop 2"]
    assert result.stores[0].role == "viewer"
    assert result.stores[1].store_is_active is False
    assert result.active_store is not None
    assert result.active_store.id == "s2"
    assert result.stores[1].is_active is True
    method, _, kwargs = session.requests[0]
    assert method == "GET"
    assert kwargs["params"] == {"provider": "telegram", "provider_user_id": "100"}


def test_redeem_invite_uses_invite_code_and_returns_already_linked() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "status": "linked",
                    "already_linked": True,
                    "store": {"store_id": "s1", "display_name": "Redeem Store"},
                    "role": "operator",
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.redeem_invite(_dummy_user(), _dummy_chat(), "123456"))

    assert result.ok is True
    assert result.already_linked is True
    assert result.active_store is not None
    assert result.active_store.id == "s1"
    assert result.active_store.name == "Redeem Store"
    assert result.role == "operator"
    method, _, kwargs = session.requests[0]
    assert method == "POST"
    assert kwargs["json"] == {
        "provider": "telegram",
        "provider_user_id": "100",
        "invite_code": "123456",
    }


def test_redeem_invite_maps_invite_not_found_to_invalid_code() -> None:
    session = FakeSession([FakeResponse(404, {"detail": "invite_not_found"})])
    client = _build_client(session)

    result = asyncio.run(client.redeem_invite(_dummy_user(), _dummy_chat(), "123456"))

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_CODE


def test_create_invite_maps_permission_denied_and_uses_minimal_actor_payload() -> None:
    session = FakeSession([FakeResponse(403, {"detail": "permission_denied"})])
    client = _build_client(session)

    result = asyncio.run(client.create_invite(_dummy_user(), _dummy_chat()))

    assert result.ok is False
    assert result.error_code == ERROR_PERMISSION_DENIED
    method, _, kwargs = session.requests[0]
    assert method == "POST"
    assert kwargs["json"] == {
        "provider": "telegram",
        "provider_user_id": "100",
        "role": "operator",
    }


def test_create_invite_maps_store_inactive_error() -> None:
    session = FakeSession([FakeResponse(400, {"detail": "store_inactive"})])
    client = _build_client(session)

    result = asyncio.run(client.create_invite(_dummy_user(), _dummy_chat()))

    assert result.ok is False
    assert result.error_code == ERROR_STORE_INACTIVE


def test_set_active_store_maps_membership_not_found_to_not_linked() -> None:
    session = FakeSession([FakeResponse(404, {"detail": "membership_not_found"})])
    client = _build_client(session)

    result = asyncio.run(client.set_active_store(_dummy_user(), _dummy_chat(), store_id="s2"))

    assert result.ok is False
    assert result.error_code == ERROR_NOT_LINKED


def test_list_store_devices_parses_items_and_online_flags() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "store_id": "s1",
                    "items": [
                        {"device_id": "d1", "display_name": "Scale A", "online": True},
                        {"device_id": "d2", "display_name": "Scale B", "online": False},
                    ],
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.list_store_devices(_dummy_user(), _dummy_chat(), store_id="s1"))

    assert result.ok is True
    assert result.store_id == "s1"
    assert [(device.id, device.display_name, device.online) for device in result.devices] == [
        ("d1", "Scale A", True),
        ("d2", "Scale B", False),
    ]
    method, _, kwargs = session.requests[0]
    assert method == "GET"
    assert kwargs["params"] == {"provider": "telegram", "provider_user_id": "100"}


def test_set_active_device_uses_device_id_payload() -> None:
    session = FakeSession([FakeResponse(200, {"active_store_id": "s1", "active_device_id": "d1"})])
    client = _build_client(session)

    result = asyncio.run(client.set_active_device(_dummy_user(), _dummy_chat(), device_id="d1"))

    assert result.ok is True
    assert result.active_store_id == "s1"
    assert result.active_device_id == "d1"
    method, _, kwargs = session.requests[0]
    assert method == "POST"
    assert kwargs["json"] == {
        "provider": "telegram",
        "provider_user_id": "100",
        "device_id": "d1",
    }


def test_set_active_device_maps_no_active_store() -> None:
    session = FakeSession([FakeResponse(400, {"detail": "no_active_store"})])
    client = _build_client(session)

    result = asyncio.run(client.set_active_device(_dummy_user(), _dummy_chat(), device_id="d1"))

    assert result.ok is False
    assert result.error_code == ERROR_NO_ACTIVE_STORE


def test_get_device_status_parses_status_payload() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "device_id": "d1",
                    "display_name": "Scale A",
                    "connected": True,
                    "last_seen_at": "2026-03-07T14:05:59Z",
                    "online": True,
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.get_device_status(_dummy_user(), _dummy_chat(), device_id="d1"))

    assert result.ok is True
    assert result.status is not None
    assert result.status.device_id == "d1"
    assert result.status.display_name == "Scale A"
    assert result.status.connected is True
    assert result.status.last_seen_at == "2026-03-07T14:05:59Z"
    assert result.status.online is True
    method, _, kwargs = session.requests[0]
    assert method == "GET"
    assert kwargs["params"] == {"provider": "telegram", "provider_user_id": "100"}


def test_get_device_status_maps_device_not_in_active_store() -> None:
    session = FakeSession([FakeResponse(404, {"detail": "device_not_in_active_store"})])
    client = _build_client(session)

    result = asyncio.run(client.get_device_status(_dummy_user(), _dummy_chat(), device_id="d1"))

    assert result.ok is False
    assert result.error_code == ERROR_DEVICE_NOT_IN_ACTIVE_STORE


def test_get_latest_result_parses_latest_detection_payload() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "device_id": "d1",
                    "device_display_name": "Scale A",
                    "image_id": "image-1",
                    "sent_at": "2026-03-07T14:04:59Z",
                    "received_at": "2026-03-07T14:05:59Z",
                    "weight_grams": 222.0,
                    "fruits": [
                        {"name": "apple", "weight_grams": 111.0},
                        {"name": "banana"},
                    ],
                    "defect": {"value": True, "type": "defect"},
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.get_latest_result(_dummy_user(), _dummy_chat()))

    assert result.ok is True
    assert result.result is not None
    assert result.result.device_id == "d1"
    assert result.result.device_display_name == "Scale A"
    assert result.result.image_id == "image-1"
    assert result.result.weight_grams == 222.0
    assert [(fruit.name, fruit.weight_grams) for fruit in result.result.fruits] == [
        ("apple", 111.0),
        ("banana", None),
    ]
    assert result.result.defect.value is True
    assert result.result.defect.type == "defect"


def test_get_device_latest_result_parses_defect_false_with_null_type() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "device_id": "d1",
                    "device_display_name": "Scale A",
                    "image_id": "image-1",
                    "sent_at": "2026-03-07T14:04:59Z",
                    "received_at": "2026-03-07T14:05:59Z",
                    "weight_grams": 222.0,
                    "fruits": [{"name": "banana", "weight_grams": 222.0}],
                    "defect": {"value": False, "type": None},
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.get_device_latest_result(_dummy_user(), _dummy_chat(), device_id="d1"))

    assert result.ok is True
    assert result.result is not None
    assert result.result.defect.value is False
    assert result.result.defect.type is None


def test_get_latest_result_defaults_missing_defect_to_false_and_none() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "device_id": "d1",
                    "device_display_name": "Scale A",
                    "image_id": "image-1",
                    "sent_at": "2026-03-07T14:04:59Z",
                    "received_at": "2026-03-07T14:05:59Z",
                    "weight_grams": 222.0,
                    "fruits": [{"name": "banana", "weight_grams": 222.0}],
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.get_latest_result(_dummy_user(), _dummy_chat()))

    assert result.ok is True
    assert result.result is not None
    assert result.result.defect.value is False
    assert result.result.defect.type is None


def test_get_latest_result_parses_fruit_class_as_name() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "device_id": "d1",
                    "device_display_name": "Scale A",
                    "image_id": "image-1",
                    "sent_at": "2026-03-07T14:04:59Z",
                    "received_at": "2026-03-07T14:05:59Z",
                    "weight_grams": 1000.0,
                    "fruits": [
                        {"fruit_class": "apple", "confidence": 0.52},
                        {"fruit_class": "banana"},
                    ],
                },
            )
        ]
    )
    client = _build_client(session)

    result = asyncio.run(client.get_latest_result(_dummy_user(), _dummy_chat()))

    assert result.ok is True
    assert result.result is not None
    assert [(fruit.name, fruit.weight_grams) for fruit in result.result.fruits] == [
        ("apple", None),
        ("banana", None),
    ]


def test_get_latest_result_maps_store_has_no_devices() -> None:
    session = FakeSession([FakeResponse(404, {"detail": "store_has_no_devices"})])
    client = _build_client(session)

    result = asyncio.run(client.get_latest_result(_dummy_user(), _dummy_chat()))

    assert result.ok is False
    assert result.error_code == ERROR_STORE_HAS_NO_DEVICES


def test_get_device_latest_result_maps_result_not_found() -> None:
    session = FakeSession([FakeResponse(404, {"detail": "result_not_found"})])
    client = _build_client(session)

    result = asyncio.run(client.get_device_latest_result(_dummy_user(), _dummy_chat(), device_id="d1"))

    assert result.ok is False
    assert result.error_code == ERROR_RESULT_NOT_FOUND
