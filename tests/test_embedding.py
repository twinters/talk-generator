"""Offline tests of carrying open fonts inside a .pptx (talkgenerator.render.embedding): the fonts as uncompressed
Embedded OpenType, in the parts, relationships and list where PowerPoint keeps them."""

import struct
import zipfile

import pytest
from lxml import etree
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn

from talkgenerator.design import fonts, themes
from talkgenerator.render import embedding
from talkgenerator.render.powerpoint import render_pptx
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_design import _deck, _theme, _with_fonts

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _read_eot(blob):
    """An EOT's header fields, its four names and its font data (https://www.w3.org/submissions/EOT/)."""
    eot_size, data_size, version, flags = struct.unpack_from("<IIII", blob, 0)
    charset, italic, weight, fs_type, magic = struct.unpack_from("<BBIHH", blob, 26)
    position, names = 80, []
    for _ in range(4):
        padding, size = struct.unpack_from("<HH", blob, position)
        names.append(blob[position + 4 : position + 4 + size].decode("utf-16-le"))
        assert padding == 0
        position += 4 + size
    padding, root_size = struct.unpack_from("<HH", blob, position)
    root_checksum, _, _, signature_size, eudc_flags, eudc_size = struct.unpack_from("<IIHHII", blob, position + 4)
    assert (padding, root_size, root_checksum, signature_size, eudc_flags, eudc_size) == (0, 0, 0x50475342, 0, 0, 0)
    return {
        "size": eot_size,
        "data size": data_size,
        "version": version,
        "flags": flags,
        "panose": blob[16:26],
        "charset": charset,
        "italic": italic,
        "weight": weight,
        "fsType": fs_type,
        "magic": magic,
        "names": names,
        "data": blob[position + 24 :],
    }


@pytest.mark.parametrize("font", sorted(fonts.OPEN_FONTS))
def test_an_open_font_becomes_an_uncompressed_eot(font):
    for path in {fonts.font_file(font), fonts.font_file(font, bold=True)}:
        data = path.read_bytes()
        blob = embedding.eot(data)
        eot, facts = _read_eot(blob), embedding.font_facts(data)
        assert eot["size"] == len(blob) and eot["data size"] == len(data) and eot["data"] == data
        assert (eot["version"], eot["flags"], eot["magic"], eot["charset"]) == (0x00020002, 0, 0x504C, 1)
        assert (eot["weight"], eot["italic"], eot["fsType"], eot["panose"]) == (facts.weight, 0, 0, facts.panose)
        assert eot["names"] == [font, facts.names[2], facts.names[5], facts.names[4]]


def test_a_cff_font_or_a_collection_is_refused():
    data = bytearray(fonts.font_file("Barlow").read_bytes())
    with pytest.raises(ValueError, match="TrueType"):
        embedding.eot(b"OTTO" + bytes(data[4:]))
    with pytest.raises(ValueError, match="collection"):
        embedding.font_facts(b"ttcf" + bytes(data[4:]))


def _open_deck(heading="Archivo Black", body="IBM Plex Mono"):
    return _deck(theme=_with_fonts(_theme("brutalist"), heading, body)).to_deck()


