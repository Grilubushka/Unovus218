import json
from pathlib import Path


class JsonStateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._data = self._load()

    def get_user(self, chat_id: int) -> dict:
        return self._data.setdefault(str(chat_id), {})

    def save_user(self, chat_id: int, data: dict) -> None:
        self._data[str(chat_id)] = data
        self._flush()

    def reset_user(self, chat_id: int) -> None:
        self._data.pop(str(chat_id), None)
        self._flush()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
