"""
hh.ru парсер — HTML-парсинг (API требует OAuth с 2024 года).
Парсит страницу поиска: https://hh.ru/search/vacancy
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import config
from parsers.base import BaseParser

logger = logging.getLogger(__name__)

HH_BASE = "https://hh.ru"
HH_SEARCH = f"{HH_BASE}/search/vacancy"

# Карта data-qa → уровень опыта
_EXPERIENCE_MAP = {
    "noExperience":   "Без опыта",
    "between1And3":   "От 1 года до 3 лет",
    "between3And6":   "От 3 до 6 лет",
    "moreThan6":      "Более 6 лет",
}


class HHParser(BaseParser):
    """Парсер вакансий hh.ru через HTML."""

    source_name = "hh.ru"

    # ── Заголовки браузера ─────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": "https://hh.ru/",
        })

    # ── URL-строитель ──────────────────────────────────────────────────────────

    def _search_url(self, query: str, page: int) -> str:
        params: Dict[str, Any] = {
            "area": config.HH_AREA_ID,
            "per_page": config.HH_PER_PAGE,
            "page": page,
            "order_by": "publication_time",
        }
        if query:
            params["text"] = query
        return f"{HH_SEARCH}?{urlencode(params)}"

    # ── Парсинг зарплаты ───────────────────────────────────────────────────────

    def _parse_salary(self, card) -> tuple:
        """
        Пробуем несколько способов извлечь зарплату.
        Возвращает (salary_from, salary_to, currency).
        """
        # 1. data-qa="vacancy-serp__compensation"
        comp = card.select_one('[data-qa="vacancy-serp__compensation"]')
        # 2. Любой span с data-qa содержащим "compensation" но не "frequency"
        if not comp:
            for el in card.select('[data-qa*="compensation"]'):
                if "frequency" not in el.get("data-qa", ""):
                    comp = el
                    break
        # 3. Fallback — ищем текст с числом + валютой
        if not comp:
            for span in card.select("span"):
                t = span.get_text(strip=True)
                if re.search(r"\d[\d\s]+[₽$€]", t):
                    comp = span
                    break

        if not comp:
            return None, None, None

        return self._split_salary_text(comp.get_text(strip=True))

    def _split_salary_text(self, text: str) -> tuple:
        """'от 80 000 до 120 000 ₽' → (80000, 120000, 'RUR')"""
        text = text.replace("\xa0", " ").replace(" ", "")
        currency = None
        if "₽" in text or "руб" in text.lower():
            currency = "RUR"
        elif "$" in text:
            currency = "USD"
        elif "€" in text:
            currency = "EUR"

        # Берём только числа >= 1000 (реальные суммы зарплат)
        nums = [int(n) for n in re.findall(r"\d+", text)
                if len(n) >= 4 and int(n) >= 1000]
        sal_from = nums[0] if len(nums) >= 1 else None
        sal_to   = nums[1] if len(nums) >= 2 else None

        # Нет реальных цифр → нет данных
        if not sal_from and not sal_to:
            return None, None, None

        return sal_from, sal_to, currency

    # ── Парсинг опыта ──────────────────────────────────────────────────────────

    def _parse_experience(self, card) -> str:
        for el in card.select('[data-qa*="work-experience"]'):
            dqa = el.get("data-qa", "")
            for key, label in _EXPERIENCE_MAP.items():
                if key in dqa:
                    return label
            # Если ключ неизвестен — берём текст
            text = el.get_text(strip=True)
            if text:
                return text
        return ""

    # ── Описание вакансии ──────────────────────────────────────────────────────

    def _get_description(self, url: str) -> str:
        """Загружаем страницу вакансии и вытаскиваем описание."""
        try:
            soup = self.get_soup(url)
            block = (
                soup.select_one('[data-qa="vacancy-description"]') or
                soup.select_one("div.vacancy-description") or
                soup.select_one('[data-qa="vacancy-branded-body"]') or
                soup.select_one("div[class*='vacancy-description']")
            )
            if block:
                return block.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.debug("[hh.ru] Описание недоступно для %s: %s", url, e)
        return ""

    # ── Дата публикации ────────────────────────────────────────────────────────

    def _parse_date(self, card) -> str:
        time_el = card.select_one("time")
        if time_el:
            return time_el.get("datetime", time_el.get_text(strip=True))
        return ""

    # ── Парсинг карточки ───────────────────────────────────────────────────────

    def _parse_card(self, card) -> Optional[Dict[str, Any]]:
        try:
            # Название и URL
            title_el = card.select_one('[data-qa="serp-item__title"]')
            if not title_el:
                return None
            title = card.select_one('[data-qa="serp-item__title-text"]')
            title_text = title.get_text(strip=True) if title else title_el.get_text(strip=True)
            href = title_el.get("href", "")
            # Убираем UTM-параметры
            url = href.split("?")[0] if href else ""
            if url and not url.startswith("http"):
                url = HH_BASE + url

            # Компания
            emp_el = card.select_one('[data-qa="vacancy-serp__vacancy-employer"]')
            company = emp_el.get_text(strip=True) if emp_el else ""

            # Зарплата
            sal_from, sal_to, currency = self._parse_salary(card)

            # Опыт
            experience = self._parse_experience(card)

            # Дата
            published_at = self._parse_date(card)

            return {
                "title":        title_text,
                "company":      company,
                "salary_from":  sal_from,
                "salary_to":    sal_to,
                "currency":     currency,
                "experience":   experience,
                "description":  "",   # загружается отдельно
                "url":          url,
                "published_at": published_at,
                "source":       self.source_name,
                "parsed_at":    datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.debug("[hh.ru] Ошибка карточки: %s", e)
            return None

    # ── Основной метод ─────────────────────────────────────────────────────────

    def fetch_vacancies(self, query: str) -> List[Dict[str, Any]]:
        vacancies: List[Dict[str, Any]] = []

        for page in range(config.HH_MAX_PAGES):
            url = self._search_url(query, page)
            try:
                soup = self.get_soup(url)
            except Exception as e:
                logger.error("[hh.ru] Не удалось загрузить страницу %d: %s", page, e)
                break

            cards = soup.select('[data-qa="vacancy-serp__vacancy"]')
            if not cards:
                logger.debug("[hh.ru] Нет карточек на странице %d — завершаем", page)
                break

            for card in cards:
                vacancy = self._parse_card(card)
                if vacancy and vacancy["url"]:
                    vacancy["description"] = self._get_description(vacancy["url"])
                    vacancies.append(vacancy)

            logger.debug("[hh.ru] Страница %d: +%d вакансий", page + 1, len(cards))

            # Проверяем наличие следующей страницы
            next_btn = soup.select_one('[data-qa="pager-next"]')
            if not next_btn:
                break

        return vacancies
