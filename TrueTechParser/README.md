# TrueTechParser 🔍

Многоисточниковый парсер вакансий на Python. Собирает актуальные вакансии с **hh.ru**, **SuperJob** и **Rabota.ru**, дедуплицирует и сохраняет в JSON.

## Возможности

- ✅ **hh.ru** — через официальный REST API (надёжно, без ключа)
- ✅ **SuperJob** — HTML-парсинг (или API если есть ключ)
- ✅ **Rabota.ru** — HTML-парсинг
- ✅ Параллельный запуск всех парсеров
- ✅ Дедупликация по URL (повторные запуски не дублируют записи)
- ✅ Сохранение в JSON, отсортированный по дате публикации
- ✅ Запуск по расписанию (каждые N часов) через APScheduler
- ✅ Красивый вывод в консоль через `rich`

## Установка

```bash
cd TrueTechParser
pip install -r requirements.txt
```

## Использование

### Один запуск (рекомендуется для начала)
```bash
python main.py --once
```

### Поиск по ключевым словам
```bash
python main.py --once --query "Python" "аналитик" "менеджер"
```

### Запуск по расписанию (каждые 4 часа)
```bash
python main.py
```

### Статистика
```bash
python main.py --stats
```

## Конфигурация

Откройте [`config.py`](config.py) и настройте:

| Параметр | По умолчанию | Описание |
|---|---|---|
| `SEARCH_QUERIES` | `[""]` | Ключевые слова поиска (`""` = все вакансии) |
| `HH_AREA_ID` | `113` | Регион: 1=Москва, 2=СПб, 113=Россия |
| `HH_MAX_PAGES` | `5` | Страниц с hh.ru |
| `SUPERJOB_MAX_PAGES` | `3` | Страниц с SuperJob |
| `RABOTA_MAX_PAGES` | `3` | Страниц с Rabota.ru |
| `SCHEDULE_HOUR` | `"*/4"` | Расписание: каждые 4 часа |
| `SUPERJOB_API_KEY` | `""` | Ключ SuperJob API (опционально) |
| `REQUEST_DELAY` | `1.5` | Пауза между запросами (сек) |

## Структура вывода

Результаты сохраняются в `output/vacancies.json`:

```json
[
  {
    "title": "Python-разработчик",
    "company": "ООО Рога и Копыта",
    "salary_from": 150000,
    "salary_to": 250000,
    "currency": "RUR",
    "experience": "От 3 до 6 лет",
    "description": "Полное описание вакансии...",
    "url": "https://hh.ru/vacancy/12345678",
    "published_at": "2026-05-20T06:00:00+0000",
    "source": "hh.ru",
    "parsed_at": "2026-05-20T06:15:00+00:00"
  }
]
```

## Структура проекта

```
TrueTechParser/
├── main.py              # Точка входа + scheduler
├── config.py            # Конфигурация
├── requirements.txt
├── parsers/
│   ├── base.py          # Базовый класс
│   ├── hh.py            # hh.ru (API)
│   ├── superjob.py      # SuperJob (API / HTML)
│   └── rabota.py        # Rabota.ru (HTML)
├── storage/
│   └── json_storage.py  # Хранилище + дедупликация
└── output/
    └── vacancies.json   # Результаты
```

## Cron (альтернатива встроенному scheduler)

Если хотите использовать системный cron вместо APScheduler:

```bash
# Каждые 4 часа
0 */4 * * * cd /path/to/TrueTechParser && python main.py --once >> logs/cron.log 2>&1
```
