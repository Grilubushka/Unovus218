import os
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


class Settings:
    def __init__(self) -> None:
        load_dotenv()
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.miniapp_url = os.environ.get("MINIAPP_URL", "")
        self.state_file = os.environ.get("STATE_FILE", "bot_state.json")

    def validate(self) -> None:
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Создай .env по примеру .env.example.")
