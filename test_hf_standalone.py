from __future__ import annotations

import asyncio
import os
from pathlib import Path

from config import get_settings
from services.image_gen.free import sniff_image_mime
from services.image_gen.huggingface import HuggingFaceImageProvider

PROMPT = (
    "editorial beauty portrait of a woman with glowing skin, "
    "soft studio lighting, close-up, high detail"
)
OUTPUT_DIR = Path("generated_carousel")
EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/avif": ".avif",
}


async def main() -> None:
    settings = get_settings()
    api_key = os.getenv("HF_API_KEY", "").strip() or settings.HF_API_KEY
    if not api_key:
        raise SystemExit(
            "HF_API_KEY не задан. Добавьте его в .env или переменные окружения."
        )

    provider = HuggingFaceImageProvider(api_key=api_key)
    try:
        data = await provider.generate_image(PROMPT)
    finally:
        await provider.close()

    mime = sniff_image_mime(data[:32]) or "application/octet-stream"
    output = OUTPUT_DIR / f"hf_standalone_test{EXTENSIONS.get(mime, '.bin')}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    print(f"saved: {output} ({len(data)} bytes, {mime})")


if __name__ == "__main__":
    asyncio.run(main())
