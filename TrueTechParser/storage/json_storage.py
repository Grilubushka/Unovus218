"""
JSON-хранилище с атомарной записью и дедупликацией по URL.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import config

logger = logging.getLogger(__name__)


class JsonStorage:
    """Сохраняет и обновляет вакансии в JSON-файле."""

    def __init__(self):
        self.output_dir = Path(config.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.output_dir / config.OUTPUT_FILE

    # ── Чтение ─────────────────────────────────────────────────────────────────

    def load(self) -> List[Dict[str, Any]]:
        """Загрузить существующие вакансии из файла."""
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            logger.warning("Файл %s имеет неверный формат — сбрасываем.", self.file_path)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Ошибка чтения %s: %s", self.file_path, e)
        return []

    # ── Запись ─────────────────────────────────────────────────────────────────

    def _atomic_write(self, data: List[Dict[str, Any]]) -> None:
        """Атомарная запись: сначала во временный файл, затем rename."""
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.output_dir, prefix=".tmp_", suffix=".json"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.file_path)
        except Exception:
            # Удаляем tmp-файл если что-то пошло не так
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ── Дедупликация и слияние ─────────────────────────────────────────────────

    def save(self, new_vacancies: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Добавить новые вакансии к существующим, убрав дубликаты по URL.

        Returns:
            Словарь со статистикой: {'total': int, 'added': int, 'skipped': int}
        """
        existing = self.load()
        existing_urls = {v.get("url", "") for v in existing if v.get("url")}

        added = 0
        skipped = 0
        for vacancy in new_vacancies:
            url = vacancy.get("url", "")
            if url and url in existing_urls:
                skipped += 1
                continue
            existing.append(vacancy)
            if url:
                existing_urls.add(url)
            added += 1

        # Сортируем по дате публикации (свежие первыми)
        existing.sort(key=lambda v: v.get("published_at", "") or "", reverse=True)

        self._atomic_write(existing)

        stats = {"total": len(existing), "added": added, "skipped": skipped}
        logger.info(
            "Сохранено: всего=%d, добавлено=%d, пропущено дублей=%d",
            stats["total"], stats["added"], stats["skipped"],
        )
        return stats

    # ── Утилиты ────────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Быстрая статистика по сохранённым вакансиям."""
        data = self.load()
        by_source: Dict[str, int] = {}
        for v in data:
            src = v.get("source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1
        return {
            "total": len(data),
            "by_source": by_source,
            "file": str(self.file_path.resolve()),
        }
