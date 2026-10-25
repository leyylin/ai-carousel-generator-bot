from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SlideContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    badge: str = ""
    title: str = ""
    subtitle: str = ""
    body: str = ""
    highlight_box: str = ""
    cta_button: str = ""
    image_prompt: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def normalize_strings(cls, value):
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value.strip()
        return value


class CarouselContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: str = ""
    niche: str = ""
    slides: list[SlideContent] = Field(min_length=5, max_length=7)

    @field_validator("topic", "niche", mode="before")
    @classmethod
    def normalize_meta(cls, value):
        return "" if value is None else str(value).strip()
