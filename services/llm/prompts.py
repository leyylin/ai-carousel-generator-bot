from __future__ import annotations

import re

SYSTEM_PROMPT = """Ты — senior SMM-редактор и эксперт по бьюти-индустрии.
Ты создаёшь продающие Instagram-карусели на русском языке для мастеров красоты.

Жёсткие правила:
1. Верни ТОЛЬКО валидный JSON без markdown, без code fences и без пояснений.
2. Ровно {slides_count} слайдов в массиве slides.
3. Слайд 1 — обложка: badge (рубрика), title с одним ключевым словом в теге <em>...</em>, subtitle, cta_button, image_prompt.
4. Слайды 2–{last_content} — контент: badge (например, "ПРИЧИНА №1"), title, body (2–4 предложения), highlight_box, image_prompt.
5. Слайд {last} — финал и CTA: badge ("ИТОГ И ЗАПИСЬ"), title, body, cta_button ("Записаться в Директ"), image_prompt.
6. highlight_box всегда начинай с "Решение: ".
7. image_prompt — только на английском, фотореалистичный, вертикальный, без текста, логотипов и водяных знаков.
8. Визуальные роли слайдов:
   - Слайд 1: красивый портрет или эстетичный фокус на теме поста, профессиональный свет.
   - Слайды 2–{last_content}, кроме предпоследнего: только предметная макросъемка — инструменты, баночки, текстуры, капли, мягкое боке. Без людей, лиц и рук.
   - Предпоследний слайд: уютная атмосфера ухода, спа-мотивы или минималистичный интерьер. Без людей.
   - Последний слайд: эстетичный премиальный результат. Без людей, лиц и рук.
9. image_prompt каждого слайда ДОЛЖЕН быть уникальным: разные объекты, ракурсы и планы. Не повторяй один и тот же портрет, сцену или описание.
10. В каждый image_prompt добавляй: high quality, sharp focus, professional photography, clean composition.
11. Тексты живые, экспертные, без воды, без медицинских гарантий и обещаний.
12. В JSON не добавляй никаких других полей.

Схема ответа:
{{
  "topic": "тема поста",
  "niche": "название ниши",
  "slides": [
    {{
      "badge": "РУБРИКА",
      "title": "Заголовок с <em>акцентом</em>",
      "subtitle": "Подзаголовок",
      "body": "",
      "highlight_box": "",
      "cta_button": "Листай дальше →",
      "image_prompt": "vertical beauty still life, high quality, sharp focus, ..."
    }}
  ]
}}"""


QUALITY_ENDING = (
    "high quality, sharp focus, professional photography, clean composition, "
    "realistic textures, refined color grading, premium beauty campaign, "
    "no text, no logos, no watermark"
)

OBJECT_ENDING = (
    "object-only still life, no people, no hands, no faces, no visible skin, "
    f"{QUALITY_ENDING}"
)

COVER_ENDING = (
    "single elegant subject, distinctive natural facial features, "
    "natural facial proportions, realistic skin texture, no beauty filter, "
    "hands out of frame, refined editorial styling, no distorted anatomy, "
    "no text, no logos, no watermark, high quality, sharp focus, "
    "professional photography, clean composition"
)

COVER_UNSAFE_RE = re.compile(
    r"\b(hands?|fingers?|holding|applying|massage|nails?|manicure|pedicure|"
    r"cuticle|over[- ]the[- ]shoulder)\b",
    re.IGNORECASE,
)

COVER_VARIATIONS = (
    "three-quarter portrait, eye-level, natural expression, shallow depth of field",
    "beauty close-up, face turned slightly away, soft rim light, minimal styling",
    "editorial portrait with generous negative space, quiet luxury mood",
    "beauty detail, face partially out of frame, tactile skin texture and highlight",
)

OBJECT_VARIATIONS = (
    "top-down flat lay composition, generous negative space",
    "45-degree macro angle, creamy bokeh background",
    "eye-level hero composition, tactile details in the foreground",
    "slightly elevated angle, delicate shadows and clean negative space",
    "close crop emphasizing texture, shallow depth of field",
    "minimal wide composition, subject slightly off-center",
)

AMBIENT_VARIATIONS = (
    "minimal wide composition, generous negative space",
    "eye-level interior composition, soft shadows and warm light",
    "slightly elevated angle, calm room overview",
)

FINAL_VARIATIONS = (
    "minimal wide composition, subject slightly off-center",
    "eye-level hero composition, polished details in focus",
    "close crop on the finished detail, clean background",
)

MIDDLE_VISUAL_ROLES = (
    "macro_tools",
    "macro_texture",
    "process_detail",
    "workspace",
)

