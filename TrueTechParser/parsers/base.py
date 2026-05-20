"""
Base parser class — абстрактный базовый класс для всех парсеров.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup

import config
from skills_extractor import extract_skills

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Базовый класс парсера вакансий."""

    source_name: str = "unknown"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET-запрос с обработкой ошибок и паузой."""
        try:
            resp = self.session.get(
                url, timeout=config.REQUEST_TIMEOUT, **kwargs
            )
            resp.raise_for_status()
            time.sleep(config.REQUEST_DELAY)
            return resp
        except requests.RequestException as e:
            logger.error("[%s] Ошибка запроса %s: %s", self.source_name, url, e)
            raise

    def get_soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Получить BeautifulSoup из URL."""
        resp = self.get(url, **kwargs)
        return BeautifulSoup(resp.text, "lxml")

    @abstractmethod
    def fetch_vacancies(self, query: str) -> List[Dict[str, Any]]:
        """Получить список вакансий для заданного поискового запроса.
        
        Returns:
            Список словарей с полями:
            title, company, salary_from, salary_to, currency,
            experience, description, url, published_at, source, parsed_at
        """

    def run(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Запустить парсер по всем запросам и вернуть объединённый список."""
        all_vacancies: List[Dict[str, Any]] = []
        for query in queries:
            display = query if query else "(все вакансии)"
            logger.info("[%s] Поиск: %s", self.source_name, display)
            try:
                vacancies = self.fetch_vacancies(query)
                # ── Извлекаем навыки из описания каждой вакансии ──────────
                for v in vacancies:
                    v["skills"] = extract_skills(v.get("description", ""))
                logger.info(
                    "[%s] Найдено %d вакансий по запросу '%s'",
                    self.source_name, len(vacancies), display
                )
                all_vacancies.extend(vacancies)
            except Exception as e:
                logger.error(
                    "[%s] Не удалось получить вакансии по запросу '%s': %s",
                    self.source_name, display, e
                )
        return all_vacancies
