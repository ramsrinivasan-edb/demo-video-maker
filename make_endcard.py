#!/usr/bin/env python
"""Build a 1440x810 end-card PNG with a QR code + URL, matching the video theme.

    python make_endcard.py --url https://example.com/repo --out build/endcard.png

Used by render.sh to append a "scan to make your own" card to the end of a video.
Runs locally (qrcode + Pillow); nothing is uploaded.
"""
import argparse
import qrcode
from PIL import Image, ImageDraw, ImageFont

W, H = 1440, 810
BG = (24, 26, 43)          # dark, close to the Dracula terminal background
TITLE = (248, 248, 242)
SUB = (150, 160, 200)
ACCENT = (139, 233, 253)   # cyan
PANEL = (255, 255, 255)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def font(size):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def centered(draw, y, text, fnt, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((W - (r - l)) / 2 - l, y), text, font=fnt, fill=fill)
    return b - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="Make your own demo videos")
    ap.add_argument("--subtitle", default="in your own voice, with your photo")
    args = ap.parse_args()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # top accent rule
    d.rectangle([(W / 2 - 60, 96), (W / 2 + 60, 102)], fill=ACCENT)

    centered(d, 140, args.title, font(58), TITLE)
    centered(d, 220, args.subtitle, font(30), SUB)

    # QR on a white rounded panel
    qr = qrcode.QRCode(border=2, box_size=10,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(args.url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    QS = 340
    qr_img = qr_img.resize((QS, QS), Image.NEAREST)
    pad = 26
    px, py = (W - QS) // 2, 300
    d.rounded_rectangle([(px - pad, py - pad), (px + QS + pad, py + QS + pad)],
                        radius=24, fill=PANEL)
    img.paste(qr_img, (px, py))

    centered(d, py + QS + pad + 34, "Scan, or visit:", font(26), SUB)
    centered(d, py + QS + pad + 74, args.url, font(30), ACCENT)

    img.save(args.out)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
