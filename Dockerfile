# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app ./app
COPY config ./config

# Non-root user
RUN adduser --disabled-password --gecos "" tgbot && chown -R tgbot:tgbot /app
USER tgbot

CMD ["python", "-m", "app.main"]
