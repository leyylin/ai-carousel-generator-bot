from __future__ import annotations

import asyncio
import html
import logging
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from string import Template
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from config import Settings
from services.errors import RendererError
from services.image_gen.base import ImageResult
from services.llm.models import CarouselContent, SlideContent

logger = logging.getLogger(__name__)

DEFAULT_HANDLE = "@your_brand"
DEFAULT_BRAND = "STUDIO / CAROUSEL"
SUPPORTED_THEMES = ("editorial", "matte_cards", "minimal")
MIDDLE_LAYOUTS = ("bottom", "center", "top", "left")
EM_RE = re.compile(r"<em>(.*?)</em>", re.IGNORECASE | re.DOTALL)
SOLUTION_PREFIX_RE = re.compile(
    r"^\s*(решение|совет|вывод|итог)\s*[:\-—]\s*", re.IGNORECASE
)


@dataclass(slots=True)
class RenderedSlide:
    index: int
    filename: str
    data: bytes
    path: Path
    width: int
    height: int


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def nl2br(value: object) -> str:
    return esc(value).replace("\n", "<br>")


def display_handle(value: str | None) -> str:
    handle = (value or "").strip()
    if not handle:
        return DEFAULT_HANDLE
    if not handle.startswith("@"):
        handle = f"@{handle}"
    return handle


