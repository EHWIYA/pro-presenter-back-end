from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_BIBLE = _API_DIR / "data" / "bible-krv.json"
_SAMPLE_BIBLE = _API_DIR / "data" / "bible-krv.sample.json"


def resolve_bible_path(path: Path) -> Path:
    """bible-krv.json 없으면 샘플로 대체 (로컬·CI)."""
    if path.is_file():
        return path
    if _SAMPLE_BIBLE.is_file():
        return _SAMPLE_BIBLE
    return path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    venues_json_path: Path = Field(
        default=_API_DIR.parent / "ops" / "venues.json",
        validation_alias="VENUES_JSON_PATH",
    )
    bible_json_path: Path = Field(
        default=_DEFAULT_BIBLE,
        validation_alias="BIBLE_JSON_PATH",
    )
    cors_origins: str = Field(default="*", validation_alias="CORS_ORIGINS")

    pp_http_timeout_sec: float = Field(default=8.0, validation_alias="PP_HTTP_TIMEOUT_SEC")
    pp_send_method: str = Field(default="theme", validation_alias="PP_SEND_METHOD")

    agent_port: int = Field(default=8787, validation_alias="AGENT_PORT")
    agent_http_timeout_sec: float = Field(default=30.0, validation_alias="AGENT_HTTP_TIMEOUT_SEC")
    agent_group_theme_key: str = Field(
        default="reader-context",
        validation_alias="AGENT_GROUP_THEME_KEY",
    )
    agent_build_mode: str = Field(default="append", validation_alias="AGENT_BUILD_MODE")
    agent_auto_trigger: bool = Field(default=False, validation_alias="AGENT_AUTO_TRIGGER")

    llm_gateway_url: str | None = Field(
        default="https://llm-api.livbee.co.kr",
        validation_alias="LLM_GATEWAY_URL",
    )
    llm_gateway_api_key: str | None = Field(default=None, validation_alias="LLM_GATEWAY_API_KEY")
    llm_gateway_timeout_sec: float = Field(default=120.0, validation_alias="LLM_GATEWAY_TIMEOUT_SEC")

    pp_theme_id: str | None = Field(default=None, validation_alias="PP_THEME_ID")
    pp_theme_slide_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PP_THEME_SLIDE_ID", "PP_ACTION_UUID"),
    )
    pp_library_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PP_LIBRARY_ID", "PP_DOCUMENT_UUID"),
    )
    pp_presentation_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PP_PRESENTATION_ID", "PP_PRESENTATION_UUID"),
    )
    pp_message_id: str | None = Field(default=None, validation_alias="PP_MESSAGE_ID")

    api_key: str | None = Field(default=None, validation_alias="API_KEY")
    send_log_path: Path | None = Field(default=None, validation_alias="SEND_LOG_PATH")

    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    song_library_auto_save: bool = Field(
        default=True, validation_alias="SONG_LIBRARY_AUTO_SAVE"
    )
    song_library_default_limit: int = Field(
        default=20, validation_alias="SONG_LIBRARY_DEFAULT_LIMIT"
    )

    @field_validator(
        "api_key",
        "pp_theme_id",
        "pp_theme_slide_id",
        "llm_gateway_url",
        "llm_gateway_api_key",
        "database_url",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def resolved_bible_path(self) -> Path:
        return resolve_bible_path(self.bible_json_path)

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
