"""Per-client settings: the properties (holiday rentals) of one installation.

They are read from <data folder>/config.toml when the app starts. Every value is checked
here, so a mistake in the file stops the app with a clear message instead of showing a
broken page to guests.

Folders of one property:
    <data folder>/alojamentos/<slug>/documentos/   the house guide
    <data folder>/alojamentos/<slug>/logo.png      the logo (optional)
"""

import re
import tomllib  # reads TOML files; part of Python since 3.11
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE_NAME = "config.toml"
FIELDS = {"slug", "name", "color", "logo", "not_found_message", "host_contact"}

SLUG_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")  # e.g. "casa-da-ribeira-k7q3xz"
MAX_SLUG_LENGTH = 60
COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}")        # e.g. "#1f4e8c"

DEFAULT_COLOR = "#1f4e8c"
DEFAULT_NOT_FOUND_MESSAGE = "Please contact the host."

# Logos: like the documents, the type is checked by its content, not only by its name
MAX_LOGO_KB = 500
LOGO_SIGNATURES = {
    ".png": b"\x89PNG\r\n\x1a\n",  # the first bytes of every PNG file
    ".jpg": b"\xff\xd8\xff",        # the first bytes of every JPG file
    ".jpeg": b"\xff\xd8\xff",
}


class ConfigError(RuntimeError):
    """A mistake in config.toml or in the property folders."""


@dataclass(frozen=True)
class Property:
    slug: str
    name: str
    folder: Path
    color: str = DEFAULT_COLOR
    logo: Path | None = None
    not_found_message: str = DEFAULT_NOT_FOUND_MESSAGE
    host_contact: str = ""

    @property
    def documents_folder(self):
        return self.folder / "documentos"


def load_properties(data_folder):
    """Read and check config.toml. Returns {slug: Property}, in the order of the file."""
    data_folder = Path(data_folder)
    path = data_folder / CONFIG_FILE_NAME
    if not path.is_file():
        raise ConfigError(
            f"{path} does not exist. To start from the demo, copy the example folder:"
            " Copy-Item -Recurse exemplo dados"
        )
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} has a mistake: {error}") from error

    entries = config.get("property")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{path} needs at least one [[property]] block.")

    properties = {}
    for number, entry in enumerate(entries, start=1):
        place = f"config.toml, property {number}"
        found = read_property(entry, data_folder, place)
        if found.slug in properties:
            raise ConfigError(f"{place}: the slug {found.slug!r} is used twice.")
        properties[found.slug] = found
    return properties


def read_property(entry, data_folder, place):
    unknown = set(entry) - FIELDS
    if unknown:  # catches typos such as "colour"
        raise ConfigError(f"{place}: unknown setting(s) {', '.join(sorted(unknown))}.")

    slug = entry.get("slug")
    if not isinstance(slug, str) or len(slug) > MAX_SLUG_LENGTH or not SLUG_PATTERN.fullmatch(slug):
        raise ConfigError(f"{place}: the slug must use only lowercase letters, numbers and hyphens.")

    name = text_setting(entry, "name", place, required=True)

    color = entry.get("color", DEFAULT_COLOR)
    if not isinstance(color, str) or not COLOR_PATTERN.fullmatch(color):
        raise ConfigError(f"{place}: the color must look like #1f4e8c.")

    folder = data_folder / "alojamentos" / slug
    if not (folder / "documentos").is_dir():
        raise ConfigError(f"{place}: the folder {folder / 'documentos'} does not exist.")

    logo = None
    if "logo" in entry:
        logo = check_logo(folder, entry["logo"], place)

    return Property(
        slug=slug,
        name=name,
        folder=folder,
        color=color.lower(),
        logo=logo,
        not_found_message=text_setting(entry, "not_found_message", place) or DEFAULT_NOT_FOUND_MESSAGE,
        host_contact=text_setting(entry, "host_contact", place),
    )


def text_setting(entry, key, place, required=False):
    value = entry.get(key, "")
    if not isinstance(value, str):
        raise ConfigError(f"{place}: {key} must be text between quotes.")
    value = value.strip()
    if required and not value:
        raise ConfigError(f"{place}: {key} is missing.")
    return value


def check_logo(folder, file_name, place):
    """The logo must be a PNG or JPG file inside the property folder, up to MAX_LOGO_KB."""
    if not isinstance(file_name, str) or not file_name or Path(file_name).name != file_name:
        raise ConfigError(f"{place}: logo must be a file name such as \"logo.png\", with no folders.")

    path = folder / file_name
    extension = path.suffix.lower()
    if extension not in LOGO_SIGNATURES:
        raise ConfigError(f"{place}: {file_name}: the logo must be a .png or .jpg file.")
    if not path.is_file():
        raise ConfigError(f"{place}: the logo {path} does not exist.")

    data = path.read_bytes()
    if not data:
        raise ConfigError(f"{place}: {file_name}: the file is empty.")
    if len(data) > MAX_LOGO_KB * 1024:
        raise ConfigError(f"{place}: {file_name}: the logo is larger than {MAX_LOGO_KB} KB.")
    if not data.startswith(LOGO_SIGNATURES[extension]):
        raise ConfigError(f"{place}: {file_name}: the file is not really a {extension[1:].upper()} image.")
    return path


def color_shades(color):
    """The main color plus a darker one (hover) and a very light one (backgrounds).

    Example: "#1f4e8c" -> {"main": "#1f4e8c", "dark": "#173a69", "light": "#e9edf4"}
    """
    red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))

    def mix(target, amount):  # move each channel `amount` of the way to `target`
        return "#" + "".join(f"{round(c + (target - c) * amount):02x}" for c in (red, green, blue))

    return {"main": color, "dark": mix(0, 0.25), "light": mix(255, 0.9)}
