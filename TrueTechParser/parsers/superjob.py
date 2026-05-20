"""
SuperJob парсер.
Поддерживает два режима:
  1. API (если задан SUPERJOB_API_KEY в config.py) — надёжнее
  2. HTML-парсинг через BeautifulSoup — если ключа нет
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config
from parsers.base import BaseParser

logger = logging.getLogger(__name__)

SJ_API_BASE  = "https://api.superjob.ru/2.0"
SJ_SITE_BASE = "https://www.superjob.ru"


class SuperJobParser(BaseParser):
    """Парсер вакансий с SuperJob."""

    source_name = "SuperJob"

    # ── API-режим ──────────────────────────────────────────────────────────────

    def _api_headers(self) -> Dict[str, str]:
        return {
            **config.HEADERS,
            "X-Api-App-Id": config.SUPERJOB_API_KEY,
        }

    def _fetch_via_api(self, query: str) -> List[Dict[str, Any]]:
        vacancies: List[Dict[str, Any]] = []
        for page in range(config.SUPERJOB_MAX_PAGES):
            params: Dict[str, Any] = {
                "count": config.SUPERJOB_PER_PAGE,
                "page":  page,
                "order_field": "date",
                "order_direction": "desc",
            }
            if query:
                params["keyword"] = query

            try:
                resp = self.session.get(
                    f"{SJ_API_BASE}/vacancies/",
                    params=params,
                    headers=self._api_headers(),
                    timeout=config.REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("[SuperJob API] Ошибка: %s", e)
                break

            import time; time.sleep(config.REQUEST_DELAY)

            objects = data.get("objects", [])
            if not objects:
                break

            for obj in objects:
                try:
                    vacancies.append(self._parse_api_item(obj))
                except Exception as e:
                    logger.warning("[SuperJob API] Пропущен объект: %s", e)

            if not data.get("more", False):
                break

        return vacancies

    def _parse_api_item(self, obj: Dict) -> Dict[str, Any]:
        salary_from = obj.get("payment_from") or None
        salary_to   = obj.get("payment_to")   or None
        currency    = obj.get("currency", "RUR") if (salary_from or salary_to) else None

        experience = ""
        exp = obj.get("experience")
        if exp:
            experience = exp.get("title", "")

        published_at = ""
        ts = obj.get("date_published")
        if ts:
            published_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        # Описание: объединяем candidat + work + client
        desc_parts = [
            obj.get("candidat", ""),
            obj.get("work", ""),
            obj.get("client", {}).get("description", "") if obj.get("client") else "",
        ]
        description = "\n\n".join(p for p in desc_parts if p).strip()

        # Очищаем от HTML
        from bs4 import BeautifulSoup
        description = BeautifulSoup(description, "lxml").get_text(separator="\n").strip()

        return {
            "title":        obj.get("profession", ""),
            "company":      (obj.get("client") or {}).get("title", ""),
            "salary_from":  salary_from,
            "salary_to":    salary_to,
            "currency":     currency,
            "experience":   experience,
            "description":  description,
            "url":          obj.get("link", ""),
            "published_at": published_at,
            "source":       self.source_name,
            "parsed_at":    datetime.now(timezone.utc).isoformat(),
        }

    # ── HTML-режим ─────────────────────────────────────────────────────────────

    def _build_search_url(self, query: str, page: int) -> str:
        base = f"{SJ_SITE_BASE}/vacancy/search/"
        params = f"?sort=date&page={page}"
        if query:
            safe = query.replace(" ", "+")
            params += f"&keywords={safe}"
        return base + params

    def _parse_salary_text(self, text: str) -> tuple:
        """Парсинг строки вида '50 000 — 80 000 ₽'."""
        text = text.strip().replace("\xa0", " ").replace(" ", "")
        currency = None
        if "₽" in text or "руб" in text.lower():
            currency = "RUR"
        elif "$" in text:
            currency = "USD"
        elif "€" in text:
            currency = "EUR"

        # Убираем символы валют
        clean = re.sub(r"[₽$€руб.]", "", text, flags=re.IGNORECASE).strip()
        parts = re.split(r"[—–\-]", clean)
        try:
            sal_from = int(re.sub(r"\D", "", parts[0])) if parts[0].strip() else None
        except (ValueError, IndexError):
            sal_from = None
        try:
            sal_to = int(re.sub(r"\D", "", parts[1])) if len(parts) > 1 and parts[1].strip() else None
        except (ValueError, IndexError):
            sal_to = None

        return sal_from, sal_to, currency

    def _parse_html_card(self, card) -> Optional[Dict[str, Any]]:
        """Распарсить карточку вакансии из HTML."""
        try:
            # Название и ссылка
            title_tag = card.select_one("a[href*='/vakansii/']")
            if not title_tag:
                return None
            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            url = href if href.startswith("http") else SJ_SITE_BASE + href

            # Компания
            company_tag = card.select_one("a[href*='/company/']") or card.select_one("span.f-test-text-company-name")
            company = company_tag.get_text(strip=True) if company_tag else ""

            # Зарплата
            salary_tag = card.select_one("span.f-test-text-company-item-salary")
            salary_from, salary_to, currency = None, None, None
            if salary_tag:
                sal_text = salary_tag.get_text(strip=True)
                if sal_text and sal_text.lower() not in ("договорная", "не указана"):
                    salary_from, salary_to, currency = self._parse_salary_text(sal_text)

            # Опыт
            experience = ""
            for span in card.select("span"):
                t = span.get_text(strip=True)
                if "опыт" in t.lower() or "без опыта" in t.lower():
                    experience = t
                    break

            return {
                "title":        title,
                "company":      company,
                "salary_from":  salary_from,
                "salary_to":    salary_to,
                "currency":     currency,
                "experience":   experience,
                "description":  "",       # загружаем отдельно
                "url":          url,
                "published_at": "",
                "source":       self.source_name,
                "parsed_at":    datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.debug("[SuperJob HTML] Ошибка карточки: %s", e)
            return None

    def _fetch_description(self, url: str) -> str:
        """Получить полное описание со страницы вакансии."""
        try:
            soup = self.get_soup(url)
            desc_block = (
                soup.select_one("div.f-test-vacancy-desription") or
                soup.select_one("[class*='vacancy-description']") or
                soup.select_one("div[itemprop='description']")
            )
            if desc_block:
                return desc_block.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.debug("[SuperJob] Не удалось загрузить описание %s: %s", url, e)
        return ""

    def _fetch_via_html(self, query: str) -> List[Dict[str, Any]]:
        vacancies: List[Dict[str, Any]] = []
        for page in range(1, config.SUPERJOB_MAX_PAGES + 1):
            url = self._build_search_url(query, page)
            try:
                soup = self.get_soup(url)
            except Exception:
                break

            cards = soup.select("div[class*='f-test-search-result-item']")
            if not cards:
                # Запасной селектор
                cards = soup.select("article")

            if not cards:
                logger.debug("[SuperJob HTML] Карточки не найдены на странице %d", page)
                break

            for card in cards:
                vacancy = self._parse_html_card(card)
                if vacancy:
                    if vacancy["url"]:
                        vacancy["description"] = self._fetch_description(vacancy["url"])
                    vacancies.append(vacancy)

        return vacancies

    # ── Основной метод ─────────────────────────────────────────────────────────

    def fetch_vacancies(self, query: str) -> List[Dict[str, Any]]:
        if config.SUPERJOB_API_KEY:
            logger.info("[SuperJob] Используем API-режим")
            return self._fetch_via_api(query)
        else:
            logger.info("[SuperJob] Используем HTML-парсинг (ключ API не задан)")
            return self._fetch_via_html(query)