ROLE_SCENES = {
    "macro_tools": (
        "extreme macro vertical still life of professional tools for {niche}, "
        "sterile metal instruments and a glass dropper arranged on a smooth stone tray, "
        "precise edges, soft side light, shallow depth of field, creamy bokeh"
    ),
    "macro_texture": (
        "extreme macro vertical still life of beauty products for {niche}, "
        "serum droplets on glass, creamy texture swatch on a glass surface, "
        "glossy bottles, water beads, tactile details, soft directional light, "
        "shallow depth of field, elegant bokeh"
    ),
    "process_detail": (
        "vertical editorial still life of a prepared treatment station for {niche}, "
        "sterile tools, amber glass bottles, folded linen towel, ceramic bowl, "
        "fresh eucalyptus, soft window light, clean composition"
    ),
    "workspace": (
        "vertical editorial still life of a minimalist workspace for {niche}, "
        "tools in a ceramic holder, linen towels, warm lamp, green plant, "
        "quiet luxury atmosphere, clean negative space"
    ),
    "care": (
        "vertical atmospheric still life of a serene spa room for {niche}, "
        "folded waffle towels, lit candles, ceramic cups, eucalyptus branches, "
        "warm diffused light, soft shadows, calm relaxing mood"
    ),
}

FINAL_SCENE = (
    "vertical premium beauty result still life, flawless finish inspired by {niche}, "
    "perfectly styled details, polished surfaces, fresh flowers, sculptural glass, "
    "clean minimal background, soft studio light, luxury campaign visual"
)


def visual_role(index: int, total: int) -> str:
    if index <= 0:
        return "cover"
    if index >= total - 1:
        return "final"
    if index == total - 2:
        return "care"
    return MIDDLE_VISUAL_ROLES[(index - 1) % len(MIDDLE_VISUAL_ROLES)]


def _stable_index(seed: str, size: int) -> int:
    return sum((position + 1) * ord(char) for position, char in enumerate(seed)) % size


def _format_niche(niche_hint: str) -> str:
    parts = [part.strip() for part in (niche_hint or "").split(",") if part.strip()]
    return ", ".join(parts[:3]) or "beauty"


def build_visual_prompt(
    index: int,
    total: int,
    niche_hint: str,
    llm_prompt: str = "",
) -> str:
    niche = _format_niche(niche_hint)
    role = visual_role(index, total)

    if role == "cover":
        original = (llm_prompt or "").strip().rstrip(" .,")
        if not original or COVER_UNSAFE_RE.search(original):
            original = ""
        scene = original or (
            f"cinematic vertical beauty portrait inspired by {niche}, "
            "one elegant subject with luminous natural skin, refined makeup, "
            "serene expression, soft rim light, clean minimal background"
        )
        variation = COVER_VARIATIONS[_stable_index(f"{niche}|{scene}", len(COVER_VARIATIONS))]
        return f"{scene}, {variation}, {COVER_ENDING}"

    if role == "final":
        scene = FINAL_SCENE.format(niche=niche)
        variation = FINAL_VARIATIONS[index % len(FINAL_VARIATIONS)]
        return f"{scene}, {variation}, {OBJECT_ENDING}"

    scene = ROLE_SCENES[role].format(niche=niche)
    variations = (
        AMBIENT_VARIATIONS if role in {"workspace", "care"} else OBJECT_VARIATIONS
    )
    variation = variations[index % len(variations)]
    return f"{scene}, {variation}, {OBJECT_ENDING}"


def build_visual_prompts(
    total: int,
    niche_hint: str,
    llm_prompts: list[str] | None = None,
) -> list[str]:
    prompts = list(llm_prompts or [])
    return [
        build_visual_prompt(
            index=index,
            total=total,
            niche_hint=niche_hint,
            llm_prompt=prompts[index] if index < len(prompts) else "",
        )
        for index in range(total)
    ]


def build_messages(
    topic: str,
    niche_title: str,
    niche_hint: str,
    slides_count: int,
) -> list[dict[str, str]]:
    last = slides_count
    last_content = slides_count - 1
    system = SYSTEM_PROMPT.format(
        slides_count=slides_count,
        last=last,
        last_content=last_content,
    )
    if topic.strip():
        topic_instruction = f"Тема поста: {topic.strip()}"
    else:
        topic_instruction = (
            "Тема не задана. Придумай сильную вирусную тему для этой ниши "
            "и укажи её в поле topic."
        )
    user = f"""Ниша: {niche_title}
Подсказка для визуала: {niche_hint}
{topic_instruction}

Сделай структуру из {slides_count} слайдов: обложка, {slides_count - 2} контентных слайда и финал с призывом записаться.
Верни только JSON по схеме."""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
