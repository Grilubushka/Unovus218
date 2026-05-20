import os
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LLM_AGENT_ACCESS_ID = "2dad3aa1-b649-4dbe-ac57-a079192e0abf"


def load_dotenv(path: str = ".env") -> None:
    env_path = resolve_project_path(path)
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
        self.state_file = str(resolve_project_path(os.environ.get("STATE_FILE", "bot_state.json")))
        self.database_path = str(resolve_project_path(os.environ.get("DATABASE_PATH", default_database_path())))
        self.llm_onboarding_enabled = parse_bool(os.environ.get("LLM_ONBOARDING_ENABLED", "true"))
        self.llm_agent_access_id = os.environ.get("LLM_AGENT_ACCESS_ID", DEFAULT_LLM_AGENT_ACCESS_ID)
        default_llm_base_url = f"https://agent.timeweb.cloud/api/v1/cloud-ai/agents/{self.llm_agent_access_id}/v1"
        self.llm_agent_base_url = os.environ.get("LLM_AGENT_BASE_URL", default_llm_base_url)
        self.llm_agent_token = os.environ.get("LLM_AGENT_TOKEN", "")
        self.llm_agent_model = os.environ.get("LLM_AGENT_MODEL", "gpt-4.1")
        self.llm_agent_timeout = parse_float(os.environ.get("LLM_AGENT_TIMEOUT"), 0.0)
        self.llm_agent_max_tokens = parse_int(os.environ.get("LLM_AGENT_MAX_TOKENS"), 500)
        self.llm_agent_progress_interval = parse_float(os.environ.get("LLM_AGENT_PROGRESS_INTERVAL"), 2.0)

    def validate(self) -> None:
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Создай .env по примеру .env.example.")
        if self.bot_token == "replace_with_botfather_token":
            raise RuntimeError("TELEGRAM_BOT_TOKEN в .env нужно заменить на реальный токен BotFather.")
        if not self.miniapp_url:
            raise RuntimeError("MINIAPP_URL не задан. Укажи публичный HTTPS URL Mini App.")
        validate_public_https_url(self.miniapp_url)


def validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("MINIAPP_URL должен быть публичным HTTPS URL, например https://unovus.arffis.com/")

    forbidden_hosts = {"example.com", "localhost", "127.0.0.1", "0.0.0.0"}
    if parsed.hostname in forbidden_hosts:
        raise RuntimeError(
            f"MINIAPP_URL указывает на служебный адрес {parsed.hostname}. "
            "Укажи реальный публичный HTTPS-домен Mini App."
        )

    if "://" in parsed.netloc:
        raise RuntimeError("MINIAPP_URL содержит лишний протокол. Нужно так: https://unovus.arffis.com/")


def default_database_path() -> str:
    return "data/bot.sqlite3"


def parse_bool(value: str) -> bool:
    return value.strip().casefold() not in {"0", "false", "no", "off", "нет"}


def parse_float(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def resolve_project_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate
