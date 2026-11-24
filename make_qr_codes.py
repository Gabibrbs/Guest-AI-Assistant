"""Make the printable QR code (PNG) of every property, without opening the app.

Run with:  python make_qr_codes.py

Each image is saved in the property's folder (inside the data folder, never in Git):
    dados/alojamentos/<slug>/qr-code.png
The QR codes point to PUBLIC_BASE_URL (from .env), so it must be set first.
"""

import os
import sys

from dotenv import load_dotenv

from app import data_folder_setting
from assistant.properties import ConfigError, load_properties
from assistant.qr import PublicAddressError, check_public_base_url, guest_link, make_qr_png

FILE_NAME = "qr-code.png"


def make_all(data_folder, public_base_url):
    """Save one QR code per property. Returns the list of (link, saved file)."""
    base = check_public_base_url(public_base_url)
    saved = []
    for prop in load_properties(data_folder).values():
        link = guest_link(base, prop.slug)
        path = prop.folder / FILE_NAME
        path.write_bytes(make_qr_png(link, prop.name))
        saved.append((link, path))
    return saved


def main():
    load_dotenv()
    try:
        saved = make_all(data_folder_setting(), os.environ.get("PUBLIC_BASE_URL"))
    except (PublicAddressError, ConfigError) as error:
        print(f"No QR codes were made: {error}")
        sys.exit(1)

    for link, path in saved:
        print(f"{path}\n    opens {link}")
    print("\nBefore printing, scan each one with a phone and check that the right page opens.")


if __name__ == "__main__":
    main()
