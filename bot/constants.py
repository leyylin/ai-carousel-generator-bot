# Neutral demo values. Replace them with the real brand of your client.
BUSINESS_NAME = "STUDIO / CAROUSEL"
DEFAULT_HANDLE = "@your_brand"
EXAMPLE_HANDLE = "@your_brand"

NICHES = {
    "manicure": {
        "title": "Маникюр и педикюр",
        "hint": "manicure, pedicure, nail design, gel polish, nail care",
    },
    "brows_lashes": {
        "title": "Брови и ресницы",
        "hint": "eyebrow shaping, lamination, tinting, eyelash extensions, lash care",
    },
    "cosmetology": {
        "title": "Косметология и уход",
        "hint": "facial care, cosmetology treatments, skin glow, hydration, cleansing",
    },
    "keratin": {
        "title": "Кератин и реконструкция волос",
        "hint": "keratin treatment, hair reconstruction, smooth shiny hair, hair care",
    },
    "hair_color": {
        "title": "Парикмахерские услуги и колористика",
        "hint": "haircut, coloring, balayage, highlights, salon styling, hair color",
    },
    "makeup": {
        "title": "Макияж и визаж",
        "hint": "makeup artistry, evening makeup, bridal makeup, skin prep, makeup details",
    },
}

THEMES = {
    "editorial": "Журнальный",
    "matte_cards": "Матовый нуар",
    "minimal": "Минимализм",
}

THEME_ORDER = ("editorial", "matte_cards", "minimal")
DEFAULT_THEME = "editorial"

FIELD_LABELS = {
    "badge": "Бейдж",
    "title": "Заголовок",
    "subtitle": "Подзаголовок",
    "body": "Основной текст",
    "highlight_box": "Блок «Решение»",
    "cta_button": "Текст кнопки",
}


def next_theme(theme: str) -> str:
    try:
        index = THEME_ORDER.index(theme)
    except ValueError:
        return DEFAULT_THEME
    return THEME_ORDER[(index + 1) % len(THEME_ORDER)]


def fields_for_slide(index: int, total: int) -> list[str]:
    if index == 0:
        return ["badge", "title", "subtitle", "cta_button"]
    if index == total - 1:
        return ["badge", "title", "body", "cta_button"]
    return ["badge", "title", "body", "highlight_box"]
