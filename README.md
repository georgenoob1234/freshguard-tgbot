# tgbot

Telegram adapter microservice based on `aiogram` with:
- DM-only behavior (group, supergroup, and channel updates are ignored)
- OMS session ensure call for private messages and callback updates
- Telegram command menu configured from `config/messages.ru.json`
- `/start`, `/help`, `/ping`, `/link`, `/stores`, `/devices`, `/last`, `/invite`, `/unlink`, `/settings`
- `/admin` command for admin UI entrypoint (Web App button when configured, browser login fallback otherwise)
- inline callback flows for store switching, device selection, selected-device actions, tare submenu, and unlink confirmation
- inline callback flow for per-store notification settings management
- internal notifications endpoint for OMS push batches: `POST /internal/notifications/push`
- internal Telegram WebApp verification endpoint for OMS: `POST /internal/admin-ui/verify-webapp-init`
- defect notifications with `Show image` callback that fetches image bytes from OMS and sends a new Telegram photo message
- browser admin login completion flow via Telegram deep-link `/start admin_login_<nonce>` and OMS `POST /bot/v1/admin-ui/login/claim` (bot disables link previews on the completion message to avoid prefetching single-use tokens)
- environment-driven config
- JSON message catalogs for user-facing texts and command descriptions

## Requirements

- Python 3.12+ (project rule: use Anaconda Python from `/opt/anaconda/bin/`)

## Configuration

Environment variables:
- `TELEGRAM_BOT_TOKEN` (required)
- `OMS_BASE_URL` (required, e.g. `https://oms.example.com`)
- `ADMIN_UI_WEBAPP_URL` (optional, HTTPS URL for Telegram Web App admin entrypoint)
- `OMS_BOT_TOKEN` (required, service-to-service bearer token)
- `HTTP_TIMEOUT_SECONDS` (optional, default `5`)
- `MESSAGES_PATH` (optional, default `config/messages.ru.json`)
- `LOG_LEVEL` (optional, default `INFO`)
- `INTERNAL_API_HOST` (optional, default `0.0.0.0`)
- `INTERNAL_API_PORT` (optional, default `8081`)
- `INTERNAL_NOTIFICATIONS_PUSH_PATH` (optional, default `/internal/notifications/push`)
- `INTERNAL_NOTIFICATIONS_AUTH_TOKEN` (optional, default empty/disabled)
- `TGBOT_INTERNAL_AUTH_TOKEN` (optional; shared secret for OMS -> tgbot WebApp verification endpoint; if unset, falls back to `INTERNAL_NOTIFICATIONS_AUTH_TOKEN`)
- `TGBOT_WEBAPP_VERIFY_ENDPOINT_PATH` (optional, default `/internal/admin-ui/verify-webapp-init`)
- `TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS` (optional, default `300`)

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
- `/admin`
- `/stores`
- `/devices`
- `/last`
- `/invite`
- `/unlink`
- `/settings`

Bot command menu entries are loaded from `bot_commands` in `config/messages.ru.json`.

## Bot flows

- `/start` renders linked or unlinked state using the OMS session summary.
- `/link <code>` redeems a six-digit invite code through OMS.
- `/stores` shows memberships and offers inline active-store switching.
- `/devices` lists devices for the active store and lets the user select an active device.
- selected-device callbacks expose `Status`, `Last detection`, `Photo`, `Tare`, and `Back`.
- `/last` shows the latest detection across any device in the active store.
- `Photo` and `Tare` callbacks submit OMS commands and render follow-up results.
- `/invite` creates an invite for the current active store.
- `/unlink` asks for explicit confirmation before revoking the selected store membership.
- `/settings` opens a generic settings screen with `Notification settings`.
- `Notification settings` always fetches fresh OMS store eligibility via `GET /bot/v1/notifications/settings/stores`.
- store selection loads per-store settings via `GET /bot/v1/notifications/settings/stores/{store_id}`.
- preference toggles use `PUT /bot/v1/notifications/settings/stores/{store_id}` and re-render from OMS response.
- when master notifications are off, subtype rows/buttons are hidden in bot UI (stored OMS subtype values are preserved and shown again when master is on).

## Internal Notifications (Milestone 6)

