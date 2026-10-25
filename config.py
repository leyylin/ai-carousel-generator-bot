from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{(DATA_DIR / 'carousel.db').as_posix()}"


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    BOT_TOKEN: str = ""
    LOG_LEVEL: str = "INFO"

    AI_MODE: str = Field(default="free")
    IMAGE_MODE: str = Field(default="free")

    FREE_LLM_ENDPOINT: str = "https://text.pollinations.ai/openai"
    FREE_LLM_MODEL: str = "openai"
    FREE_LLM_API_KEY: str = ""

    OPENROUTER_ENDPOINT: str = "https://openrouter.ai/api/v1/chat/completions"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENROUTER_SITE_URL: str = "https://t.me/"

    FREE_IMAGE_BASE_URL: str = "https://image.pollinations.ai/prompt"
    FREE_IMAGE_MODEL: str = "flux"
    IMAGE_WIDTH: int = Field(default=1080, ge=512, le=2048)
    IMAGE_HEIGHT: int = Field(default=1350, ge=512, le=2048)
    IMAGE_SUFFIX: str = (
        ", aesthetic beauty salon photography, soft studio lighting, high resolution, "
        "editorial magazine style, 8k, no text, no watermark"
    )
    IMAGE_CONCURRENCY: int = Field(default=3, ge=1, le=10)
    IMAGE_RETRIES: int = Field(default=3, ge=0, le=8)
    IMAGE_TIMEOUT: int = Field(default=120, ge=10, le=600)

    FAL_KEY: str = ""
    REPLICATE_API_TOKEN: str = ""
    HF_API_KEY: str = ""

    LLM_TIMEOUT: int = Field(default=90, ge=10, le=300)
    LLM_RETRIES: int = Field(default=2, ge=0, le=5)
    SLIDES_COUNT: int = Field(default=6, ge=5, le=7)

    FREE_TRIAL_GENERATIONS: int = Field(default=2, ge=0)
    SUB_GENERATIONS_LIMIT: int = Field(default=30, ge=1)
    SUB_PRICE_STARS: int = Field(default=250, ge=1)
    SUB_DAYS: int = Field(default=30, ge=1)

    MAX_TOPIC_LENGTH: int = Field(default=300, ge=10)
    MAX_FIELD_LENGTH: int = Field(default=1200, ge=50)

    DATABASE_URL: str = DEFAULT_DATABASE_URL
    RENDER_OUTPUT_DIR: Path = BASE_DIR / "generated_carousel"
    RENDER_CONCURRENCY: int = Field(default=1, ge=1, le=4)
    SEND_MEDIA_MODE: str = "photo"

    @field_validator("AI_MODE")
    @classmethod
    def validate_ai_mode(cls, value: str) -> str:
        normalized = (value or "free").strip().lower()
        if normalized not in {"free", "paid"}:
            raise ValueError("AI_MODE must be 'free' or 'paid'")
        return normalized

    @field_validator("IMAGE_MODE")
    @classmethod
    def validate_image_mode(cls, value: str) -> str:
        normalized = (value or "free").strip().lower()
        if normalized not in {"free", "paid", "hf", "huggingface", "local"}:
            raise ValueError(
                "IMAGE_MODE must be 'free', 'paid', 'hf', 'huggingface' or 'local'"
            )
        return normalized

    @field_validator("SEND_MEDIA_MODE")
    @classmethod
    def validate_media_mode(cls, value: str) -> str:
        normalized = (value or "photo").strip().lower()
        if normalized not in {"photo", "document", "both"}:
            raise ValueError("SEND_MEDIA_MODE must be 'photo', 'document' or 'both'")
        return normalized

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        return (value or "INFO").strip().upper()

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env", override=False)
        ai_mode = _env("AI_MODE", "free").lower()
        image_mode = (_env("IMAGE_MODE") or ai_mode).lower()
        render_dir = Path(_env("RENDER_OUTPUT_DIR", str(BASE_DIR / "generated_carousel")))
        if not render_dir.is_absolute():
            render_dir = BASE_DIR / render_dir
        return cls(
            BOT_TOKEN=_env("BOT_TOKEN"),
            LOG_LEVEL=_env("LOG_LEVEL", "INFO"),
            AI_MODE=ai_mode,
            IMAGE_MODE=image_mode,
            FREE_LLM_ENDPOINT=_env("FREE_LLM_ENDPOINT", "https://text.pollinations.ai/openai"),
            FREE_LLM_MODEL=_env("FREE_LLM_MODEL", "openai"),
            FREE_LLM_API_KEY=_env("FREE_LLM_API_KEY"),
            OPENROUTER_ENDPOINT=_env(
                "OPENROUTER_ENDPOINT", "https://openrouter.ai/api/v1/chat/completions"
            ),
            OPENROUTER_API_KEY=_env("OPENROUTER_API_KEY"),
            OPENROUTER_MODEL=_env("OPENROUTER_MODEL", "google/gemini-2.0-flash-001"),
            OPENROUTER_SITE_URL=_env("OPENROUTER_SITE_URL", "https://t.me/"),
            FREE_IMAGE_BASE_URL=_env(
                "FREE_IMAGE_BASE_URL", "https://image.pollinations.ai/prompt"
            ),
            FREE_IMAGE_MODEL=_env("FREE_IMAGE_MODEL", "flux"),
            IMAGE_WIDTH=int(_env("IMAGE_WIDTH", "1080")),
            IMAGE_HEIGHT=int(_env("IMAGE_HEIGHT", "1350")),
            IMAGE_SUFFIX=_env(
                "IMAGE_SUFFIX",
                ", aesthetic beauty salon photography, soft studio lighting, high resolution, "
                "editorial magazine style, 8k, no text, no watermark",
            ),
            IMAGE_CONCURRENCY=int(_env("IMAGE_CONCURRENCY", "3")),
            IMAGE_RETRIES=int(_env("IMAGE_RETRIES", "3")),
            IMAGE_TIMEOUT=int(_env("IMAGE_TIMEOUT", "120")),
            FAL_KEY=_env("FAL_KEY"),
            REPLICATE_API_TOKEN=_env("REPLICATE_API_TOKEN"),
            HF_API_KEY=_env("HF_API_KEY"),
            LLM_TIMEOUT=int(_env("LLM_TIMEOUT", "90")),
            LLM_RETRIES=int(_env("LLM_RETRIES", "2")),
            SLIDES_COUNT=int(_env("SLIDES_COUNT", "6")),
            FREE_TRIAL_GENERATIONS=int(_env("FREE_TRIAL_GENERATIONS", "2")),
            SUB_GENERATIONS_LIMIT=int(_env("SUB_GENERATIONS_LIMIT", "30")),
            SUB_PRICE_STARS=int(_env("SUB_PRICE_STARS", "250")),
            SUB_DAYS=int(_env("SUB_DAYS", "30")),
            MAX_TOPIC_LENGTH=int(_env("MAX_TOPIC_LENGTH", "300")),
            MAX_FIELD_LENGTH=int(_env("MAX_FIELD_LENGTH", "1200")),
            DATABASE_URL=_env("DATABASE_URL", DEFAULT_DATABASE_URL),
            RENDER_OUTPUT_DIR=render_dir,
            RENDER_CONCURRENCY=int(_env("RENDER_CONCURRENCY", "1")),
            SEND_MEDIA_MODE=_env("SEND_MEDIA_MODE", "photo"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
