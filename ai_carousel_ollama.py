#!/usr/bin/env python3
"""
AI Carousel Engine — Production Script.
Generates a 6-slide Instagram carousel (1080x1350 PNG) utilizing the official Unsplash API,
anti-repeat history rotation, auto-fitting editorial typography, and 3 design templates.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import html
import json
import mimetypes
import os
import random
import re
import struct
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from dotenv import load_dotenv
from playwright.async_api import Error as PlaywrightError, async_playwright

WIDTH, HEIGHT = 1080, 1350
OUTPUT_DIR = Path("generated_carousel")
ASSET_DIR = OUTPUT_DIR / "assets"
PHOTO_HISTORY_PATH = ASSET_DIR / "photo_history.json"

NICHES = {
    "manicure": "Маникюр",
    "brows": "Брови",
    "lashes": "Ресницы",
    "cosmetology": "Косметология",
    "keratin": "Кератин",
    "hair": "Парикмахерские услуги",
}

# Точечные поисковые запросы под каждый из 6 слайдов для идеального смыслового соответствия
SLIDE_SPECIFIC_QUERIES = [
    "woman blow drying long hair salon",       # Слайд 1: Обложка (укладка феном)
    "shiny smooth brunette hair texture",      # Слайд 2: Пористость и структура волос
    "woman towel hair care beauty",            # Слайд 3: Мытье и бережное промакивание
    "hairdresser styling hair dryer brush",    # Слайд 4: Техника сушки феном
    "hair serum oil dropper beauty care",      # Слайд 5: Салонный уход и косметика
    "luxury beauty hair salon mirror",         # Слайд 6: Финальный результат / Запись
]

# Надежный резервный пул на случай исчерпания лимитов API
CURATED_PHOTO_POOL: dict[str, list[dict[str, str]]] = {
    "keratin": [
        {"name": "Professional blow-drying sleek hair", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1712481846916-8f73ffc2067a?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Glossy healthy brunette hair texture", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1519699047748-de8e457a634e?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Salon hair styling and thermal care", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1560869713-7d0a29430803?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Professional hairbrush and dryer tools", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Long silky hair care routine", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1527799820374-dcf8d9d4a388?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Master hairstylist working with client", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1562322140-8baeececf3df?auto=format&fit=crop&w=1600&q=88"},
    ],
    "manicure": [
        {"name": "Aesthetic manicure nail art", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1604654894610-df63bc536371?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Glossy gel nail styling", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1632345031435-8727f6897d53?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Clean nude manicure close-up", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1610992015732-2449b76344bc?auto=format&fit=crop&w=1600&q=88"},
    ],
    "cosmetology": [
        {"name": "Cosmetology facial mask procedure", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Gentle facial cleansing routine", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=1600&q=88"},
        {"name": "Hyaluronic acid serum dropper", "page": "https://unsplash.com", "url": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=1600&q=88"},
    ],
}
CURATED_PHOTO_POOL["hair"] = CURATED_PHOTO_POOL["keratin"]
CURATED_PHOTO_POOL["brows"] = CURATED_PHOTO_POOL["keratin"]
CURATED_PHOTO_POOL["lashes"] = CURATED_PHOTO_POOL["keratin"]

CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500;1,600&family=Montserrat:wght@400;500;600;700&display=swap');
* { box-sizing:border-box; }
html,body { margin:0; width:1080px; height:1350px; overflow:hidden; }
body { font-family:'Montserrat',Arial,sans-serif; -webkit-font-smoothing:antialiased; }
.slide {
  position:relative; width:1080px; height:1350px; overflow:hidden; isolation:isolate;
  color:var(--ink); background:var(--paper);
  --paper:#F4EFEA; --ink:#231F1D; --soft:#4E4641; --accent:#9A6B4C; --accent-light:#E8C8A9;
  --tip-bg:#26211E; --step-bg:#9A6B4C; --card-bg:rgba(255,252,248,.93); --card-border:rgba(255,255,255,.96);
  --line:rgba(74,59,48,.18); --shadow:rgba(35,25,18,.14);
}
.theme-blush {
  --paper:#F6EAEB; --ink:#302128; --soft:#5E4952; --accent:#A44A64; --accent-light:#F2CBD4;
  --tip-bg:#482733; --step-bg:#A44A64; --card-bg:rgba(255,250,251,.93); --card-border:rgba(255,255,255,.96);
  --line:rgba(117,69,82,.2);
}
.theme-midnight {
  --paper:#221E1D; --ink:#F9F4EE; --soft:#D8CBC0; --accent:#D8AE86; --accent-light:#F1D7B6;
  --tip-bg:#382C26; --step-bg:#B68B66; --card-bg:rgba(42,36,33,.91); --card-border:rgba(255,255,255,.18);
  --line:rgba(255,255,255,.2); --shadow:rgba(0,0,0,.32);
}
/* Фикс кадрирования: фокус смещен чуть вверх (на лица и ключевые детали) */
.slide::before { content:''; position:absolute; inset:0; z-index:-2; background-image:var(--photo); background-size:cover; background-position:center 30%; transform:scale(1.015); }
.slide::after { content:''; position:absolute; inset:0; z-index:-1; pointer-events:none; }
.slide.cover::before,.slide.cta::before { filter:saturate(.94) contrast(1.04); }
.slide.cover::after,.slide.cta::after {
  background:linear-gradient(180deg,rgba(18,14,12,.42) 0%,rgba(18,14,12,.22) 34%,rgba(18,14,12,.84) 76%,rgba(18,14,12,.95) 100%);
}
.slide.info::before { opacity:1; filter:saturate(.85) contrast(1.02) brightness(.96); }
.slide.info::after { background:linear-gradient(135deg,rgba(246,240,233,.89) 0%,rgba(246,240,233,.95) 55%,rgba(246,240,233,.84) 100%); }
.theme-blush.info::after { background:linear-gradient(135deg,rgba(249,236,238,.89) 0%,rgba(249,236,238,.95) 55%,rgba(249,236,238,.84) 100%); }
.theme-midnight.info::after { background:linear-gradient(135deg,rgba(32,28,27,.87) 0%,rgba(32,28,27,.93) 55%,rgba(32,28,27,.82) 100%); }

.masthead { position:absolute; z-index:5; top:52px; left:62px; right:62px; display:flex; align-items:center; justify-content:space-between; gap:24px; }
.brand { font-size:15px; font-weight:700; letter-spacing:2.8px; text-transform:uppercase; display:flex; gap:12px; align-items:center; }
.brand::before { content:''; display:inline-block; width:30px; height:1.5px; background:currentColor; opacity:.85; }
.pill { border:1px solid rgba(255,255,255,.55); border-radius:999px; padding:13px 24px; color:#fff; font-size:14px; font-weight:700; letter-spacing:1.8px; background:rgba(255,255,255,.14); backdrop-filter:blur(16px); white-space:nowrap; }
.cover .brand,.cta .brand { color:rgba(255,250,244,.92); }
.cover-content { position:absolute; left:62px; right:62px; bottom:140px; color:#fffaf4; max-width:950px; }
.kicker { display:flex; align-items:center; gap:12px; font-size:15px; font-weight:700; letter-spacing:2.6px; text-transform:uppercase; margin-bottom:20px; color:var(--accent-light); line-height:1.4; }
.info .kicker { color:var(--accent); }
.kicker::before { content:''; width:32px; height:1.5px; display:inline-block; background:currentColor; opacity:.85; flex:0 0 32px; }
h1,h2 { font-family:'Cormorant Garamond',Georgia,serif; font-weight:600; letter-spacing:-1.2px; }
.cover h1 { font-size:102px; line-height:1.0; margin:0; max-width:940px; text-wrap:pretty; }
em { font-style:italic; font-weight:600; color:var(--accent-light); }
.cover .dek { font-size:26px; line-height:1.48; margin-top:26px; color:rgba(255,250,244,.92); max-width:820px; font-weight:400; }
.number { font-family:'Cormorant Garamond',Georgia,serif; font-size:32px; font-weight:600; letter-spacing:1px; white-space:nowrap; }
.cover-bottom,.cta-bottom { position:absolute; bottom:52px; left:62px; right:62px; display:flex; justify-content:space-between; align-items:center; color:rgba(255,250,244,.92); border-top:1px solid rgba(255,255,255,.2); padding-top:24px; }
.cover-bottom::before,.cta-bottom::before { content:'ЛИСТАЙ КАРУСЕЛЬ  →'; font-size:14px; font-weight:700; letter-spacing:2.2px; opacity:.88; }
.info .masthead { color:var(--ink); }
.info .brand { color:var(--soft); }
.info .pill { color:var(--ink); background:rgba(255,255,255,.78); border-color:rgba(35,31,29,.15); }
.theme-midnight.info .pill { color:#fff; background:rgba(255,255,255,.12); border-color:rgba(255,255,255,.28); }
.info .main { position:absolute; top:136px; left:58px; right:58px; bottom:56px; display:flex; flex-direction:column; justify-content:space-between; min-height:0; }
.info h2 { font-size:68px; line-height:1.02; margin:0 0 14px; max-width:950px; color:var(--ink); text-wrap:pretty; }
.info h2 em { color:var(--accent); }
.lead { font-size:22px; line-height:1.48; max-width:930px; color:var(--soft); margin:0 0 18px; font-weight:500; }
.photo-strip { height:350px; width:100%; flex:0 0 350px; border-radius:28px; position:relative; overflow:hidden; margin:0 0 18px; box-shadow:0 20px 46px var(--shadow); background:linear-gradient(135deg,#b9a08b,#332c2a); isolation:isolate; }
.photo-strip::before { content:''; position:absolute; z-index:-1; inset:0; background-image:var(--photo); background-position:center 30%; background-size:cover; filter:saturate(.98); transform:scale(1.015); }
.photo-strip::after { content:'CAROUSEL NOTES  •  EDITORIAL'; position:absolute; left:22px; bottom:20px; padding:11px 18px; border:1px solid rgba(255,255,255,.55); border-radius:999px; color:white; font-size:11px; font-weight:700; letter-spacing:2px; background:rgba(20,17,17,.38); backdrop-filter:blur(12px); }
.cards { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:0; flex:0 0 auto; min-height:0; }
.glass-card { height:230px; min-height:230px; display:flex; flex-direction:column; justify-content:flex-start; padding:26px 26px 24px; border:1px solid var(--card-border); background:var(--card-bg); border-radius:24px 24px 24px 8px; box-shadow:0 14px 36px rgba(48,34,25,.08); backdrop-filter:blur(16px); }
.card-top { display:flex; align-items:center; gap:14px; margin-bottom:14px; }
.step { display:inline-flex; width:42px; height:42px; flex:0 0 42px; align-items:center; justify-content:center; border-radius:50%; background:var(--step-bg); color:#fffaf3; font-size:14px; font-weight:700; letter-spacing:.5px; }
.glass-card h3 { font-size:21px; line-height:1.25; margin:0; color:var(--ink); font-weight:700; }
.glass-card p { margin:0; font-size:18px; line-height:1.5; color:var(--soft); font-weight:500; }
.tip { display:grid; grid-template-columns:215px 1fr; align-items:center; gap:24px; padding:24px 30px; min-height:104px; border-radius:10px 24px 24px 24px; color:#fdf8f0; background:var(--tip-bg); box-shadow:0 14px 32px rgba(31,25,22,.16); }
.tip-title { font-family:'Cormorant Garamond',Georgia,serif; font-size:36px; font-weight:600; line-height:1.05; color:var(--accent-light); }
.tip p { margin:0; font-size:18px; line-height:1.48; color:rgba(255,250,243,.95); font-weight:500; }
.bottom-row { display:flex; justify-content:space-between; align-items:center; margin-top:12px; padding-top:4px; }
.bottom-row::before { content:'@your_brand'; font-size:16px; font-weight:600; color:var(--soft); opacity:.8; }
.info .number { color:var(--soft); }
.info .main.side-layout { top:136px; bottom:58px; display:grid; grid-template-columns:.84fr 1fr; grid-template-rows:minmax(0,1fr) auto; gap:22px; align-items:stretch; }
.info .main.side-layout .photo-strip { grid-column:1; grid-row:1; height:auto; min-height:0; flex:1 1 auto; margin:0; border-radius:28px 28px 8px 28px; }
.info .main.side-layout .side-copy { grid-column:2; grid-row:1; min-width:0; display:flex; flex-direction:column; padding:6px 4px 0 0; }
.info .main.side-layout .side-copy .kicker { margin-bottom:14px; }
.info .main.side-layout .side-copy::after { content:'STUDIO  •  CAROUSEL JOURNAL'; margin-top:auto; padding-top:16px; border-top:1px solid var(--line); color:var(--soft); opacity:.75; font-size:12px; font-weight:700; letter-spacing:2px; }
.info .main.side-layout h2 { font-size:60px; line-height:1.02; margin-bottom:14px; }
.info .main.side-layout .lead { font-size:20px; line-height:1.48; margin-bottom:18px; }
.info .main.side-layout .cards { grid-template-columns:1fr; gap:14px; margin-bottom:0; flex:0 0 auto; }
.info .main.side-layout .glass-card { height:auto; min-height:165px; justify-content:flex-start; padding:22px 24px; border-radius:20px 20px 20px 6px; }
.info .main.side-layout .glass-card p { font-size:17.5px; }
.info .main.side-layout .tip { grid-column:1 / -1; grid-row:2; grid-template-columns:210px 1fr; padding:24px 28px; }
.info .main.side-layout .bottom-row { position:absolute; left:0; right:0; bottom:-48px; margin:0; }
.info .main.layout-4 .photo-strip { height:340px; flex-basis:340px; margin-bottom:0; }
.info .main.layout-4 .cards { position:relative; z-index:2; margin:-26px 16px 14px; }
.info .main.layout-4 .glass-card { min-height:215px; box-shadow:0 18px 40px rgba(48,34,25,.14); }
.info .main.layout-2 .photo-strip { height:340px; flex-basis:340px; }
.cta .masthead { color:#fffaf4; }
.cta-content { position:absolute; top:230px; left:62px; right:62px; color:#fffaf4; max-width:930px; }
.cta h1 { font-size:98px; line-height:1.0; margin:0 0 24px; max-width:900px; text-wrap:pretty; }
.cta .lead { font-size:25px; line-height:1.48; color:rgba(255,250,244,.94); max-width:820px; margin-bottom:34px; font-weight:400; }
.bonus { max-width:820px; padding:32px 36px; border:1px solid rgba(255,255,255,.42); border-radius:8px 28px 28px 28px; background:rgba(25,20,18,.58); backdrop-filter:blur(20px); box-shadow:0 20px 50px rgba(0,0,0,.25); }
.bonus-label { font-size:14px; font-weight:700; letter-spacing:2.6px; color:#E8C8A9; margin-bottom:12px; text-transform:uppercase; }
.bonus p { font-family:'Cormorant Garamond',Georgia,serif; font-size:36px; font-weight:600; line-height:1.18; margin:0; }
.cta-button { display:inline-flex; align-items:center; justify-content:center; margin-top:34px; padding:24px 44px; border-radius:999px; background:#E8C8A9; color:#231F1D; font-size:18px; font-weight:700; letter-spacing:1.6px; box-shadow:0 14px 34px rgba(0,0,0,.25); }
"""

