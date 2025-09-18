"""Generator placeholdera miniatury maszyn."""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 128, 128
BG_COLOR = (24, 24, 24)
FG_COLOR = (240, 240, 240)
BORDER_COLOR = (180, 180, 180)
TEXT = "Brak\nzdjęcia"


def _measure_text(
    draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont
) -> tuple[int, int]:
    if hasattr(draw, "multiline_textbbox"):
        left, top, right, bottom = draw.multiline_textbbox(
            (0, 0),
            TEXT,
            font=font,
            spacing=2,
            align="center",
        )
        return right - left, bottom - top
    return draw.multiline_textsize(TEXT, font=font, spacing=2)


def main() -> None:
    os.makedirs("grafiki", exist_ok=True)

    image = Image.new("RGB", (W, H), color=BG_COLOR)
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, W - 1, H - 1], outline=BORDER_COLOR)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    text_width, text_height = _measure_text(draw, font)
    draw.multiline_text(
        ((W - text_width) // 2, (H - text_height) // 2),
        TEXT,
        fill=FG_COLOR,
        font=font,
        align="center",
        spacing=2,
    )

    out_path = os.path.join("grafiki", "machine_placeholder.jpg")
    image.save(out_path, quality=92)
    print(f"Utworzono {out_path}")


if __name__ == "__main__":
    main()
