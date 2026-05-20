# Unovus 218: Telegram Bot + Mini App

Прототип Telegram-бота и Telegram Mini App для построения персональных образовательных маршрутов. Версия работает без подключенного ИИ: профиль собирается в чате, маршрут строится детерминированным алгоритмом из мокового каталога бесплатных русскоязычных материалов, прогресс и обратная связь сохраняются в SQLite.

## Что уже умеет

- Бот собирает профиль пользователя через диалог.
- Все данные чата пишутся в SQLite: состояние диалога, сообщения, callback-кнопки, ответы анкеты.
- После онбординга создается `course_session` с персональным маршрутом.
- Mini App читает маршрут из БД через API и показывает интерактивную карту.
- Темы маршрута кликабельны, материалы открываются по ссылкам.
- Пользователь может отметить модуль пройденным.
- Обратная связь `сложно / просто / заменить` перестраивает маршрут без ИИ.
- Есть связь `бот -> БД -> Mini App -> БД`; админский контур может читать `/api/admin/summary`.

## Архитектура

```text
Telegram Bot
  -> bot/main.py
  -> bot/application: сценарий онбординга
  -> bot/domain: построение маршрута без ИИ
  -> bot/infrastructure: Telegram API, SQLite, Mini App API

SQLite
  -> users
  -> chat_states
  -> chat_messages
  -> quiz_sessions
  -> quiz_answers
  -> course_sessions
  -> course_module_events
  -> user_certificates

Telegram Mini App
  -> React + Vite
  -> /api/roadmap
  -> /api/progress/mark
  -> /api/feedback
  -> /api/roadmap/rebuild
```

## Основные команды бота

- `/start` — начать сбор профиля.
- `/app` или `/roadmap` — открыть Mini App для готового маршрута.
- `/routes` — посмотреть маршруты внутри чата.
- `/debug` — проверить URL миниаппа и путь к БД.

## Переменные окружения

Создай `.env` на основе `.env.example`:

```env
TELEGRAM_BOT_TOKEN=replace_with_botfather_token
MINIAPP_URL=https://your-domain.ru/
DATABASE_PATH=data/bot.sqlite3
LLM_ONBOARDING_ENABLED=false
```

`LLM_ONBOARDING_ENABLED=false` — нормальный режим для текущего прототипа. Когда появится реальный ИИ-агент, можно включить LLM и задать `LLM_AGENT_TOKEN`.

## Локальный запуск

```powershell
python -m bot.main
```

Отдельно можно проверить Mini App API:

```powershell
python -m bot.infrastructure.miniapp_server
```

Mini App в режиме разработки:

```powershell
cd miniapp
npm install
npm run dev
```

Production-сборка:

```powershell
cd miniapp
npm run build
```

## Docker

Сборка и запуск:

```bash
docker compose build --no-cache
docker compose up -d
```

Остановить:

```bash
docker compose stop progressors-bot
```

Полностью остановить compose-проект:

```bash
docker compose down
```

Проверка Mini App на сервере:

```bash
curl http://localhost:8080/
curl http://localhost:8080/api/roadmap
curl http://localhost:8080/api/admin/summary
```

## Настройка Telegram Mini App

После деплоя и настройки HTTPS-домена в `.env`:

```bash
docker compose run --rm -e SETUP_TELEGRAM=true progressors-bot python -m bot.setup_telegram
```

Важно: `MINIAPP_URL` должен быть публичным HTTPS URL без двойного протокола. Правильно:

```env
MINIAPP_URL=https://unovus.arffis.com/
```

Неправильно:

```env
MINIAPP_URL=https://https://unovus.arffis.com/
MINIAPP_URL=http://localhost:8080/
MINIAPP_URL=https://example.com/
```

## Nginx для домена

Если домен уже отдает старую страницу из `/var/www`, нужно проксировать его на контейнер:

```nginx
server {
    server_name unovus.arffis.com www.unovus.arffis.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/unovus.arffis.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/unovus.arffis.com/privkey.pem;
}
```

Проверка и перезапуск:

```bash
sudo nginx -t
sudo systemctl reload nginx
curl https://unovus.arffis.com/api/roadmap
```

## API Mini App

- `GET /api/roadmap` — последний маршрут из БД.
- `GET /api/roadmap?telegram_user_id=123` — маршрут конкретного Telegram-пользователя.
- `POST /api/progress/mark` — отметить модуль пройденным.
- `POST /api/feedback` — сохранить обратную связь, при необходимости перестроить маршрут.
- `POST /api/roadmap/rebuild` — перестроить маршрут вручную.
- `POST /api/certificates/upload` — загрузить сертификат.
- `GET /api/admin/summary` — сводка для будущей админки.

Пример перестройки маршрута:

```bash
curl -X POST http://localhost:8080/api/roadmap/rebuild \
  -H "Content-Type: application/json" \
  -d '{"courseId":1,"reason":"replace"}'
```

## Деплой на сервер

1. Забрать свежий код:

```bash
git pull --rebase origin main
```

2. Заполнить `.env` на сервере.

3. Собрать и запустить контейнер:

```bash
docker compose build --no-cache
docker compose up -d
```

4. Настроить Nginx на `127.0.0.1:8080`.

5. Обновить меню Telegram:

```bash
docker compose run --rm -e SETUP_TELEGRAM=true progressors-bot python -m bot.setup_telegram
```

6. Проверить:

```bash
docker compose logs -f progressors-bot
curl https://unovus.arffis.com/
curl https://unovus.arffis.com/api/roadmap
```

## Безопасность

Нельзя коммитить реальный токен Telegram-бота. Если токен уже попадал в чат, README или git, перевыпусти его через BotFather командой `/revoke`.