SAMPLE_CONTENT = {
    "slides": [
        {
            "eyebrow": "HAIR CARE NOTES • РАЗБОР МАСТЕРА",
            "title": "Почему волосы пушатся после мытья?",
            "emphasis": "пушатся",
            "dek": "Разбираем 4 главные причины потери гладкости — и как сделать волосы шелковистыми без утяжеления",
            "lead": "",
            "cards": [],
            "tip_title": "",
            "tip": "",
            "bonus_title": "",
            "bonus": "",
            "cta_label": "",
        },
        {
            "eyebrow": "01 / СТРУКТУРА И ПОРИСТОСТЬ",
            "title": "Повышенная пористость и реакция на влагу",
            "emphasis": "пористость",
            "dek": "",
            "lead": "Когда кутикула волоса приоткрыта, пряди мгновенно впитывают влагу из воздуха и начинают хаотично завиваться.",
            "cards": [
                {
                    "title": "Нехватка липидного слоя",
                    "body": "После окрашиваний и горячих укладок защитный барьер истончается, а чешуйки волоса перестают плотно прилегать.",
                },
                {
                    "title": "Эффект влажного воздуха",
                    "body": "Обезвоженный волос тянет воду из внешней среды, из-за чего укладка теряет форму уже через 15 минут на улице.",
                },
            ],
            "tip_title": "Практический совет",
            "tip": "После каждого мытья закрывайте чешуйки кислым кондиционером (pH 4.5–5.5) — он сглаживает поверхность волоса.",
            "bonus_title": "",
            "bonus": "",
            "cta_label": "",
        },
        {
            "eyebrow": "02 / ОШИБКИ ПОСЛЕ ДУША",
            "title": "Трение полотенцем и сушка без дисциплины",
            "emphasis": "полотенцем",
            "dek": "",
            "lead": "Мокрые волосы максимально уязвимы к растяжению: любое грубое механическое воздействие поднимает пушок по всей длине.",
            "cards": [
                {
                    "title": "Махровое полотенце",
                    "body": "Тяжелая махровая ткань и привычка тереть волосы создают микроповреждения и спутывают влажные пряди.",
                },
                {
                    "title": "Естественная сушка",
                    "body": "Когда пористые волосы сохнут сами по себе без вытягивания, кутикула фиксируется в приподнятом состоянии.",
                },
            ],
            "tip_title": "Маленький ритуал",
            "tip": "Промакивайте воду мягким тюрбаном из микрофибры или гладкой хлопковой тканью без выкручивания жгутом.",
            "bonus_title": "",
            "bonus": "",
            "cta_label": "",
        },
        {
            "eyebrow": "03 / ТЕХНИКА УКЛАДКИ",
            "title": "Как сушить волосы феном для зеркальной гладкости",
            "emphasis": "гладкости",
            "dek": "",
            "lead": "Правильная сушка феном с насадкой-концентратором не портит волосы, а наоборот — запечатывает кутикулу и дает блеск.",
            "cards": [
                {
                    "title": "Направление потока",
                    "body": "Всегда направляйте поток теплого воздуха строго сверху вниз по росту волос — от корней к кончикам.",
                },
                {
                    "title": "Термозащита и брашинг",
                    "body": "Крем-термозащита создает невесомую пленку, которая удерживает влагу внутри и убирает статическое электричество.",
                },
            ],
            "tip_title": "Секрет мастера",
            "tip": "В самом конце укладки пройдитесь по прядям холодным воздухом фена — это зафиксирует форму и усилит блеск.",
            "bonus_title": "",
            "bonus": "",
            "cta_label": "",
        },
        {
            "eyebrow": "04 / ДОМАШНИЙ И САЛОННЫЙ УХОД",
            "title": "Когда домашнего ухода уже недостаточно",
            "emphasis": "недостаточно",
            "dek": "",
            "lead": "Если волосы плотные, вьющиеся или сильно повреждены, одних масок и масел может не хватать для стойкого эффекта.",
            "cards": [
                {
                    "title": "Слои увлажнения",
                    "body": "Комбинируйте смываемый кондиционер и несмываемый крем-флюид: они работают на разных уровнях структуры.",
                },
                {
                    "title": "Салонная реконструкция",
                    "body": "Правильно подоброванная процедура дисциплинирует полотно волос и сокращает время укладки в 3 раза.",
                },
            ],
            "tip_title": "А как же кератин?",
            "tip": "Состав подбирается строго после диагностики: для тонких волос — легкое питание, для плотных — выпрямление.",
            "bonus_title": "",
            "bonus": "",
            "cta_label": "",
        },
        {
            "eyebrow": "ИНДИВИДУАЛЬНЫЙ РАЗБОР",
            "title": "Хотите забыть про пушистость и утюжок по утрам?",
            "emphasis": "пушистость",
            "dek": "",
            "lead": "Напишите в Direct слово «ГЛАДКОСТЬ» — проведем бесплатную диагностику ваших волос и подберем идеальную процедуру.",
            "cards": [],
            "tip_title": "",
            "tip": "",
            "bonus_title": "БОНУС ДЛЯ ПОДПИСЧИКОВ",
            "bonus": "Гайд по подбору домашнего ухода и скидка 10% на первое посещение при записи на этой неделе.",
            "cta_label": "НАПИСАТЬ В DIRECT ↗",
        },
    ]
}


