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
        default=Path("/live/venues.json"),
        validation_alias="VENUES_JSON_PATH",
    )
    bible_json_path: Path = Field(
        default=_DEFAULT_BIBLE,
        validation_alias="BIBLE_JSON_PATH",
    )
    cors_origins: str = Field(default="*", validation_alias="CORS_ORIGINS")

    pp_http_timeout_sec: float = Field(default=8.0, validation_alias="PP_HTTP_TIMEOUT_SEC")
    pp_send_method: str = Field(default="theme", validation_alias="PP_SEND_METHOD")

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

    @field_validator("api_key", "pp_theme_id", "pp_theme_slide_id", mode="before")
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
