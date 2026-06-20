import os
import re
from dataclasses import dataclass
from typing import Optional

from .errors import ConfigError

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


NOTION_TOKEN_PATTERN = re.compile(r"^(secret|ntn)_[A-Za-z0-9_-]{20,}$")
WEREAD_API_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~+/=-]{10,}$")
NOTION_ID_PATTERN = re.compile(
    r"^[a-f0-9]{32}$|^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)
NOTION_ID_IN_TEXT_PATTERN = re.compile(
    r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Settings:
    weread_api_key: str
    notion_token: str
    notion_target: str
    notion_data_source_id: Optional[str] = None
    notion_database_id: Optional[str] = None
    full_sync: bool = False


def emit_error(message: str) -> None:
    if os.getenv("GITHUB_ACTIONS") == "true":
        safe = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error::{safe}")
    else:
        print(f"配置错误: {message}")


def fail_config(message: str) -> None:
    emit_error(message)
    raise ConfigError(message)


def _clean_env(name: str, required: bool = False) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None:
        if required:
            fail_config(f"缺少 {name}，请在 GitHub Secrets 或 .env 中配置")
        return None

    value = re.sub(r"\s+", "", raw)
    if value:
        os.environ[name] = value
        return value

    os.environ.pop(name, None)
    if required:
        fail_config(f"{name} 为空，请检查配置")
    return None


def _validate_regex(name: str, value: Optional[str], pattern: re.Pattern, hint: str) -> None:
    if value and not pattern.search(value):
        fail_config(f"{name} 格式不正确：{hint}")


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings(require_weread: bool = True) -> Settings:
    load_dotenv()

    weread_api_key = _clean_env("WEREAD_API_KEY", required=require_weread)
    notion_token = _clean_env("NOTION_TOKEN", required=True)
    notion_page = _clean_env("NOTION_PAGE")
    notion_database_id = _clean_env("NOTION_DATABASE_ID")
    notion_data_source_id = _clean_env("NOTION_DATA_SOURCE_ID")

    if weread_api_key:
        _validate_regex(
            "WEREAD_API_KEY",
            weread_api_key,
            WEREAD_API_KEY_PATTERN,
            "应为微信读书 Gateway API Key，不能包含空格或换行",
        )
    _validate_regex(
        "NOTION_TOKEN",
        notion_token,
        NOTION_TOKEN_PATTERN,
        "应以 secret_ 或 ntn_ 开头，不能包含空格或换行",
    )
    for name, value in (
        ("NOTION_DATA_SOURCE_ID", notion_data_source_id),
        ("NOTION_DATABASE_ID", notion_database_id),
    ):
        _validate_regex(
            name,
            value,
            NOTION_ID_PATTERN,
            "应为 32 位 Notion ID 或带连字符的 UUID",
        )

    notion_target = notion_data_source_id or notion_page or notion_database_id
    if not notion_target:
        fail_config("缺少 NOTION_PAGE / NOTION_DATA_SOURCE_ID / NOTION_DATABASE_ID，请至少配置其中一个")
    if notion_page and not NOTION_ID_IN_TEXT_PATTERN.search(notion_page):
        fail_config("NOTION_PAGE 格式不正确：请填写 Notion 数据库链接、页面链接或 ID")

    return Settings(
        weread_api_key=weread_api_key or "",
        notion_token=notion_token or "",
        notion_target=notion_target,
        notion_data_source_id=notion_data_source_id,
        notion_database_id=notion_database_id,
        full_sync=_truthy(os.getenv("WEREAD_NOTION_FULL_SYNC")),
    )


def extract_notion_id(text: str) -> str:
    match = NOTION_ID_IN_TEXT_PATTERN.search(text)
    if not match:
        fail_config("获取 Notion ID 失败，请检查 NOTION_PAGE / NOTION_DATA_SOURCE_ID")
    return match.group(0)
