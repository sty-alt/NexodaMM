"""Сгенерировать QR-код на бота (для печати в салоне и Instagram).

Пример:  python make_qr.py myshop_bot
Результат: PNG-файл в папке data/ со ссылкой t.me/<username> и подписью.
"""
from __future__ import annotations

import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import qrcode
from PIL import Image, ImageDraw, ImageFont

from bot.config import DATA_DIR


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make(username: str, caption: str = "Запись онлайн") -> str:
    username = username.lstrip("@")
    url = f"https://t.me/{username}"

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=2
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    w, h = qr_img.size
    footer = 120
    canvas = Image.new("RGB", (w, h + footer), "white")
    canvas.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    f_big = _font(40)
    f_small = _font(28)

    def centered(text, y, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) / 2, y), text, fill="black", font=font)

    centered(f"@{username}", h + 15, f_big)
    centered(caption, h + 70, f_small)

    out = DATA_DIR / f"qr_{username}.png"
    canvas.save(out)
    return str(out)


def main() -> None:
    if len(sys.argv) < 2:
        print("Укажи username бота.\nПример:  python make_qr.py myshop_bot")
        return
    username = sys.argv[1]
    caption = sys.argv[2] if len(sys.argv) > 2 else "Запись онлайн"
    path = make(username, caption)
    print(f"✅ QR-код готов: {path}")
    print("Распечатай его в салоне и добавь в Instagram-профиль/сторис.")


if __name__ == "__main__":
    main()
