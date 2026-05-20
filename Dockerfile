FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MINIAPP_PORT=8080
ENV STATE_FILE=/app/data/bot_state.json

WORKDIR /app

COPY bot ./bot
COPY miniapp ./miniapp
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/data

EXPOSE 8080

CMD ["/app/docker-entrypoint.sh"]
