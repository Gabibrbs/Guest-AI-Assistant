"""Reading and checking config.toml (assistant/properties.py)."""

from pathlib import Path

import pytest

from assistant.properties import (
    DEFAULT_COLOR,
    DEFAULT_NOT_FOUND_MESSAGE,
    MAX_LOGO_KB,
    ConfigError,
    color_shades,
    load_properties,
)

EXAMPLE_FOLDER = Path(__file__).parent.parent / "exemplo"
PNG = b"\x89PNG\r\n\x1a\n" + b"rest of the image"
JPG = b"\xff\xd8\xff\xe0" + b"rest of the image"


def make_folder(tmp_path, config, slugs=("casa-a-111111",)):
    """A data folder with config.toml and an (empty) documents folder for each slug."""
    for slug in slugs:
        (tmp_path / "alojamentos" / slug / "documentos").mkdir(parents=True)
    (tmp_path / "config.toml").write_text(config, encoding="utf-8")
    return tmp_path


def one_property(**settings):
    """A config.toml with one property; each setting becomes `key = value`."""
    values = {"slug": '"casa-a-111111"', "name": '"Casa A"', **settings}
    lines = [f"{key} = {value}" for key, value in values.items() if value is not None]
    return "[[property]]\n" + "\n".join(lines) + "\n"


# ---------- Valid files ----------

def test_the_example_config_in_the_repository_is_valid():
    properties = load_properties(EXAMPLE_FOLDER)

    prop = properties["casa-da-ribeira-demo"]
    assert prop.name == "Casa da Ribeira Example"
    assert len(list(prop.documents_folder.glob("*.md"))) == 7


def test_example_config_warns_not_to_change_the_slug():
    text = (EXAMPLE_FOLDER / "config.toml").read_text(encoding="utf-8")

    assert "NÃO MUDES O SLUG depois de imprimir o QR code" in text


def test_reads_every_setting(tmp_path):
    (tmp_path / "alojamentos" / "casa-a-111111").mkdir(parents=True)
    (tmp_path / "alojamentos" / "casa-a-111111" / "logo.png").write_bytes(PNG)
    folder = make_folder(tmp_path, one_property(
        color='"#2F6F4E"',
        logo='"logo.png"',
        not_found_message='"Please message the host on Airbnb."',
        host_contact='"WhatsApp +351 000 000 001"',
    ))

    prop = load_properties(folder)["casa-a-111111"]

    assert prop.name == "Casa A"
    assert prop.color == "#2f6f4e"
    assert prop.logo == folder / "alojamentos" / "casa-a-111111" / "logo.png"
    assert prop.not_found_message == "Please message the host on Airbnb."
    assert prop.host_contact == "WhatsApp +351 000 000 001"
    assert prop.documents_folder == folder / "alojamentos" / "casa-a-111111" / "documentos"


def test_optional_settings_have_defaults(tmp_path):
    prop = load_properties(make_folder(tmp_path, one_property()))["casa-a-111111"]

    assert prop.color == DEFAULT_COLOR
    assert prop.logo is None
    assert prop.not_found_message == DEFAULT_NOT_FOUND_MESSAGE
    assert prop.host_contact == ""


def test_several_properties_keep_the_order_of_the_file(tmp_path):
    config = one_property() + one_property(slug='"loft-b-222222"', name='"Loft B"')
    folder = make_folder(tmp_path, config, slugs=("casa-a-111111", "loft-b-222222"))

    assert list(load_properties(folder)) == ["casa-a-111111", "loft-b-222222"]


# ---------- Mistakes in the file ----------

def test_missing_config_file_explains_how_to_start(tmp_path):
    with pytest.raises(ConfigError, match="Copy-Item -Recurse exemplo dados"):
        load_properties(tmp_path)


def test_toml_syntax_mistake(tmp_path):
    with pytest.raises(ConfigError, match="has a mistake"):
        load_properties(make_folder(tmp_path, '[[property]]\nname = "no closing quote\n'))


