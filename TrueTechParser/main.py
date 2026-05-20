"""
TrueTechParser — точка входа.

Использование:
    python main.py            # запуск по расписанию (cron)
    python main.py --once     # один запуск и выход
    python main.py --stats    # показать статистику по сохранённым вакансиям
"""

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

import config
from parsers import HHParser, SuperJobParser, RabotaParser
from storage import JsonStorage

# ── Логирование ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
logger = logging.getLogger("truetechparser")
console = Console()

# ── Парсеры ───────────────────────────────────────────────────────────────────

PARSERS = [
    HHParser,
    SuperJobParser,
    RabotaParser,
]


# ── Основная логика ───────────────────────────────────────────────────────────

def run_parser(parser_class, queries: List[str]) -> List[Dict[str, Any]]:
    """Запустить один парсер и вернуть результаты."""
    parser = parser_class()
    return parser.run(queries)


def collect_all(queries: List[str]) -> List[Dict[str, Any]]:
    """Запустить все парсеры параллельно."""
    all_vacancies: List[Dict[str, Any]] = []

    console.rule("[bold cyan]TrueTechParser — Сбор вакансий[/bold cyan]")

    with ThreadPoolExecutor(max_workers=len(PARSERS)) as executor:
        futures = {
            executor.submit(run_parser, pc, queries): pc.source_name
            for pc in PARSERS
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                results = future.result()
                all_vacancies.extend(results)
                logger.info(
                    "✅ [bold green]%s[/bold green]: получено [bold]%d[/bold] вакансий",
                    source, len(results),
                )
            except Exception as e:
                logger.error("❌ [bold red]%s[/bold red] завершился с ошибкой: %s", source, e)

    return all_vacancies


def print_stats(storage: JsonStorage) -> None:
    """Вывести красивую таблицу статистики."""
    stats = storage.stats()

    table = Table(title="📊 Статистика TrueTechParser", show_header=True, header_style="bold magenta")
    table.add_column("Источник", style="cyan", no_wrap=True)
    table.add_column("Вакансий", style="green", justify="right")

    for source, count in stats["by_source"].items():
        table.add_row(source, str(count))

    table.add_section()
    table.add_row("[bold]Итого[/bold]", f"[bold]{stats['total']}[/bold]")

    console.print(table)
    console.print(f"\n📁 Файл: [link={stats['file']}]{stats['file']}[/link]")


def job(queries: List[str], storage: JsonStorage) -> None:
    """Один полный цикл сбора и сохранения вакансий."""
    vacancies = collect_all(queries)

    if not vacancies:
        logger.warning("Вакансии не найдены. Проверьте настройки и доступность сайтов.")
        return

    stats = storage.save(vacancies)

    rprint(Panel(
        f"[bold green]Готово![/bold green]\n"
        f"  Получено:   [bold]{len(vacancies)}[/bold]\n"
        f"  Добавлено:  [bold green]{stats['added']}[/bold green]\n"
        f"  Дублей:     [bold yellow]{stats['skipped']}[/bold yellow]\n"
        f"  Всего в БД: [bold]{stats['total']}[/bold]",
        title="TrueTechParser",
        border_style="green",
    ))


# ── CLI & Scheduler ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TrueTechParser — парсер вакансий (hh.ru, SuperJob, Rabota.ru)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Выполнить один запуск и выйти (без расписания)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Показать статистику по сохранённым вакансиям",
    )
    parser.add_argument(
        "--query",
        nargs="*",
        help="Поисковые запросы (переопределяет config.SEARCH_QUERIES)",
    )
    args = parser.parse_args()

    storage = JsonStorage()
    queries = args.query if args.query is not None else config.SEARCH_QUERIES

    # ── Только статистика ──────────────────────────────────────────────────────
    if args.stats:
        print_stats(storage)
        sys.exit(0)

    # ── Один запуск ───────────────────────────────────────────────────────────
    if args.once:
        job(queries, storage)
        sys.exit(0)

    # ── По расписанию ─────────────────────────────────────────────────────────
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler не установлен. Запустите: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="Europe/Moscow")
    trigger = CronTrigger(
        hour=config.SCHEDULE_HOUR,
        minute=config.SCHEDULE_MINUTE,
    )
    scheduler.add_job(job, trigger, args=[queries, storage], id="collect_vacancies")

    rprint(Panel(
        f"[bold cyan]Планировщик запущен[/bold cyan]\n"
        f"  Расписание: каждые [bold]{config.SCHEDULE_HOUR}[/bold] часа\n"
        f"  Запросы:    [bold]{queries or ['(все вакансии)']}[/bold]\n\n"
        f"  Для немедленного запуска используйте: [italic]python main.py --once[/italic]\n"
        f"  Остановить: [bold red]Ctrl+C[/bold red]",
        title="TrueTechParser",
        border_style="cyan",
    ))

    # Запускаем сразу при старте
    logger.info("Первый запуск сразу при старте...")
    job(queries, storage)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Планировщик остановлен.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