def test_a_themed_deck_carries_its_open_fonts_where_powerpoint_keeps_them(images, tmp_path):
    path = tmp_path / "deck.pptx"
    render_pptx(_open_deck()).save(path)
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        content_types = etree.fromstring(package.read("[Content_Types].xml"))
        presentation = etree.fromstring(package.read("ppt/presentation.xml"))
        relationships = etree.fromstring(package.read("ppt/_rels/presentation.xml.rels"))
        parts = {name: package.read(name) for name in names if name.startswith("ppt/fonts/")}
        slides = [etree.fromstring(package.read(name)) for name in names if name.startswith(("ppt/slides/s", "ppt/ch"))]
    assert presentation.get("embedTrueTypeFonts") == "1" and presentation.get("saveSubsetFonts") is None
    assert any(
        default.get("Extension") == "fntdata" and default.get("ContentType") == "application/x-fontdata"
        for default in content_types
    )
    # The list comes after the slide and notes sizes and before the default text style, as the schema has it
    children = [child.tag.replace(_P, "") for child in presentation]
    assert children.index("notesSz") < children.index("embeddedFontLst") < children.index("defaultTextStyle")
    targets = {rel.get("Id"): rel for rel in relationships.iter(f"{_RELS}Relationship")}
    entries = presentation.find(f"{_P}embeddedFontLst")
    assert [entry.find(f"{_P}font").get("typeface") for entry in entries] == ["Archivo Black", "IBM Plex Mono"]
    for entry, styles in zip(entries, (["regular"], ["regular", "bold"]), strict=True):
        font = entry.find(f"{_P}font")
        assert [child.tag.replace(_P, "") for child in entry] == ["font", *styles]  # (no bold: Archivo Black has none)
        assert font.get("pitchFamily") in ("34", "49") and len(font.get("panose")) == 20 and font.get("charset") == "0"
        for style in styles:
            relationship = targets[entry.find(f"{_P}{style}").get(f"{_R}id")]
            assert relationship.get("Type") == RT.FONT and relationship.get("Target").endswith(".fntdata")
            eot = _read_eot(parts["ppt/" + relationship.get("Target")])
            bundled = fonts.font_file(font.get("typeface"), bold=style == "bold")
            assert (
                eot["names"][:2] == [font.get("typeface"), style.capitalize()] and eot["data"] == bundled.read_bytes()
            )
    assert len(parts) == 3
    # Every run in an open font says what kind of font it is, so a stand-in is of the same kind
    runs = [
        latin for slide in slides for latin in slide.iter(f"{_A}latin") if latin.get("typeface") in fonts.OPEN_FONTS
    ]
    assert {latin.get("typeface") for latin in runs} == {"Archivo Black", "IBM Plex Mono"}
    for latin in runs:
        assert latin.get("pitchFamily") == ("49" if latin.get("typeface") == "IBM Plex Mono" else "34")
        assert len(latin.get("panose")) == 20 and latin.get("charset") == "0"
    Presentation(str(path))  # (and it opens)


def test_a_chart_in_an_open_font_says_so_too(images):
    presentation = render_pptx(_open_deck("Archivo Black", "Lato"))
    charts = [part for part in presentation.part.package.iter_parts() if "/charts/" in str(part.partname)]
    latins = [
        latin for part in charts for latin in part._element.iter(qn("a:latin")) if latin.get("typeface") == "Lato"
    ]
    assert charts and latins and all(latin.get("panose") and latin.get("pitchFamily") == "34" for latin in latins)


def test_a_deck_in_installed_fonts_carries_none(images):
    presentation = render_pptx(_open_deck("Arial Black", "Courier New"))
    assert presentation.part._element.find(qn("p:embeddedFontLst")) is None
    assert not any(str(part.partname).startswith("/ppt/fonts/") for part in presentation.part.package.iter_parts())
    assert presentation.part._element.get("embedTrueTypeFonts") is None


def test_a_font_goes_in_once(images):
    presentation = render_pptx(_open_deck())
    assert embedding.embed_fonts(presentation) == []  # (in already)
    assert len(presentation.part._element.find(qn("p:embeddedFontLst"))) == 2


def test_the_open_fonts_runs_are_of_their_kind():
    """(the pitch family PowerPoint matches a stand-in by, where the font's own PANOSE leaves it open)"""
    for font in fonts.OPEN_FONTS:
        facts = embedding.font_facts(fonts.font_file(font).read_bytes())
        family = embedding.pitch_family(font, facts)
        if font in ("Courier Prime", "IBM Plex Mono", "Space Mono"):
            assert family == 0x31  # fixed pitch, modern
        elif fonts.OPEN_FONTS[font] in ("Times New Roman", "Georgia"):
            assert family == 0x12  # variable pitch, roman
        else:
            assert family == 0x22  # variable pitch, swiss


def test_the_heavy_display_faces_are_only_ever_headings_that_arent_made_bolder():
    for family in themes.FAMILIES.values():
        for heading, body in family.open_fonts:
            assert body not in themes._HEAVY_FONTS
            if fonts.font_file(heading, bold=True) == fonts.font_file(heading):
                assert heading in themes._HEAVY_FONTS
