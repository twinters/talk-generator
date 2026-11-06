"""Animations on slides, which python-pptx can't make: the timing XML that PowerPoint writes for them.

For now two, which keep a punchline for a click:
- a chart whose series after the first appear on clicks, one by one, wiping in from the left. On a trend chart, that
  makes a second line draw itself across the chart as the punchline;
- shapes that fade in together on a click, such as a Venn diagram's overlap, or a matrix's dot with its name.
In the editor, and in viewers that don't play animations, everything simply shows.
"""

from __future__ import annotations

import itertools
from typing import Any, Final

from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn

# A chart's series, as an animation target (categoryIdx -3: all of them; bldStep: a series at a time)
_SERIES_TARGET: Final = (
    '<p:tgtEl><p:spTgt spid="{spid}"><p:graphicEl>'
    '<a:chart seriesIdx="{series}" categoryIdx="-3" bldStep="series"/>'
    "</p:graphicEl></p:spTgt></p:tgtEl>"
)

# One click: the series appears, wiping in from the left in a second (PowerPoint's preset 22, "Wipe", subtype 8)
_CLICK: Final = (
    '<p:par><p:cTn id="{click}" fill="hold"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst><p:childTnLst>'
    '<p:par><p:cTn id="{group}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:par><p:cTn id="{effect}" presetID="22" presetClass="entr" presetSubtype="8" fill="hold" grpId="0" '
    'nodeType="clickEffect"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:set><p:cBhvr><p:cTn id="{show}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
    "{target}<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
    '<p:to><p:strVal val="visible"/></p:to></p:set>'
    '<p:animEffect transition="in" filter="wipe(left)"><p:cBhvr><p:cTn id="{wipe}" dur="1000"/>{target}</p:cBhvr>'
    "</p:animEffect>"
    "</p:childTnLst></p:cTn></p:par>"
    "</p:childTnLst></p:cTn></p:par>"
    "</p:childTnLst></p:cTn></p:par>"
)

# A chart built a series at a time, without drawing its background (its axes, legend and first series) first
_CHART_BUILD: Final = (
    '<p:bldGraphic spid="{spid}" grpId="0"><p:bldSub><a:bldChart bld="series" animBg="0"/></p:bldSub></p:bldGraphic>'
)

# One click: shapes fade in together in half a second (PowerPoint's preset 10, "Fade"), the first as the click's
# effect and the others with it
_SHAPES_CLICK: Final = (
    '<p:par><p:cTn id="{click}" fill="hold"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst><p:childTnLst>'
    '<p:par><p:cTn id="{group}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    "{effects}"
    "</p:childTnLst></p:cTn></p:par>"
    "</p:childTnLst></p:cTn></p:par>"
)
_FADE_IN: Final = (
    '<p:par><p:cTn id="{effect}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold" grpId="0" '
    'nodeType="{node}"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:set><p:cBhvr><p:cTn id="{show}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
    "<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
    '<p:to><p:strVal val="visible"/></p:to></p:set>'
    '<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{fade}" dur="500"/>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
    "</p:childTnLst></p:cTn></p:par>"
)
# A shape that appears as one object, its text with it
_SHAPE_BUILD: Final = '<p:bldP spid="{spid}" grpId="0" animBg="1"/>'

_TIMING: Final = (
    "<p:timing {namespaces}><p:tnLst><p:par>"
    '<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
    '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
    "{clicks}"
    "</p:childTnLst></p:cTn>"
    '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
    '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
    "</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst>"
    "<p:bldLst>{builds}</p:bldLst></p:timing>"
)


def reveal_chart_series(slide: Any, chart_frame: Any, series_count: int) -> None:
    """Have the chart's series after the first appear on clicks, one by one (the slide gets this as its only
    animation)."""
    if series_count < 2:
        return
    spid = chart_frame.shape_id
    ids = itertools.count(3)  # 1 and 2 are the root and the main sequence
    clicks = []
    for series in range(1, series_count):
        target = _SERIES_TARGET.format(spid=spid, series=series)
        click, group, effect, show, wipe = (next(ids) for _ in range(5))
        clicks.append(_CLICK.format(click=click, group=group, effect=effect, show=show, wipe=wipe, target=target))
    _set_timing(slide, "".join(clicks), _CHART_BUILD.format(spid=spid))


def reveal_shapes(slide: Any, shapes: list[Any]) -> None:
    """Have the shapes appear together on a click, fading in (the slide gets this as its only animation)."""
    if not shapes:
        return
    ids = itertools.count(5)  # 1 and 2 are the root and the main sequence, 3 and 4 the click and its group
    effects = []
    for index, shape in enumerate(shapes):
        effect, show, fade = (next(ids) for _ in range(3))
        node = "clickEffect" if index == 0 else "withEffect"
        effects.append(_FADE_IN.format(effect=effect, node=node, show=show, fade=fade, spid=shape.shape_id))
    builds = "".join(_SHAPE_BUILD.format(spid=shape.shape_id) for shape in shapes)
    _set_timing(slide, _SHAPES_CLICK.format(click=3, group=4, effects="".join(effects)), builds)


def _set_timing(slide: Any, clicks: str, builds: str) -> None:
    timing = parse_xml(_TIMING.format(namespaces=nsdecls("p", "a"), clicks=clicks, builds=builds))
    # A slide's timing comes after its colour map and transition, and before its extensions
    slide_element = slide.element
    for old in slide_element.findall(qn("p:timing")):
        slide_element.remove(old)
    extensions = slide_element.find(qn("p:extLst"))
    if extensions is not None:
        extensions.addprevious(timing)
    else:
        slide_element.append(timing)
