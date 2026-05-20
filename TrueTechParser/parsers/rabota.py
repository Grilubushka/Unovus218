"""
Rabota.ru парсер — HTML-парсинг через BeautifulSoup.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, quote_plus

import config
from parsers.base import BaseParser

logger = logging.getLogger(__name__)

RABOTA_BASE = "https://www.rabota.ru"


class RabotaParser(BaseParser):
    """Парсер вакансий с rabota.ru."""

    source_name = "Rabota.ru"

    def _build_search_url(self, query: str, page: int) -> str:
        params: Dict[str, Any] = {
            "sortBy": "Date",
            "page": page,
        }
        if query:
            params["query"] = query

        return f"{RABOTA_BASE}/vacancy/search/?{urlencode(params)}"

    def _parse_salary_text(self, text: str) -> tuple:
        """Парсинг строки зарплаты."""
        text = text.strip().replace("\xa0", " ").replace(" ", "").lower()
        if not text or "договор" in text or "не указ" in text:
            return None, None, None

        currency = None
        if "руб" in text or "₽" in text:
            currency = "RUR"
        elif "$" in text or "usd" in text:
            currency = "USD"
        elif "€" in text or "eur" in text:
            currency = "EUR"

        nums = re.findall(r"\d+", text)
        sal_from = int(nums[0]) if len(nums) >= 1 else None
        sal_to   = int(nums[1]) if len(nums) >= 2 else None
        return sal_from, sal_to, currency

    def _parse_experience(self, text: str) -> str:
        """Нормализовать строку опыта."""
        text = text.strip()
        mapping = {
            "без опыта": "Без опыта",
            "1 год": "от 1 года",
            "3 года": "от 3 лет",
            "5 лет": "от 5 лет",
            "6 лет": "более 6 лет",
        }
        for key, val in mapping.items():
            if key in text.lower():
                return val
        return text

    def _get_description(self, url: str) -> str:
        """Получить полное описание вакансии."""
        try:
            soup = self.get_soup(url)
            # Различные возможные блоки с описанием
            selectors = [
                "div[data-qa='vacancy-description']",
                "div.vacancy-description",
                "section.vacancy__description",
                "div[class*='description']",
                "div[itemprop='description']",
                "article.vacancy",
            ]
            for sel in selectors:
                block = soup.select_one(sel)
                if block:
                    return block.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.debug("[Rabota.ru] Описание недоступно для %s: %s", url, e)
        return ""

    def _parse_card(self, card) -> Optional[Dict[str, Any]]:
        """Распарсить карточку вакансии."""
        try:
            # Название и ссылка
            title_tag = (
                card.select_one("a[data-qa='vacancy-title']") or
                card.select_one("h3 a") or
                card.select_one("a[href*='/vacancy/']")
            )
            if not title_tag:
                return None
            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            url = href if href.startswith("http") else RABOTA_BASE + href

            # Компания
            company_tag = (
                card.select_one("a[data-qa='vacancy-company-name']") or
                card.select_one("span[data-qa='vacancy-company']") or
                card.select_one("div.company-name a") or
                card.select_one("a[href*='/company/']")
            )
            company = company_tag.get_text(strip=True) if company_tag else ""

            # Зарплата
            salary_tag = (
                card.select_one("span[data-qa='vacancy-salary']") or
                card.select_one("div[class*='salary']") or
                card.select_one("span[class*='salary']")
            )
            salary_from, salary_to, currency = None, None, None
            if salary_tag:
                salary_from, salary_to, currency = self._parse_salary_text(
                    salary_tag.get_text(strip=True)
                )

            # Опыт
            experience = ""
            exp_tag = (
                card.select_one("span[data-qa='vacancy-experience']") or
                card.select_one("div[class*='experience']")
            )
            if exp_tag:
                experience = self._parse_experience(exp_tag.get_text(strip=True))

            # Дата публикации
            published_at = ""
            date_tag = card.select_one("span[data-qa='vacancy-date']") or card.select_one("time")
            if date_tag:
                dt_attr = date_tag.get("datetime", "")
                published_at = dt_attr if dt_attr else date_tag.get_text(strip=True)

            return {
                "title":        title,
                "company":      company,
                "salary_from":  salary_from,
                "salary_to":    salary_to,
                "currency":     currency,
                "experience":   experience,
                "description":  "",   # загружаем отдельно
                "url":          url,
                "published_at": published_at,
                "source":       self.source_name,
                "parsed_at":    datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.debug("[Rabota.ru] Ошибка карточки: %s", e)
            return None

    def fetch_vacancies(self, query: str) -> List[Dict[str, Any]]:
        vacancies: List[Dict[str, Any]] = []

        for page in range(1, config.RABOTA_MAX_PAGES + 1):
            url = self._build_search_url(query, page)
            try:
                soup = self.get_soup(url)
            except Exception as e:
                logger.error("[Rabota.ru] Не удалось загрузить страницу %d: %s", page, e)
                break

            # Ищем карточки вакансий разными селекторами
            cards = (
                soup.select("div[data-qa='vacancy-card']") or
                soup.select("article[class*='vacancy']") or
                soup.select("div[class*='vacancy-card']") or
                soup.select("li[class*='vacancy']")
            )

            if not cards:
                logger.debug("[Rabota.ru] Карточки не найдены на странице %d — завершаем", page)
                break

            for card in cards:
                vacancy = self._parse_card(card)
                if vacancy:
                    if vacancy["url"]:
                        vacancy["description"] = self._get_description(vacancy["url"])
                    vacancies.append(vacancy)

            logger.debug("[Rabota.ru] Страница %d: +%d вакансий", page, len(cards))

        return vacancies