- OMS pushes batches to `POST /internal/notifications/push`.
- The bot accepts mixed `device_offline`, `device_online`, and `defect_detected` deliveries in one batch.
- Each delivery is processed independently and returned in the OMS format:
  - `status: sent` on success
  - `status: failed` with normalized `failure_reason` (`telegram_forbidden`, `telegram_chat_not_found`, `telegram_bad_request`, `transport_timeout`, `transport_error`, `internal_error`)
- `defect_detected` may include a `Show image` button (when `can_show_image=true`).
- On `Show image` callback, tgbot calls `GET /bot/v1/notifications/results/{result_id}/image` and sends the image as a new Telegram message.
- Optional internal endpoint auth:
  - set `INTERNAL_NOTIFICATIONS_AUTH_TOKEN`
  - send either `Authorization: Bearer <token>` or `X-Internal-Token: <token>`

## Internal WebApp verification

- OMS calls `POST /internal/admin-ui/verify-webapp-init` on tgbot internal API.
- Request body: `{"init_data":"<raw Telegram WebApp initData>"}`.
- Endpoint auth uses `TGBOT_INTERNAL_AUTH_TOKEN` (or `INTERNAL_NOTIFICATIONS_AUTH_TOKEN` fallback) with:
  - `Authorization: Bearer <token>` (preferred), or
  - `X-Internal-Token: <token>`
- tgbot validates the payload with `TELEGRAM_BOT_TOKEN`, enforces freshness via `TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS`, and returns:
  - success: `{"ok":true,"provider":"telegram","provider_user_id":"...","username":"...","display_name":"..."}`
  - failure: `{"ok":false,"reason":"invalid_telegram_init_data"}` or `{"ok":false,"reason":"stale_telegram_init_data"}`

## OMS contract notes

- `POST /bot/v1/session/ensure` is the source of truth for `is_banned`, `is_linked`, `memberships_count`, `active_store_id`, `active_store_display_name`, and `active_device_id`.
- Bot actor context for `session/ensure` includes `provider`, `provider_user_id`, `provider_chat_id`, and optional Telegram profile fields.
- Other bot endpoints use the OMS bot-actor DTOs with `provider` and `provider_user_id`, plus route-specific fields such as `invite_code` or `store_id`.
- `POST /bot/v1/invites/redeem` uses `invite_code` and may return `already_linked: true` in a successful response.
- `GET /bot/v1/stores` returns `items[]` with `display_name`, `store_is_active`, and `is_active_store`.
- `GET /bot/v1/notifications/settings/stores` returns OMS-eligible stores for per-store notification settings.
- `GET /bot/v1/notifications/settings/stores/{store_id}` returns per-store preferences and capabilities.
- `PUT /bot/v1/notifications/settings/stores/{store_id}` accepts partial preference updates and returns refreshed store settings.
- `GET /bot/v1/stores/{store_id}/devices` returns `items[]` with `device_id`, `display_name`, and `online`.
- `POST /bot/v1/context/active_device` sets the OMS-side active device for the current user context.
- `GET /bot/v1/devices/{device_id}/status` and `GET /bot/v1/devices/{device_id}/results/last` are active-store scoped.
- `GET /bot/v1/results/last` returns the latest detection across all devices in the active store.
- Bot-side error handling follows OMS `detail` strings such as `invite_not_found`, `invite_expired`, `invite_revoked`, `invite_exhausted`, `permission_denied`, `no_active_store`, `store_inactive`, `membership_not_found`, `device_not_in_active_store`, `store_has_no_devices`, `result_not_found`, `store_not_available`, `notifications_not_available`, and `notification_option_not_available`.

## Tests

```bash
/opt/anaconda/bin/pytest
```

## Docker

### Build

```bash
docker build -t tgbot:latest .
```

### Run (standalone)

```bash
docker run --rm \
  -e TELEGRAM_BOT_TOKEN="your-token" \
  -e OMS_BASE_URL="https://oms.example.com" \
  -e OMS_BOT_TOKEN="your-oms-token" \
  tgbot:latest
```

### Run with env file

```bash
cp .env.example .env
# Edit .env with real values
docker run --rm --env-file .env tgbot:latest
```

### Run with Docker Compose

```bash
cp .env.example .env
# Edit .env with real values
docker compose up -d
```

### OMS on host machine

If OMS runs on the host, use `host.docker.internal` for `OMS_BASE_URL`:

- **Linux**: `docker run --add-host=host.docker.internal:host-gateway ...`
- **Compose**: Uncomment `extra_hosts` in `docker-compose.yml`
