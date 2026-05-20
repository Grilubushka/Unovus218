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

## Mini App

Mini App реализован на React + Vite. В Docker он собирается в `dist` на Node stage, после чего контейнер отдаёт готовую статику на порту `8080`. Для Telegram это не backend приложения, а webview-интерфейс внутри бота.

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
