# Telegram bot + Mini App: образовательные маршруты

В репозитории подготовлен прототип Telegram-бота и React Mini App для конструктора персональных маршрутов обучения. Бот является основной точкой входа: проводит онбординг, сохраняет профиль пользователя и открывает Mini App кнопкой `web_app`. Построение маршрута, прогресс и работа с материалами находятся в Mini App.

## Запуск

### Локально

1. Создать `.env` на основе `.env.example`.
2. Положить туда токен BotFather и публичный HTTPS-адрес Mini App.
3. Запустить бота:

```powershell
python -m bot.main
```

Настроить команды и кнопку меню Mini App в Telegram:

```powershell
python -m bot.setup_telegram
```

Важно: токен нельзя коммитить. Если токен уже был опубликован, перевыпусти его через BotFather командой `/revoke`.

### База онбординга

Основной бот использует SQLite-базу старого онбординга:

```env
DATABASE_PATH=data/bot.sqlite3
```

В неё пишутся пользователи, сессии квиза, ответы и события. Второй шаг онбординга также читает из этой базы популярные пользовательские ответы и подмешивает их в TOP-10. В Docker путь переопределяется на `/app/data/bot.sqlite3`, чтобы база жила в volume контейнера.

### JSON для backend админки

После завершения онбординга бот собирает отдельный JSON-payload формата `admin.onboarding.v1`. В него входят Telegram-пользователь, id quiz/course-сессий, нормализованный профиль, сырые ключи профиля, все ответы по шагам, итог и сгенерированный маршрут. Payload сохраняется:

- в `bot_state.json` по ключу пользователя `admin_onboarding_payload`;
- в `analytics_events.payload_json` событием `admin_onboarding_payload_prepared`.

Этот объект можно без дополнительной нормализации отправлять следующим шагом в backend админки.

## Структура

- `bot/domain` — каталог MVP-направлений и чистая логика сборки маршрута для совместимости прототипа.
- `bot/application` — сценарий онбординга и форматирование сообщений.
- `bot/infrastructure` — Telegram Bot API, конфиг и JSON-хранилище состояния.
- `bot/presentation` — inline-клавиатуры и WebApp-кнопка.
- `miniapp/src/domain` — чистая логика нормализации профиля, выбора трека, ограничений маршрута и ранжирования материалов.
- `miniapp/src/infrastructure` — мок-каталог знаний и репозиторий. В будущем здесь заменяется источник данных на API.
- `miniapp/src/presentation` — UI, состояние экрана, стили и события прототипа.

## Что демонстрирует бот

- `/start` показывает интро онбординга;
- кнопка старта запускает 7-шаговый квиз из TrueTechTelegram;
- вопросы собирают цель, интерес/специальность, возраст, ближайший результат, уровень, время и ограничения;
- можно выбирать кнопки или писать свой вариант;
- после анкеты бот сохраняет профиль и показывает кнопку открытия Mini App;
- `/app` повторно показывает кнопку Mini App для уже собранного профиля.

### LLM-адаптация онбординга

Бот умеет подключать Timeweb AI-агента через OpenAI-compatible Chat Completions API и использовать его только для UX-копирайтинга: переформулировать текст текущего шага, подписи кнопок и финальный итог. Структура квиза, коды ответов и callback-логика остаются фиксированными.

```env
LLM_ONBOARDING_ENABLED=true
LLM_AGENT_BASE_URL=https://agent.timeweb.cloud/api/v1/cloud-ai/agents/2dad3aa1-b649-4dbe-ac57-a079192e0abf/v1
LLM_AGENT_ACCESS_ID=2dad3aa1-b649-4dbe-ac57-a079192e0abf
LLM_AGENT_TOKEN=your_timeweb_agent_token
LLM_AGENT_MODEL=gpt-4.1
LLM_AGENT_TIMEOUT=0
LLM_AGENT_MAX_TOKENS=500
LLM_AGENT_PROGRESS_INTERVAL=2
```

