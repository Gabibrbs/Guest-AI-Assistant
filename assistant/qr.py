"""QR codes for the guest links, as PNG images ready to print.

The image has the QR code in large size, the property's name and a short sentence below
it, and the link in small print (for anyone who cannot scan).

The QR code uses the highest error correction (H): up to about 30% of it can be dirty,
torn or covered and phones can still read it.
"""

import io
from urllib.parse import urlsplit

import qrcode
from PIL import Image, ImageDraw, ImageFont

TAGLINE = "Scan for answers about your stay"

WIDTH = 1200          # pixels; about 10 cm wide when printed at 300 dpi
MARGIN = 80
QR_WIDTH = 960        # the QR code (with its white border) is at most this wide
TEXT_GAP = 24


class PublicAddressError(ValueError):
    """PUBLIC_BASE_URL is missing or is not a web address."""


def check_public_base_url(value):
    """Return the public address without a final "/", e.g. "https://conta.pythonanywhere.com".

    The app cannot know on its own the address guests use, so it comes from .env.
    """
    value = (value or "").strip().rstrip("/")
    if not value:
        raise PublicAddressError(
            "PUBLIC_BASE_URL is missing. Add the app's public address to .env, "
            "for example PUBLIC_BASE_URL=https://account.pythonanywhere.com"
        )
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.query or parts.fragment:
        raise PublicAddressError(
            f"PUBLIC_BASE_URL must be a web address like https://account.pythonanywhere.com, not {value!r}."
        )
    return value


def guest_link(public_base_url, slug):
    """The link printed in the QR code, e.g. https://conta.pythonanywhere.com/p/casa-da-ribeira-k7q3xz"""
    return f"{public_base_url}/p/{slug}"


def make_qr_code(link):
    """The QR code itself (not yet an image), with high error correction."""
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=4)
    code.add_data(link)
    code.make(fit=True)  # chooses the smallest QR size that holds the link
    return code


def make_qr_png(link, property_name, tagline=TAGLINE):
    """The printable PNG (bytes): QR code, property name, tagline and the link."""
    code = make_qr_code(link)
    modules = code.modules_count + 2 * code.border          # squares across, white border included
    code.box_size = QR_WIDTH // modules                      # whole pixels per square keep it sharp
    qr_image = code.make_image(fill_color="black", back_color="white").get_image().convert("RGB")

    lines = [
        # (text, largest font size, smallest font size, color)
        (property_name, 72, 32, (31, 41, 51)),
        (tagline, 44, 24, (75, 85, 99)),
        (link, 28, 16, (107, 114, 128)),
    ]
    fonts = [fitting_font(text, largest, smallest) for text, largest, smallest, _ in lines]
    heights = [text_size(text, font)[1] for (text, *_), font in zip(lines, fonts)]

    height = MARGIN + qr_image.height + sum(heights) + TEXT_GAP * (len(lines) + 1) + MARGIN
    page = Image.new("RGB", (WIDTH, height), "white")
    page.paste(qr_image, ((WIDTH - qr_image.width) // 2, MARGIN))

    draw = ImageDraw.Draw(page)
    y = MARGIN + qr_image.height + TEXT_GAP
    for (text, _, _, color), font, line_height in zip(lines, fonts, heights):
        width = text_size(text, font)[0]
        draw.text(((WIDTH - width) // 2, y), text, font=font, fill=color)
        y += line_height + TEXT_GAP

    output = io.BytesIO()
    page.save(output, format="PNG", dpi=(300, 300))
    return output.getvalue()


def fitting_font(text, largest, smallest):
    """The largest font size (down to `smallest`) at which `text` fits the page width."""
    for size in range(largest, smallest - 1, -2):
        font = ImageFont.load_default(size=size)  # a font that comes with Pillow, on every system
        if text_size(text, font)[0] <= WIDTH - 2 * MARGIN:
            return font
    return ImageFont.load_default(size=smallest)


def text_size(text, font):
    left, top, right, bottom = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
    return right - left, bottom - top
