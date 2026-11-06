"""Animations on slides, which python-pptx can't make: the timing XML that PowerPoint writes for them.

For now three:
- a chart whose series after the first appear on clicks, one by one, wiping in from the left. On a trend chart, that
  makes a second line draw itself across the chart as the punchline;
- shapes that fade in together on a click, such as a Venn diagram's overlap, or a matrix's dot with its name;
- videos that play by themselves as their slide comes up, looping and without sound, the way the gifs they stand in
  for do.
In the editor, and in viewers that don't play animations, everything simply shows, and a video shows its poster frame.
"""

from __future__ import annotations

import itertools
from typing import Any, Final

from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn

from talkgenerator.util import video_util

# A slide's timing: the root, holding the main sequence (what happens on clicks, or by itself) and the media after it,
# then what's built a step at a time
_TIMING: Final = (
    "<p:timing {namespaces}><p:tnLst><p:par>"
    '<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
    '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
    "{sequence}"
    "</p:childTnLst></p:cTn>"
    '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
    '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
    "</p:seq>{media}</p:childTnLst></p:cTn></p:par></p:tnLst>{builds}</p:timing>"
)

# CHARTS

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

# Built a series at a time, without drawing the chart's background (its axes, legend and first series) first
_SERIES_BUILD: Final = (
    '<p:bldLst><p:bldGraphic spid="{spid}" grpId="0"><p:bldSub><a:bldChart bld="series" animBg="0"/></p:bldSub>'
    "</p:bldGraphic></p:bldLst>"
)

# SHAPES

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

# VIDEOS

# The step that starts with the main sequence, without a click (cTn 2), and the group of effects in it
_ON_ITS_OWN: Final = (
    '<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/>'
    '<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>'
    '<p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    "{effects}"
    "</p:childTnLst></p:cTn></p:par>"
    "</p:childTnLst></p:cTn></p:par>"
)

# A video plays from its start (PowerPoint's "Play" media effect, preset 1), for as long as it lasts: the first one
# after the slide comes up ("Start: Automatically"), the others with it
_PLAY: Final = (
    '<p:par><p:cTn id="{effect}" presetID="1" presetClass="mediacall" presetSubtype="0" fill="hold" '
    'nodeType="{node_type}"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr><p:cTn id="{call}"{duration} fill="hold"/>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:cmd>'
    "</p:childTnLst></p:cTn></p:par>"
)

# The video itself: it loops until the slide ends ("Loop until Stopped"), without sound ("Mute"), as gifs have none
_MEDIA: Final = (
    '<p:video><p:cMediaNode vol="80000" mute="1">'
    '<p:cTn id="{node}" repeatCount="indefinite" fill="hold" display="0">'
    '<p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cMediaNode></p:video>'
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
    timing = _TIMING.format(
        namespaces=nsdecls("p", "a"), sequence="".join(clicks), media="", builds=_SERIES_BUILD.format(spid=spid)
    )
    _replace_timing(slide, parse_xml(timing))


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
    timing = _TIMING.format(
        namespaces=nsdecls("p", "a"),
        sequence=_SHAPES_CLICK.format(click=3, group=4, effects="".join(effects)),
        media="",
        builds=f"<p:bldLst>{builds}</p:bldLst>",
    )
    _replace_timing(slide, parse_xml(timing))


def play_videos(slide: Any) -> None:
    """Have the slide's videos play by themselves as it comes up, all at once, looping and without sound (the slide
    gets this as its only animation). The timing python-pptx gives them plays a video once it's clicked."""
    videos = slide.element.xpath("./p:cSld/p:spTree//p:pic[p:nvPicPr/p:nvPr/a:videoFile]")
    if not videos:
        return
    spids = [video.xpath("./p:nvPicPr/p:cNvPr/@id")[0] for video in videos]
    ids = itertools.count(5)  # 1 to 4 are the root, the main sequence, and the step and group the videos start in
    effects = []
    for number, (spid, video) in enumerate(zip(spids, videos, strict=True)):
        seconds = video_util.duration(_video_bytes(slide, video))
        duration = f' dur="{round(seconds * 1000)}"' if seconds else ""
        node_type = "afterEffect" if number == 0 else "withEffect"
        effect, call = next(ids), next(ids)
        effects.append(_PLAY.format(effect=effect, call=call, node_type=node_type, duration=duration, spid=spid))
    media = "".join(_MEDIA.format(node=next(ids), spid=spid) for spid in spids)
    timing = _TIMING.format(
        namespaces=nsdecls("p"), sequence=_ON_ITS_OWN.format(effects="".join(effects)), media=media, builds=""
    )
    _replace_timing(slide, parse_xml(timing))


def _video_bytes(slide: Any, video: Any) -> bytes:
    """The video file a slide's video shape plays."""
    part_id = video.xpath("./p:nvPicPr/p:nvPr/a:videoFile/@r:link")[0]
    return bytes(slide.part.related_part(part_id).blob)


def _replace_timing(slide: Any, timing: Any) -> None:
    """Give the slide this timing instead of the one it has: after its colour map and transition, and before its
    extensions."""
    slide_element = slide.element
    for old in slide_element.findall(qn("p:timing")):
        slide_element.remove(old)
    extensions = slide_element.find(qn("p:extLst"))
    if extensions is not None:
        extensions.addprevious(timing)
    else:
        slide_element.append(timing)