def render_title(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    parts: list[str] = []
    position = 0
    for match in EM_RE.finditer(text):
        parts.append(esc(text[position : match.start()]))
        inner = match.group(1).strip()
        if inner:
            parts.append(f"<em>{esc(inner)}</em>")
        position = match.end()
    parts.append(esc(text[position:]))
    result = "".join(parts).strip()
    if "<em>" not in result and result:
        head, separator, tail = result.rpartition(" ")
        if separator and head:
            result = f"{head} <em>{tail}</em>"
        else:
            result = f"<em>{result}</em>"
    return result


def layout_for(index: int, total: int) -> str:
    if index <= 0 or index >= total - 1:
        return "bottom"
    return MIDDLE_LAYOUTS[(index - 1) % len(MIDDLE_LAYOUTS)]


def strip_solution_prefix(value: str) -> str:
    return SOLUTION_PREFIX_RE.sub("", value or "", count=1).strip()


def verify_png_bytes(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RendererError("Рендер вернул некорректный PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


class CarouselRenderer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.template_dir = Path(__file__).resolve().parent / "templates"
        html_path = self.template_dir / "slide.html"
        if not html_path.is_file():
            raise RendererError("Не найден шаблон слайда")
        self._template = Template(html_path.read_text(encoding="utf-8"))
        base_path = self.template_dir / "base.css"
        if not base_path.is_file():
            raise RendererError("Не найден базовый стиль слайда")
        self._base_style = base_path.read_text(encoding="utf-8")
        self._styles: dict[str, str] = {}
        for theme in SUPPORTED_THEMES:
            css_path = self.template_dir / f"{theme}.css"
            if not css_path.is_file():
                raise RendererError(f"Не найден стиль {theme}")
            self._styles[theme] = css_path.read_text(encoding="utf-8")

        self._playwright = None
        self._browser = None
        self._start_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max(1, settings.RENDER_CONCURRENCY))

    async def start(self) -> None:
        if self._browser is not None and self._browser.is_connected():
            return
        async with self._start_lock:
            if self._browser is not None and self._browser.is_connected():
                return
            try:
                if self._playwright is None:
                    self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
            except PlaywrightError as exc:
                if self._playwright is not None:
                    await self._playwright.stop()
                    self._playwright = None
                raise RendererError(
                    "Не удалось запустить Chromium. Выполните: playwright install chromium"
                ) from exc

    async def close(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            finally:
                self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            finally:
                self._playwright = None

    async def render_carousel(
        self,
        content: CarouselContent,
        images: list[ImageResult | None],
        theme: str,
        handle: str | None,
        niche: str,
        brand: str | None = None,
    ) -> list[RenderedSlide]:
        if theme not in SUPPORTED_THEMES:
            raise RendererError(f"Неизвестный шаблон: {theme}")
        if not content.slides:
            raise RendererError("В контенте нет слайдов")

        await self.start()
        async with self._semaphore:
            context = await self._browser.new_context(
                viewport={"width": self.settings.IMAGE_WIDTH, "height": self.settings.IMAGE_HEIGHT},
                device_scale_factor=1,
                color_scheme="light",
                reduced_motion="reduce",
            )
            page = await context.new_page()
            page.set_default_timeout(60_000)
            run_dir = self.settings.RENDER_OUTPUT_DIR / "runs" / uuid4().hex
            run_dir.mkdir(parents=True, exist_ok=True)
            rendered: list[RenderedSlide] = []
            try:
                total = len(content.slides)
                for index, slide in enumerate(content.slides):
                    image = images[index] if index < len(images) else None
                    html_content = self._build_html(
                        slide=slide,
                        image=image,
                        index=index,
                        total=total,
                        theme=theme,
                        handle=handle,
                        niche=niche,
                        brand=brand,
                        content=content,
                    )
                    await page.set_content(
                        html_content, wait_until="domcontentloaded", timeout=60_000
                    )
                    await self._wait_for_fonts(page)
                    await self._fit_title(page)
                    await page.wait_for_timeout(120)
                    path = run_dir / f"slide_{index + 1:02d}.png"
                    await page.screenshot(
                        path=str(path),
                        type="png",
                        animations="disabled",
                        caret="hide",
                    )
                    data = path.read_bytes()
                    width, height = verify_png_bytes(data)
                    if (width, height) != (
                        self.settings.IMAGE_WIDTH,
                        self.settings.IMAGE_HEIGHT,
                    ):
                        raise RendererError(
                            f"Неверный размер слайда: {width}x{height}"
                        )
                    rendered.append(
                        RenderedSlide(
                            index=index + 1,
                            filename=f"slide_{index + 1:02d}.png",
                            data=data,
                            path=path,
                            width=width,
                            height=height,
                        )
                    )
                return rendered
            finally:
                await page.close()
                await context.close()

    @staticmethod
    async def _wait_for_fonts(page) -> None:
        try:
            await page.evaluate(
                """async () => {
                    if (!document.fonts || !document.fonts.ready) return;
                    await Promise.race([
                        document.fonts.ready,
                        new Promise((resolve) => setTimeout(resolve, 5000))
                    ]);
                }"""
            )
        except Exception:
            logger.debug("Font wait skipped", exc_info=True)

    @staticmethod
    async def _fit_title(page) -> None:
        await page.evaluate(
            """() => {
                const el = document.querySelector('.title');
                if (!el) return;
                let size = parseFloat(getComputedStyle(el).fontSize);
                const computed = getComputedStyle(el);
                const maxHeight = parseFloat(computed.maxHeight) || 460;
                const min = 30;
                let guard = 0;
                while (size > min && guard++ < 80) {
                    const tooWide = el.scrollWidth > el.clientWidth + 3;
                    const tooTall = el.scrollHeight > maxHeight + 2;
                    if (!tooWide && !tooTall) break;
                    size -= 2;
                    el.style.fontSize = size + 'px';
                }
            }"""
        )

    def _build_html(
        self,
        slide: SlideContent,
        image: ImageResult | None,
        index: int,
        total: int,
        theme: str,
        handle: str | None,
        niche: str,
        content: CarouselContent,
        brand: str | None = None,
    ) -> str:
        kind = "cover" if index == 0 else "final" if index == total - 1 else "middle"
        layout = layout_for(index, total)
        photo_var = (
            f"--photo:url('{image.data_uri}');" if image is not None else "--photo:none;"
        )
        subtitle = (
            f'<p class="subtitle">{esc(slide.subtitle)}</p>' if slide.subtitle else ""
        )
        body = f'<p class="body">{nl2br(slide.body)}</p>' if slide.body else ""
        highlight = ""
        if slide.highlight_box:
            highlight_text = strip_solution_prefix(slide.highlight_box)
            if highlight_text:
                highlight = (
                    '<div class="highlight">'
                    '<div class="highlight-label">Решение</div>'
                    f"<p>{nl2br(highlight_text)}</p>"
                    "</div>"
                )
        cta_text = slide.cta_button
        if not cta_text:
            if kind == "cover":
                cta_text = "Листай дальше →"
            elif kind == "final":
                cta_text = "Записаться в Директ"
        cta = f'<div class="cta">{esc(cta_text)}</div>' if cta_text else ""
        resolved_niche = niche or content.niche or ""
        return self._template.safe_substitute(
            css=f"{self._base_style}\n{self._styles[theme]}",
            photo_var=photo_var,
            kind=kind,
            layout=layout,
            badge=esc(slide.badge),
            counter=f"{index + 1:02d} / {total:02d}",
            niche=esc(resolved_niche),
            title=render_title(slide.title),
            subtitle=subtitle,
            body=body,
            highlight=highlight,
            cta=cta,
            handle=esc(display_handle(handle)),
            brand=esc((brand or "").strip() or DEFAULT_BRAND),
        )
