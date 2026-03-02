# tgbot (Milestone 1)

Minimal Telegram adapter microservice based on `aiogram` with:
- DM-only behavior (group/supergroup/channel updates are ignored)
- OMS session ensure call for private message and callback updates
- Telegram command menu configured from `config/messages.ru.json`
- `/start`, `/help`, `/ping`
- environment-driven config
- JSON message catalog (`config/messages.ru.json`) for user-facing texts and command descriptions

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

Bot command menu entries are loaded from `bot_commands` in `config/messages.ru.json`.

## Tests

```bash
/opt/anaconda/bin/pytest
```

## Docker

```bash
docker build -t tgbot:milestone0 .
docker run --rm \
  -e TELEGRAM_BOT_TOKEN="123456:replace_with_real_token" \
  -e OMS_BASE_URL="https://oms.example.com" \
  -e OMS_BOT_TOKEN="replace_with_real_service_token" \
  tgbot:milestone1
```
