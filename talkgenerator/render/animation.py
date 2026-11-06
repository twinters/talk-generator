"""Animations on slides, which python-pptx can't make: the timing XML that PowerPoint writes for them.

For now four:
- a chart whose series after the first appear on clicks, one by one, wiping in from the left. On a trend chart, that
  makes a second line draw itself across the chart as the punchline;
- shapes that fade in together on a click, such as a Venn diagram's overlap, or a matrix's dot with its name;
- videos that play by themselves as their slide comes up, looping and without sound, the way the gifs they stand in
  for do;
- a layout's animation, copied onto a slide made from it (the 2019 template's columns appear click by click, the
  one before dimming), with the slide's videos playing as their column appears.
In the editor, and in viewers that don't play animations, everything simply shows, and a video shows its poster frame.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from copy import deepcopy
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


def animate_as(slide: Any, timing: Any, ids: Mapping[str, str]) -> None:
    """Give the slide a copy of a layout's animation as its own (ids: the slide's shapes' ids, by the layout's), without
    what animates shapes the slide doesn't have (such as an empty caption), and with the slide's videos playing as
    they appear, or as the slide comes up if they're there from the start (the slide gets this as its only
    animation)."""
    copied = deepcopy(timing)
    # How the layout's shapes build (their text as a whole, or by paragraph), as the slide's: only shapes with text
    # build so (a picture or a video that took a placeholder's place has nothing to build)
    texts = set(slide.element.xpath("./p:cSld/p:spTree//p:sp[p:txBody]/p:nvSpPr/p:cNvPr/@id"))
    for build in list(copied.iter(qn("p:bldP"))):
        spid = ids.get(build.get("spid"))
        if spid in texts:
            build.set("spid", spid)
        else:
            build.getparent().remove(build)
    builds = copied.find(qn("p:bldLst"))
    if builds is not None and not len(builds):
        copied.remove(builds)
    for target in list(copied.iter(qn("p:spTgt"))):
        spid = ids.get(target.get("spid"))
        if spid is None:
            _drop_effect(target)
        else:
            target.set("spid", spid)
    sequence = copied.find(f".//{qn('p:cTn')}[@nodeType='mainSeq']/{qn('p:childTnLst')}")
    if sequence is None:
        return
    for step in list(sequence):
        if not any(node.get("presetClass") for node in step.iter(qn("p:cTn"))):
            sequence.remove(step)  # (a click that would show nothing)
    _play_where_they_appear(slide, sequence)
    if not len(sequence):
        return
    for number, node in enumerate(copied.find(qn("p:tnLst")).iter(qn("p:cTn")), 1):  # (root 1, main sequence 2)
        node.set("id", str(number))
    _replace_timing(slide, copied)


def _drop_effect(target: Any) -> None:
    """Take out the effect that animates the target, and what's left empty around it."""
    node = target.getparent()
    while node is not None and not (node.tag == qn("p:par") and _is_effect(node)):
        node = node.getparent()
    if node is None or node.getparent() is None:
        return  # (taken out already: an effect can name its shape twice, as a dimming does)
    while node is not None and node.tag == qn("p:par"):
        parent = node.getparent()
        parent.remove(node)
        if len(parent) or parent.tag != qn("p:childTnLst"):
            return
        node = parent.getparent().getparent()  # (the empty list's time node, and its par)


def _is_effect(par: Any) -> bool:
    node = par.find(qn("p:cTn"))
    return node is not None and node.get("presetClass") is not None


def _play_where_they_appear(slide: Any, sequence: Any) -> None:
    """Play the slide's videos with the effects that make them appear, or (those that are there from the start) as the
    slide comes up; looping and without sound."""
    videos = slide.element.xpath("./p:cSld/p:spTree//p:pic[p:nvPicPr/p:nvPr/a:videoFile]")
    if not videos:
        return
    from_the_start = []
    for video in videos:
        spid = video.xpath("./p:nvPicPr/p:cNvPr/@id")[0]
        seconds = video_util.duration(_video_bytes(slide, video))
        duration = f' dur="{round(seconds * 1000)}"' if seconds else ""
        entrance = next(
            (
                node
                for node in sequence.iter(qn("p:cTn"))
                if node.get("presetClass") == "entr" and node.find(f".//{qn('p:spTgt')}[@spid='{spid}']") is not None
            ),
            None,
        )
        if entrance is None:
            from_the_start.append((spid, duration))
            continue
        play = _PLAY.format(effect=0, call=0, node_type="withEffect", duration=duration, spid=spid)
        entrance.getparent().addnext(_parsed(play))  # (in the group of the effect that shows it)
    if from_the_start:
        effects = "".join(
            _PLAY.format(
                effect=0, call=0, node_type="afterEffect" if number == 0 else "withEffect", duration=duration, spid=spid
            )
            for number, (spid, duration) in enumerate(from_the_start)
        )
        sequence.insert(0, _parsed(_ON_ITS_OWN.format(effects=effects)))
    root = sequence.getparent().getparent().getparent()  # (the main sequence's seq, in the root's list)
    for video in videos:
        spid = video.xpath("./p:nvPicPr/p:cNvPr/@id")[0]
        root.append(_parsed(_MEDIA.format(node=0, spid=spid)))


def _parsed(xml: str) -> Any:
    """A time node's XML (as the templates above have it, without namespaces), parsed."""
    tag = xml[1 : xml.index(">")]
    return parse_xml(xml.replace(f"<{tag}>", f"<{tag} {nsdecls('p', 'a')}>", 1))


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
