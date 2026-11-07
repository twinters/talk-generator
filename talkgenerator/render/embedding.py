"""Carry a deck's open fonts inside its .pptx, so that PowerPoint shows them where they aren't installed
(docs/v5-plan.md, section 9).

PowerPoint keeps an embedded font as an Embedded OpenType (EOT) part, /ppt/fonts/fontN.fntdata, related from the
presentation and listed in its embeddedFontLst, with embedTrueTypeFonts on. It compresses the fonts it embeds itself
(MTX), but takes an uncompressed EOT as well: the font file behind an EOT header (tried in PowerPoint for Windows on
2026-11-07, on a computer without the font). python-pptx has no API for this, so the parts go in by hand. LibreOffice
25.8 and later read these fonts too. PowerPoint for the web (and most likely Keynote) shows a stand-in instead, which
texts are fitted to as well (talkgenerator.design.fonts.OPEN_FONTS); every run in an open font gets the font's PANOSE
and pitch family, as PowerPoint writes a font picked from its menu, so that a stand-in is at least of the same kind.

Whole fonts go in, regular and bold, so that a deck stays editable in them; PowerPoint keeps them whole when it saves
the file again.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from lxml import etree
from pptx.opc.constants import CONTENT_TYPE as CT
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part
from pptx.oxml.ns import qn
from pptx.presentation import Presentation

from talkgenerator.design import fonts

logger = logging.getLogger("talkgenerator")

# What comes after the embedded font list in a presentation's XML (ISO/IEC 29500-1, CT_Presentation)
_AFTER_FONT_LIST: Final = (
    "p:custShowLst",
    "p:photoAlbum",
    "p:custDataLst",
    "p:kinsoku",
    "p:defaultTextStyle",
    "p:modifyVerifier",
    "p:extLst",
)
_SERIF_STAND_INS: Final = frozenset({"Times New Roman", "Georgia"})
# Windows' pitch and family bits, as a:latin's pitchFamily has them
_FIXED_MODERN: Final = 0x31  # FIXED_PITCH | FF_MODERN
_VARIABLE_ROMAN: Final = 0x12  # VARIABLE_PITCH | FF_ROMAN
_VARIABLE_SWISS: Final = 0x22  # VARIABLE_PITCH | FF_SWISS


@dataclass(frozen=True)
class FontFacts:
    """What an EOT header and a run need to know about a TrueType font (from its OS/2, head, post and name tables)."""

    truetype: bool  # TrueType outlines (an EOT can't hold a CFF font)
    variable: bool
    fs_type: int  # what the font allows: 0 is installable embedding
    weight: int
    italic: bool
    fixed_pitch: bool
    panose: bytes
    unicode_ranges: tuple[int, int, int, int]
    codepage_ranges: tuple[int, int]
    checksum_adjustment: int
    names: dict[int, str]  # by name ID, in English where the font has more languages


def font_facts(data: bytes) -> FontFacts:
    """The facts of a font file (a TrueType or OpenType font, not a collection)."""
    version, tables = _tables(data)
    os2, head, post = tables["OS/2"][0], tables["head"][0], tables["post"][0]
    os2_version = struct.unpack_from(">H", data, os2)[0]
    unicode_ranges: Any = struct.unpack_from(">4I", data, os2 + 42)
    codepage_ranges: Any = struct.unpack_from(">2I", data, os2 + 78) if os2_version >= 1 else (0, 0)
    return FontFacts(
        truetype=version in (0x00010000, 0x74727565),  # (not 'OTTO', CFF)
        variable="fvar" in tables,
        fs_type=struct.unpack_from(">H", data, os2 + 8)[0],
        weight=struct.unpack_from(">H", data, os2 + 4)[0],
        italic=bool(struct.unpack_from(">H", data, os2 + 62)[0] & 1),
        fixed_pitch=struct.unpack_from(">I", data, post + 12)[0] != 0,
        panose=data[os2 + 32 : os2 + 42],
        unicode_ranges=unicode_ranges,
        codepage_ranges=codepage_ranges,
        checksum_adjustment=struct.unpack_from(">I", data, head + 8)[0],
        names=_names(data, tables["name"][0]),
    )


def eot(data: bytes) -> bytes:
    """The font as an Embedded OpenType (https://www.w3.org/submissions/EOT/): version 2.2, without compression or
    obfuscation (Flags 0), so the font file itself follows the header."""
    font = font_facts(data)
    if not font.truetype:
        raise ValueError("An EOT holds a TrueType font, not a CFF one")
    body = struct.pack("<III", len(data), 0x00020002, 0)  # FontDataSize, Version, Flags
    body += font.panose
    # Charset (DEFAULT_CHARSET), Italic, Weight, fsType, MagicNumber
    body += struct.pack("<BBIHH", 1, int(font.italic), font.weight, font.fs_type, 0x504C)
    body += struct.pack("<4I", *font.unicode_ranges)
    body += struct.pack("<2I", *font.codepage_ranges)
    body += struct.pack("<I", font.checksum_adjustment)
    body += struct.pack("<4I", 0, 0, 0, 0)  # Reserved1-4
    for name_id in (1, 2, 5, 4):  # FamilyName, StyleName, VersionName, FullName (UTF-16), each after its padding
        name = font.names.get(name_id, "").encode("utf-16-le")
        body += struct.pack("<HH", 0, len(name)) + name
    body += struct.pack("<HH", 0, 0)  # Padding5, RootStringSize (no RootString)
    body += struct.pack("<II", 0x50475342, 0)  # RootStringCheckSum (of no bytes), EUDCCodePage
    body += struct.pack("<HH", 0, 0)  # Padding6, SignatureSize (no Signature)
    body += struct.pack("<II", 0, 0)  # EUDCFlags, EUDCFontSize (no EUDC font)
    return struct.pack("<I", 4 + len(body) + len(data)) + body + data  # EOTSize first


def embed_fonts(presentation: Presentation) -> list[str]:
    """Carry the open fonts that the presentation's texts are in (on its slides and in its charts) inside it, each
    once, regular and bold (where it has a bold); and give their runs the fonts' PANOSE and pitch family. Returns
    the fonts it embedded now."""
    used = _typefaces(presentation)
    element = presentation.part._element
    font_list = element.find(qn("p:embeddedFontLst"))
    embedded = set() if font_list is None else {entry.find(qn("p:font")).get("typeface") for entry in font_list}
    added = []
    for font in sorted(used & set(fonts.OPEN_FONTS)):
        regular, bold = fonts.font_file(font), fonts.font_file(font, bold=True)
        if regular is None:
            logger.warning("Can't embed %s: its file isn't in talkgenerator's data/fonts", font)
            continue
        _mark_runs(presentation, font, _facts(str(regular)))
        if font in embedded:
            continue
        if font_list is None:
            font_list = etree.Element(qn("p:embeddedFontLst"))
            _insert_font_list(element, font_list)
        styles = {"regular": regular, "bold": bold if bold is not None and bold != regular else None}
        _add_font(presentation, font_list, font, _facts(str(regular)), styles)
        added.append(font)
    if font_list is not None:
        element.set("embedTrueTypeFonts", "1")
        # (whole fonts are in: PowerPoint would keep only the characters used when it saves the file again)
        element.attrib.pop("saveSubsetFonts", None)
    return added


def pitch_family(font: str, facts: FontFacts) -> int:
    """The open font's pitch and family bits, for a run's pitchFamily: of its kind (its stand-in's), as most of
    these fonts' own PANOSE leaves it open."""
    if facts.fixed_pitch:
        return _FIXED_MODERN
    return _VARIABLE_ROMAN if fonts.OPEN_FONTS.get(font) in _SERIF_STAND_INS else _VARIABLE_SWISS


def _add_font(
    presentation: Presentation, font_list: Any, font: str, facts: FontFacts, styles: dict[str, Path | None]
) -> None:
    package = presentation.part.package
    entry = etree.SubElement(font_list, qn("p:embeddedFont"))
    typeface = etree.SubElement(entry, qn("p:font"))
    typeface.set("typeface", font)
    typeface.set("panose", facts.panose.hex().upper())
    typeface.set("pitchFamily", str(pitch_family(font, facts)))
    typeface.set("charset", "0")
    for style, path in styles.items():  # (in the schema's order: regular, bold, italic, boldItalic)
        if path is None:
            continue
        part = Part(package.next_partname("/ppt/fonts/font%d.fntdata"), CT.X_FONTDATA, package, _eot(str(path)))
        etree.SubElement(entry, qn(f"p:{style}")).set(qn("r:id"), presentation.part.relate_to(part, RT.FONT))


def _insert_font_list(presentation_element: Any, font_list: Any) -> None:
    """Put the embedded font list where the schema has it: after the slide and notes sizes, before what follows."""
    for tag in _AFTER_FONT_LIST:
        following = presentation_element.find(qn(tag))
        if following is not None:
            following.addprevious(font_list)
            return
    presentation_element.append(font_list)


def _xml_parts(presentation: Presentation) -> list[Any]:
    return [part for part in presentation.part.package.iter_parts() if hasattr(part, "_element")]


def _typefaces(presentation: Presentation) -> set[str]:
    """The fonts the presentation's runs name (on its slides, in its charts and wherever else)."""
    return {
        str(latin.get("typeface"))
        for part in _xml_parts(presentation)
        for latin in part._element.iter(qn("a:latin"))
        if latin.get("typeface")
    }


def _mark_runs(presentation: Presentation, font: str, facts: FontFacts) -> None:
    """Give every run in the font its PANOSE, pitch family and character set."""
    for part in _xml_parts(presentation):
        for latin in part._element.iter(qn("a:latin")):
            if latin.get("typeface") == font:
                latin.set("panose", facts.panose.hex().upper())
                latin.set("pitchFamily", str(pitch_family(font, facts)))
                latin.set("charset", "0")


@cache
def _facts(path: str) -> FontFacts:
    return font_facts(Path(path).read_bytes())


@cache
def _eot(path: str) -> bytes:
    return eot(Path(path).read_bytes())


def _tables(data: bytes) -> tuple[int, dict[str, tuple[int, int]]]:
    """The font's sfnt version, and where each of its tables is (offset and length)."""
    version, count = struct.unpack_from(">IH", data, 0)
    if version == 0x74746366:  # 'ttcf'
        raise ValueError("A font collection, not a font")
    tables = {}
    for index in range(count):
        tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + 16 * index)
        tables[tag.decode("latin-1")] = (offset, length)
    return version, tables


def _names(data: bytes, offset: int) -> dict[int, str]:
    """The name table's names by ID: Windows' Unicode ones, in US English where there are others; else Mac's."""
    _, count, strings = struct.unpack_from(">HHH", data, offset)
    found: dict[int, tuple[int, str]] = {}
    for index in range(count):
        platform, encoding, language, name_id, length, start = struct.unpack_from(">6H", data, offset + 6 + 12 * index)
        raw = data[offset + strings + start : offset + strings + start + length]
        if platform == 3 and encoding in (0, 1, 10):
            rank, text = (0 if language == 0x409 else 1), raw.decode("utf-16-be", errors="replace")
        elif platform == 1 and encoding == 0:
            rank, text = 2, raw.decode("mac-roman", errors="replace")
        else:
            continue
        if name_id not in found or rank < found[name_id][0]:
            found[name_id] = (rank, text)
    return {name_id: text for name_id, (_, text) in sorted(found.items())}
