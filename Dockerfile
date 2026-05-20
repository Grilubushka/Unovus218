FROM node:20-alpine AS miniapp-builder

WORKDIR /app/miniapp

COPY miniapp/package.json miniapp/package-lock.json miniapp/vite.config.js ./
COPY miniapp/index.html ./index.html
COPY miniapp/src ./src

RUN npm ci && npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MINIAPP_PORT=8080
ENV STATE_FILE=/app/data/bot_state.json

WORKDIR /app

COPY bot ./bot
COPY --from=miniapp-builder /app/miniapp/dist ./miniapp
COPY bot.sqlite3 ./seed/bot.sqlite3
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/data /app/seed

EXPOSE 8080

CMD ["/app/docker-entrypoint.sh"]