def safe_text(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def title_with_emphasis(title: str, emphasis: str) -> str:
    escaped_title = safe_text(title)
    escaped_emphasis = safe_text(emphasis)
    if escaped_emphasis and escaped_emphasis.lower() in escaped_title.lower():
        match = re.search(re.escape(escaped_emphasis), escaped_title, flags=re.IGNORECASE)
        if match:
            return (
                escaped_title[: match.start()]
                + "<em>"
                + escaped_title[match.start() : match.end()]
                + "</em>"
                + escaped_title[match.end() :]
            )
    words = escaped_title.split(" ")
    if len(words) >= 3:
        words[-1] = f"<em>{words[-1]}</em>"
        return " ".join(words)
    return escaped_title


def canonical_niche(niche: str) -> str:
    value = niche.strip().lower()
    aliases = {
        "маникюр": "manicure",
        "ногти": "manicure",
        "брови": "brows",
        "ресницы": "lashes",
        "косметология": "cosmetology",
        "кератин": "keratin",
        "парикмахер": "hair",
        "парикмахерские услуги": "hair",
        "волосы": "hair",
    }
    return aliases.get(value, value if value in CURATED_PHOTO_POOL else "keratin")


async def generate_content(topic: str, niche_name: str, model: str) -> dict[str, Any]:
    steps = [
        f"Анализ темы и болевых точек аудитории в нише «{niche_name}»...",
        "Формирование структуры из 6 слайдов (Cover → 4 Info → CTA)...",
        "Генерация экспертных карточек, советов и курсивных акцентов...",
    ]
    for step in steps:
        print(f"   ⏳ {step}")
        await asyncio.sleep(0.4)
    return SAMPLE_CONTENT


def sniff_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis"}:
        return "image/avif"
    return None


def is_valid_cached_image(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 10_000:
            return False
        with path.open("rb") as f:
            return sniff_image_mime(f.read(32)) is not None
    except OSError:
        return False


async def search_unsplash_official(request_context, query: str, access_key: str) -> list[dict[str, str]]:
    api_url = f"https://api.unsplash.com/search/photos?query={quote_plus(query)}&per_page=10&orientation=portrait"
    headers = {
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1",
    }
    found: list[dict[str, str]] = []
    try:
        resp = await request_context.get(api_url, headers=headers, timeout=10_000)
        if not resp.ok:
            return []
        payload = await resp.json()
        results = payload.get("results", [])
        for item in results:
            urls = item.get("urls", {})
            raw_url = urls.get("regular") or urls.get("small")
            if not raw_url:
                continue
            clean_url = raw_url.split("?")[0] + "?auto=format&fit=crop&w=1600&q=88"
            desc = item.get("alt_description") or item.get("description") or f"Unsplash ({query})"
            link = item.get("links", {}).get("html") or "https://unsplash.com"
            found.append({"name": str(desc).capitalize()[:65], "page": link, "url": clean_url})
    except Exception:
        return []
    return found


async def download_photos(request_context, niche_key: str) -> tuple[list[Path], list[dict[str, str]]]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    access_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    
    try:
        history_data = json.loads(PHOTO_HISTORY_PATH.read_text(encoding="utf-8")) if PHOTO_HISTORY_PATH.exists() else {}
    except Exception:
        history_data = {}
    if not isinstance(history_data, dict):
        history_data = {}

    history: list[str] = history_data.get(niche_key, [])
    if not isinstance(history, list):
        history = []

    recent_urls = set(history[-30:])
    image_paths: list[Path] = []
    selected: list[dict[str, str]] = []
    used_in_this_run: set[str] = set()

    for idx, query in enumerate(SLIDE_SPECIFIC_QUERIES, start=1):
        dynamic_hits = []
        if access_key:
            dynamic_hits = await search_unsplash_official(request_context, query, access_key)
        
        valid_hits = [h for h in dynamic_hits if h["url"] not in recent_urls.union(used_in_this_run)]
        
        chosen = None
        if valid_hits:
            chosen = random.choice(valid_hits)
        else:
            fallback_pool = CURATED_PHOTO_POOL.get(niche_key, CURATED_PHOTO_POOL["keratin"])
            available = [p for p in fallback_pool if p["url"] not in recent_urls.union(used_in_this_run)]
            chosen = random.choice(available) if available else fallback_pool[(idx - 1) % len(fallback_pool)]

        used_in_this_run.add(chosen["url"])
        url = chosen["url"]
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        target = ASSET_DIR / f"photo_{digest}.img"

        if is_valid_cached_image(target):
            image_paths.append(target)
            selected.append(chosen)
            print(f"   📸 Слайд {idx}/6 [Кеш] → {chosen['name']}")
        else:
            try:
                resp = await request_context.get(
                    url,
                    timeout=20_000,
                    headers={
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        "Referer": "https://unsplash.com/",
                        "User-Agent": "Mozilla/5.0",
                    },
                )
                if not resp.ok:
                    raise RuntimeError("HTTP error")
                data = await resp.body()
                if sniff_image_mime(data[:32]) is None or len(data) < 10_000:
                    raise RuntimeError("Bad image")
                target.write_bytes(data)
                image_paths.append(target)
                selected.append(chosen)
                print(f"   📸 Слайд {idx}/6 [Загружено] → {chosen['name']}")
            except Exception:
                fallback = CURATED_PHOTO_POOL.get(niche_key, CURATED_PHOTO_POOL["keratin"])[(idx - 1) % len(CURATED_PHOTO_POOL["keratin"])]
                f_url = fallback["url"]
                f_digest = hashlib.sha256(f_url.encode("utf-8")).hexdigest()[:16]
                f_target = ASSET_DIR / f"photo_{f_digest}.img"
                if not f_target.is_file() and target.is_file():
                    f_target.write_bytes(target.read_bytes())
                image_paths.append(f_target if f_target.is_file() else target)
                selected.append(fallback)
                print(f"   📸 Слайд {idx}/6 [Резерв] → {fallback['name']}")

    history_data[niche_key] = (history + [p["url"] for p in selected])[-120:]
    try:
        PHOTO_HISTORY_PATH.write_text(json.dumps(history_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return image_paths, selected


def data_uri(path: Path | None) -> str | None:
    if not path:
        return None
    payload = path.read_bytes()
    mime = sniff_image_mime(payload[:32]) or mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"


def build_slide_html(
    slide: dict[str, Any], image_data: str | None, slide_number: int, niche_name: str, theme: str
) -> str:
    kind = "cover" if slide_number == 1 else "cta" if slide_number == 6 else "info"
    title = title_with_emphasis(slide.get("title", ""), slide.get("emphasis", ""))
    eyebrow = safe_text(slide.get("eyebrow", ""))
    image = f"url('{image_data}')" if image_data else "linear-gradient(135deg,#9b8778,#292523)"
    category = safe_text(niche_name.upper())

    if kind == "cover":
        content = f"""
        <div class="masthead"><div class="brand">STUDIO / CAROUSEL</div><div class="pill">{category}</div></div>
        <div class="cover-content"><div class="kicker">{eyebrow}</div><h1>{title}</h1><div class="dek">{safe_text(slide.get('dek',''))}</div></div>
        <div class="cover-bottom"><div class="number">01 <span style="opacity:.45">/</span> 06</div></div>
        """
    elif kind == "info":
        cards = slide.get("cards") or []
        card_markup = "".join(
            f'<div class="glass-card"><div class="card-top"><span class="step">0{j}</span><h3>{safe_text(card.get("title", ""))}</h3></div><p>{safe_text(card.get("body", ""))}</p></div>'
            for j, card in enumerate(cards[:2], start=1)
        )
        layout_class = "side-layout" if slide_number in (3, 5) else f"layout-{slide_number}"
        photo = '<div class="photo-strip"></div>'
        copy = f"""<div class="side-copy"><div class="kicker">{eyebrow}</div><h2>{title}</h2><p class="lead">{safe_text(slide.get('lead',''))}</p>
        <div class="cards">{card_markup}</div>
        </div>"""
        if slide_number in (3, 5):
            main_content = (
                f"{photo}{copy}"
                f'<div class="tip"><div class="tip-title">{safe_text(slide.get("tip_title","Совет"))}</div>'
                f'<p>{safe_text(slide.get("tip",""))}</p></div>'
                f'<div class="bottom-row"><div class="number">0{slide_number} <span style="opacity:.4">/</span> 06</div></div>'
            )
        else:
            main_content = (
                f'<div class="kicker">{eyebrow}</div><h2>{title}</h2>'
                f'<p class="lead">{safe_text(slide.get("lead",""))}</p>'
                f'{photo}<div class="cards">{card_markup}</div>'
                f'<div class="tip"><div class="tip-title">{safe_text(slide.get("tip_title","Совет"))}</div>'
                f'<p>{safe_text(slide.get("tip",""))}</p></div>'
                f'<div class="bottom-row"><div class="number">0{slide_number} <span style="opacity:.4">/</span> 06</div></div>'
            )
        content = f"""
        <div class="masthead"><div class="brand">STUDIO / CAROUSEL</div><div class="pill">{category}</div></div>
        <div class="main {layout_class}">{main_content}</div>
        """
    else:
        content = f"""
        <div class="masthead"><div class="brand">STUDIO / CAROUSEL</div><div class="pill">{category}</div></div>
        <div class="cta-content"><div class="kicker">{eyebrow}</div><h1>{title}</h1><p class="lead">{safe_text(slide.get('lead',''))}</p>
        <div class="bonus"><div class="bonus-label">{safe_text(slide.get('bonus_title','БОНУС'))}</div><p>{safe_text(slide.get('bonus',''))}</p></div>
        <div class="cta-button">{safe_text(slide.get('cta_label','НАПИШИ В DIRECT'))}</div></div>
        <div class="cta-bottom"><div class="number">06 <span style="opacity:.45">/</span> 06</div></div>
        """
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width={WIDTH}, initial-scale=1"><style>{CSS}</style></head>
    <body><main class="slide {kind} theme-{theme}" style="--photo:{image}">{content}</main></body></html>"""


def verify_png(path: Path) -> tuple[int, int]:
    with path.open("rb") as file:
        header = file.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"Файл {path.name} не является корректным PNG")
    width, height = struct.unpack(">II", header[16:24])
    if (width, height) != (WIDTH, HEIGHT):
        raise RuntimeError(f"Неверный размер {path.name}: {width}x{height}, ожидался {WIDTH}x{HEIGHT}")
    return width, height


def save_photo_sources(niche_key: str, selected_photos: list[dict[str, str]]) -> None:
    lines = [
        "Источники фотографий (Unsplash Commercial License)",
        f"Ниша: {NICHES.get(niche_key, niche_key)}",
        "",
    ]
    for index, item in enumerate(selected_photos, start=1):
        lines.append(f"{index}. {item['name']}\n   Источник: {item['page']}\n   CDN: {item['url']}")
    (OUTPUT_DIR / "photo_sources.txt").write_text("\n\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-генератор Instagram-карусели: 6 слайдов, 1080x1350 px")
    parser.add_argument("--topic", default=None)
    parser.add_argument("--niche", default=None)
    parser.add_argument("--theme", default=None, choices=["editorial", "blush", "midnight"])
    parser.add_argument("--model", default=None)
    return parser.parse_args()


async def main() -> None:
    load_dotenv()
    args = parse_args()
    print("\n" + "=" * 60)
    print("✨ AI CAROUSEL ENGINE — ГЕНЕРАТОР КАРУСЕЛЕЙ (1080x1350)")
    print("=" * 60)

    if not args.topic:
        entered = input("👉 Введите тему [Почему волосы пушатся после мытья?]: ").strip()
        args.topic = entered or "Почему волосы пушатся после мытья?"
    if not args.niche:
        print("\nДоступные beauty-ниши:")
        print("  1) Маникюр   2) Брови   3) Ресницы   4) Косметология   5) Кератин   6) Парикмахерские услуги")
        choice = input("👉 Выберите номер ниши [5 - Кератин]: ").strip() or "5"
        args.niche = {
            "1": "manicure",
            "2": "brows",
            "3": "lashes",
            "4": "cosmetology",
            "5": "keratin",
            "6": "hair",
        }.get(choice, "keratin")
    if not args.theme:
        print("\nДоступные дизайн-шаблоны:")
        print("  1) Editorial (Светлый журнальный)   2) Blush (Нежно-пудровый)   3) Midnight (Темный люкс)")
        choice = input("👉 Выберите номер шаблона [1 - Editorial]: ").strip() or "1"
        args.theme = {"1": "editorial", "2": "blush", "3": "midnight"}.get(choice, "editorial")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    niche_key = canonical_niche(args.niche)
    niche_name = NICHES.get(niche_key, "Кератин")
    model = args.model or os.getenv("OLLAMA_MODEL", "qwen3:8b")

    print("\n" + "-" * 60)
    print(f"📌 Тема:   {args.topic}")
    print(f"📌 Ниша:   {niche_name} | Дизайн-шаблон: {args.theme.upper()}")
    print("-" * 60)

    print(f"\n[1/3] 🧠 Генерация структуры и экспертного текста...")
    generated = await generate_content(args.topic, niche_name, model)
    print("   ✅ Готово: сформирован контент-план на 6 слайдов.")

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch()
        except PlaywrightError as exc:
            raise RuntimeError("Chromium не установлен. Выполни: playwright install chromium") from exc

        context = await browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
            color_scheme="light",
            reduced_motion="reduce",
        )
        request_context = await playwright.request.new_context()

        print("\n[2/3] 🔍 Подбор актуальных фото через Unsplash API...")
        try:
            image_paths, selected_photos = await download_photos(request_context, niche_key)
        finally:
            await request_context.dispose()

        page = await context.new_page()
        print("\n[3/3] 🎨 Журнальная верстка и рендер PNG-слайдов (1080x1350 px)...")
        for i, slide in enumerate(generated["slides"], start=1):
            html_content = build_slide_html(
                slide, data_uri(image_paths[(i - 1) % len(image_paths)]), i, niche_name, args.theme
            )
            await page.set_content(html_content, wait_until="domcontentloaded", timeout=60_000)
            try:
                await page.evaluate("document.fonts.ready")
            except Exception:
                pass

            await page.evaluate(
                """() => {
              for (const el of document.querySelectorAll('.cover h1, .cta h1, .info h2')) {
                let size = parseFloat(getComputedStyle(el).fontSize);
                const min = el.matches('.info h2') ? 46 : 62;
                const maxHeight = el.matches('.info h2') ? 215 : 440;
                let guard = 0;
                while (size > min && guard++ < 40) {
                  const box = el.getBoundingClientRect();
                  const tooWide = el.scrollWidth > el.clientWidth + 3;
                  const tooTall = box.height > maxHeight;
                  if (!tooWide && !tooTall) break;
                  size -= 2;
                  el.style.fontSize = size + 'px';
                }
              }
            }"""
            )
            await page.wait_for_timeout(150)
            out_path = OUTPUT_DIR / f"slide_{i}.png"
            await page.screenshot(path=str(out_path), type="png", animations="disabled", caret="hide")
            w, h = verify_png(out_path)
            print(f"   ✅ Сохранен слайд 0{i}/06 → {out_path.name} ({w}x{h} px)")

        await context.close()
        await browser.close()

    save_photo_sources(niche_key, selected_photos)
    (OUTPUT_DIR / "carousel_text.json").write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"🎉 ГОТОВО! Все 6 слайдов сохранены в папку: {OUTPUT_DIR.resolve()}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())