def test_file_without_properties(tmp_path):
    with pytest.raises(ConfigError, match="at least one"):
        load_properties(make_folder(tmp_path, "# nothing here\n"))


def test_unknown_setting_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="unknown setting.*colour"):
        load_properties(make_folder(tmp_path, one_property(colour='"#123456"')))


@pytest.mark.parametrize("slug", [
    '"Casa-A"', '"casa_a"', '"../casa"', '"casa a"', '""', '"-casa"', '"casa-"', '"casa--a"',
    '"' + "a" * 61 + '"', "123",
])
def test_invalid_slug_is_refused(tmp_path, slug):
    with pytest.raises(ConfigError, match="slug must use only"):
        load_properties(make_folder(tmp_path, one_property(slug=slug)))


@pytest.mark.parametrize("name", [None, '""', '"   "', "42"])
def test_name_is_required_text(tmp_path, name):
    with pytest.raises(ConfigError, match="name"):
        load_properties(make_folder(tmp_path, one_property(name=name)))


@pytest.mark.parametrize("color", ['"#12345"', '"blue"', '"#12345g"', '"1f4e8c"', '"#1f4e8c; x"', "123"])
def test_invalid_color_is_refused(tmp_path, color):
    with pytest.raises(ConfigError, match="color must look like"):
        load_properties(make_folder(tmp_path, one_property(color=color)))


def test_missing_documents_folder_is_refused(tmp_path):
    folder = make_folder(tmp_path, one_property(slug='"another-slug"'))  # folder made for casa-a-111111

    with pytest.raises(ConfigError, match="does not exist"):
        load_properties(folder)


def test_same_slug_twice_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="used twice"):
        load_properties(make_folder(tmp_path, one_property() + one_property(name='"Copy"')))


# ---------- Logo ----------

def logo_folder(tmp_path, file_name, data):
    property_folder = tmp_path / "alojamentos" / "casa-a-111111"
    property_folder.mkdir(parents=True)
    if data is not None:
        (property_folder / file_name).write_bytes(data)
    return property_folder


@pytest.mark.parametrize("file_name, data", [("logo.png", PNG), ("logo.jpg", JPG), ("Logo.JPEG", JPG)])
def test_png_and_jpg_logos_are_accepted(tmp_path, file_name, data):
    logo_folder(tmp_path, file_name, data)

    prop = load_properties(make_folder(tmp_path, one_property(logo=f'"{file_name}"')))["casa-a-111111"]

    assert prop.logo.name == file_name


@pytest.mark.parametrize("file_name, data, message", [
    ("logo.gif", b"GIF89a...", "must be a .png or .jpg"),
    ("logo.svg", b"<svg/>", "must be a .png or .jpg"),
    ("logo.png", JPG, "not really a PNG"),
    ("logo.jpg", PNG, "not really a JPG"),
    ("logo.png", b"", "the file is empty"),
    ("logo.png", PNG + b"x" * (MAX_LOGO_KB * 1024), f"larger than {MAX_LOGO_KB} KB"),
    ("logo.png", None, "does not exist"),
])
def test_invalid_logo_is_refused(tmp_path, file_name, data, message):
    logo_folder(tmp_path, file_name, data)

    with pytest.raises(ConfigError, match=message):
        load_properties(make_folder(tmp_path, one_property(logo=f'"{file_name}"')))


@pytest.mark.parametrize("logo", ['"../logo.png"', '"images/logo.png"', '""', "1"])
def test_logo_must_be_a_file_in_the_property_folder(tmp_path, logo):
    (tmp_path / "logo.png").write_bytes(PNG)

    with pytest.raises(ConfigError, match="file name"):
        load_properties(make_folder(tmp_path, one_property(logo=logo)))


# ---------- Colors ----------

def test_color_shades():
    assert color_shades("#1f4e8c") == {"main": "#1f4e8c", "dark": "#173a69", "light": "#e9edf4"}
    assert color_shades("#000000")["light"] == "#e6e6e6"
    assert color_shades("#ffffff")["dark"] == "#bfbfbf"
