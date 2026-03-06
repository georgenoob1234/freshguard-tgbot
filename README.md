# tgbot (Milestone 3)

Telegram adapter microservice based on `aiogram` with:
- DM-only behavior (group, supergroup, and channel updates are ignored)
- OMS session ensure call for private messages and callback updates
- Telegram command menu configured from `config/messages.ru.json`
- `/start`, `/help`, `/ping`, `/link`, `/stores`, `/devices`, `/last`, `/invite`, `/unlink`
- inline callback flows for store switching, device selection, selected-device actions, tare submenu, and unlink confirmation
- environment-driven config
- JSON message catalogs for user-facing texts and command descriptions

## Requirements

- Python 3.12+ (project rule: use Anaconda Python from `/opt/anaconda/bin/`)

## Configuration

Environment variables:
- `TELEGRAM_BOT_TOKEN` (required)
- `OMS_BASE_URL` (required, e.g. `https://oms.example.com`)
- `OMS_BOT_TOKEN` (required, service-to-service bearer token)
- `HTTP_TIMEOUT_SECONDS` (optional, default `5`)
- `MESSAGES_PATH` (optional, default `config/messages.ru.json`)
- `LOG_LEVEL` (optional, default `INFO`)

## Run locally

```bash
/opt/anaconda/bin/pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="123456:replace_with_real_token"
export OMS_BASE_URL="https://oms.example.com"
export OMS_BOT_TOKEN="replace_with_real_service_token"
/opt/anaconda/bin/python -m app.main
```

After startup, the bot responds to:
- `/start`
- `/help`
- `/ping`
- `/link <code>`
- `/stores`
- `/devices`
- `/last`
- `/invite`
- `/unlink`

Bot command menu entries are loaded from `bot_commands` in `config/messages.ru.json`.

## Bot flows

- `/start` renders linked or unlinked state using the OMS session summary.
- `/link <code>` redeems a six-digit invite code through OMS.
- `/stores` shows memberships and offers inline active-store switching.
- `/devices` lists devices for the active store and lets the user select an active device.
- selected-device callbacks expose `Status`, `Last detection`, `Photo`, `Tare`, and `Back`.
- `/last` shows the latest detection across any device in the active store.
- `Photo` and `Tare` currently keep the Milestone 3 UX but answer with placeholder messages because OMS does not expose bot-side execution endpoints for those actions yet.
- `/invite` creates an invite for the current active store.
- `/unlink` asks for explicit confirmation before revoking the selected store membership.

## OMS contract notes

- `POST /bot/v1/session/ensure` is the source of truth for `is_banned`, `is_linked`, `memberships_count`, `active_store_id`, `active_store_display_name`, and `active_device_id`.
- Bot actor context for `session/ensure` includes `provider`, `provider_user_id`, `provider_chat_id`, and optional Telegram profile fields.
- Other bot endpoints use the OMS bot-actor DTOs with `provider` and `provider_user_id`, plus route-specific fields such as `invite_code` or `store_id`.
- `POST /bot/v1/invites/redeem` uses `invite_code` and may return `already_linked: true` in a successful response.
- `GET /bot/v1/stores` returns `items[]` with `display_name`, `store_is_active`, and `is_active_store`.
- `GET /bot/v1/stores/{store_id}/devices` returns `items[]` with `device_id`, `display_name`, and `online`.
- `POST /bot/v1/context/active_device` sets the OMS-side active device for the current user context.
- `GET /bot/v1/devices/{device_id}/status` and `GET /bot/v1/devices/{device_id}/results/last` are active-store scoped.
- `GET /bot/v1/results/last` returns the latest detection across all devices in the active store.
- Bot-side error handling follows OMS `detail` strings such as `invite_not_found`, `invite_expired`, `invite_revoked`, `invite_exhausted`, `permission_denied`, `no_active_store`, `store_inactive`, `membership_not_found`, `device_not_in_active_store`, `store_has_no_devices`, and `result_not_found`.

## Tests

```bash
/opt/anaconda/bin/pytest
```

## Docker

```bash
docker build -t tgbot:milestone2 .
docker run --rm \
  -e TELEGRAM_BOT_TOKEN="123456:replace_with_real_token" \
  -e OMS_BASE_URL="https://oms.example.com" \
  -e OMS_BOT_TOKEN="replace_with_real_service_token" \
  tgbot:milestone2
```