Системные промпты лежат в `bot/application/onboarding_adaptation.py`. Защита от prompt injection сделана в два слоя: пользовательские ответы передаются агенту только как JSON-данные, а ответ агента принимается только как JSON по ожидаемой схеме, чистится, ограничивается по длине и экранируется перед отправкой в Telegram.
Пока агент думает, бот редактирует центральное сообщение в промежуточное состояние. `LLM_AGENT_TIMEOUT` задается в секундах; значение `0` означает ждать ответ без ограничения по времени.
`LLM_AGENT_MAX_TOKENS` ограничивает размер JSON-ответа агента, чтобы он не тратил время на длинный вывод.
`LLM_AGENT_PROGRESS_INTERVAL` задает, как часто обновлять спиннер ожидания в Telegram.

## Mini App

Mini App реализован на React + Vite. В Docker он собирается в `dist` на Node stage, после чего контейнер отдаёт готовую статику на порту `8080`. Этот же порт отдаёт JSON API для Mini App:

- `GET /api/roadmap?telegram_user_id=...` — читает маршрут конкретного Telegram-пользователя и возвращает статус завершённого онбординга;
- `POST /api/progress/mark` — записывает завершение модуля в `course_sessions` и `course_module_events`;
- `POST /api/feedback` — записывает обратную связь в `course_module_events`.
- `POST /api/certificates/upload` — сохраняет PDF или изображение сертификата из Mini App в `data/certificates` и `user_certificates`.

Mini App получает Telegram ID из `window.Telegram.WebApp.initDataUnsafe.user.id` или из параметра `telegram_user_id`, который бот добавляет в `web_app`-кнопку. API больше не отдаёт последний маршрут без пользователя: если ID не передан или у пользователя нет завершённого онбординга, Mini App показывает стартовый экран с просьбой пройти анкету в боте.

Локальная разработка Mini App:

```powershell
cd miniapp
npm install
npm run dev
```

Проверка production-сборки:

```powershell
cd miniapp
npm run build
```

Проверка API на сервере:

```bash
curl 'http://localhost:8080/api/roadmap?telegram_user_id=123'
```

### Docker

Контейнер запускает два процесса:

- Telegram-бота через long polling;
- статическую Mini App на порту `8080`.

Сборка и запуск:

```powershell
docker compose up -d --build
```

На сервере нужно направить публичный HTTPS-домен на порт контейнера `8080`, например:

```env
MINIAPP_URL=https://your-domain.ru/
```

После изменения `MINIAPP_URL` один раз обнови Telegram-команды и кнопку Mini App:

```powershell
docker compose run --rm -e SETUP_TELEGRAM=true progressors-bot python -m bot.setup_telegram
```

или временно поставь в `docker-compose.yml`:

```yaml
SETUP_TELEGRAM: "true"
```

запусти контейнер, затем верни значение обратно на `"false"`.

## Если Telegram открывает Example Domain

Это значит, что в Telegram всё ещё зарегистрирован старый Mini App URL `https://example.com/...`.

Проверь `.env` на сервере:

```env
MINIAPP_URL=https://unovus.arffis.com/
```

После изменения `.env` нужно выполнить оба шага:

```bash
docker compose up -d --force-recreate
docker compose run --rm progressors-bot python -m bot.setup_telegram
```

Во время настройки в консоли должно появиться:

```text
Configuring Mini App URL: https://unovus.arffis.com/
Telegram commands and Mini App menu button configured.
```

Если там напечатался `example.com`, значит контейнер читает старый `.env` или файл `.env` изменён не в той папке.

## Быстрая диагностика на сервере

Проверка контейнера:

```bash
curl http://localhost:8080/ | grep Прогрессоры
```

Проверка публичного домена:

```bash
curl https://unovus.arffis.com/ | grep Прогрессоры
```

Обе команды должны найти `Прогрессоры`. Если первая работает, а вторая нет, проблема в nginx/reverse proxy, а не в Docker.

Проверка переменных внутри контейнера:

```bash
docker compose exec progressors-bot sh -lc 'echo $MINIAPP_URL'
```

Проверка URL прямо в Telegram:

```text
/debug
```

Если `/debug` показывает `example.com`, нужно исправить `.env`, пересоздать контейнер и заново выполнить `bot.setup_telegram`.
