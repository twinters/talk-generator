"""Animations on slides, which python-pptx can't make: the timing XML that PowerPoint writes for them.

A slide can have several of these, each adding its clicks after those the slide has already:
- a chart whose series after the first appear on clicks, one by one, wiping in from the left. On a trend chart, that
  makes a second line draw itself across the chart as the punchline;
- shapes that fade in together on a click, such as a Venn diagram's overlap, or a matrix's dot with its name, and the
  elements of a deck that appear on a click of their own (a quiz's answer);
- columns that fade in click by click, the one before dimming, as the 2019 template's column slides have them (a
  themed deck's columns);
- a layout's animation, copied onto a slide made from it (the 2019 template's columns, which appear click by click).
And its videos play by themselves, looping and without sound, the way the gifs they stand in for do: as the effect
that shows them plays, or as the slide comes up if they're there from the start.
In the editor, and in viewers that don't play animations, everything simply shows, and a video shows its poster frame.

The templates below leave their time nodes unnumbered (0): every change ends by numbering the slide's (_settle).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, Final, Literal

from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn

from talkgenerator.util import video_util

# The main sequence: what happens on clicks, or by itself (time node 2, the first in the root's list)
_MAIN_SEQUENCE: Final = (
    '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst/></p:cTn>'
    '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
    '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
    "</p:seq>"
)
# A slide's timing: the root (time node 1), holding the main sequence and, after it, the media. After the time nodes
# comes the build list: how the shapes with text build, for each of their effects
_TIMING: Final = (
    '<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
    f"{_MAIN_SEQUENCE}"
    "</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"
)

# A step of the main sequence, with the group of effects in it that start together
_STEP: Final = (
    '<p:par><p:cTn id="0" fill="hold"><p:stCondLst>{start}</p:stCondLst><p:childTnLst>'
    '<p:par><p:cTn id="0" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    "{effects}"
    "</p:childTnLst></p:cTn></p:par>"
    "</p:childTnLst></p:cTn></p:par>"
)
_ON_A_CLICK: Final = '<p:cond delay="indefinite"/>'
# As the main sequence (time node 2) starts, which it does with the slide, instead of on a click
_AS_THE_SLIDE_COMES_UP: Final = '<p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond>'

# CHARTS

# A chart's series, as an animation target (categoryIdx -3: all of them; bldStep: a series at a time)
_SERIES_TARGET: Final = (
    '<p:tgtEl><p:spTgt spid="{spid}"><p:graphicEl>'
    '<a:chart seriesIdx="{series}" categoryIdx="-3" bldStep="series"/>'
    "</p:graphicEl></p:spTgt></p:tgtEl>"
)

# The series appears, wiping in from the left in a second (PowerPoint's preset 22, "Wipe", subtype 8)
_WIPE_IN: Final = (
    '<p:par><p:cTn id="0" presetID="22" presetClass="entr" presetSubtype="8" fill="hold" grpId="0" '
    'nodeType="clickEffect"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:set><p:cBhvr><p:cTn id="0" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
    "{target}<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
    '<p:to><p:strVal val="visible"/></p:to></p:set>'
    '<p:animEffect transition="in" filter="wipe(left)"><p:cBhvr><p:cTn id="0" dur="1000"/>{target}</p:cBhvr>'
    "</p:animEffect>"
    "</p:childTnLst></p:cTn></p:par>"
)

# Built a series at a time, without drawing the chart's background (its axes, legend and first series) first
_SERIES_BUILD: Final = (
    '<p:bldGraphic spid="{spid}" grpId="0"><p:bldSub><a:bldChart bld="series" animBg="0"/></p:bldSub></p:bldGraphic>'
)

# SHAPES

# The shape appears, fading in in half a second (PowerPoint's preset 10, "Fade")
_FADE_IN: Final = (
    '<p:par><p:cTn id="0" presetID="10" presetClass="entr" presetSubtype="0" fill="hold" grpId="{group}" '
    'nodeType="{node}"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:set><p:cBhvr><p:cTn id="0" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
    "<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
    '<p:to><p:strVal val="visible"/></p:to></p:set>'
    '<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="0" dur="500"/>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
    "</p:childTnLst></p:cTn></p:par>"
)

# The shape dims to half its opacity until the slide ends (PowerPoint's preset 9, "Transparency"), as the 2019
# template's columns do when the next one appears
_DIM: Final = (
    '<p:par><p:cTn id="0" presetID="9" presetClass="emph" presetSubtype="0" grpId="{group}" nodeType="{node}">'
    '<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:set><p:cBhvr><p:cTn id="0" dur="indefinite"/><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
    "<p:attrNameLst><p:attrName>style.opacity</p:attrName></p:attrNameLst></p:cBhvr>"
    '<p:to><p:strVal val="0.5"/></p:to></p:set>'
    '<p:animEffect filter="image" prLst="opacity: 0.5"><p:cBhvr rctx="IE"><p:cTn id="0" dur="indefinite"/>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
    "</p:childTnLst></p:cTn></p:par>"
)

# How a shape with text builds for one of its effects: as one object, its text with it
_SHAPE_BUILD: Final = '<p:bldP spid="{spid}" grpId="{group}" animBg="1"/>'

Effect = Literal["appear", "dim"]
_EFFECTS: Final[dict[str, str]] = {"appear": _FADE_IN, "dim": _DIM}

# VIDEOS

# A video plays from its start (PowerPoint's "Play" media effect, preset 1), for as long as it lasts
_PLAY: Final = (
    '<p:par><p:cTn id="0" presetID="1" presetClass="mediacall" presetSubtype="0" fill="hold" '
    'nodeType="{node}"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
    '<p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr><p:cTn id="0"{duration} fill="hold"/>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:cmd>'
    "</p:childTnLst></p:cTn></p:par>"
)

# The video itself: it loops until the slide ends ("Loop until Stopped"), without sound ("Mute"), as gifs have none
_MEDIA: Final = (
    '<p:video><p:cMediaNode vol="80000" mute="1">'
    '<p:cTn id="0" repeatCount="indefinite" fill="hold" display="0">'
    '<p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cMediaNode></p:video>'
)

_VIDEOS: Final = "./p:cSld/p:spTree//p:pic[p:nvPicPr/p:nvPr/a:videoFile]"


def reveal_chart_series(slide: Any, chart_frame: Any, series_count: int) -> None:
    """Have the chart's series after the first appear on clicks, one by one."""
    if series_count < 2:
        return
    timing = _timing(slide)
    for series in range(1, series_count):
        target = _SERIES_TARGET.format(spid=chart_frame.shape_id, series=series)
        _sequence(timing).append(_parsed(_STEP.format(start=_ON_A_CLICK, effects=_WIPE_IN.format(target=target))))
    _builds(timing).append(_parsed(_SERIES_BUILD.format(spid=chart_frame.shape_id)))
    _settle(slide)


def reveal_shapes(slide: Any, shapes: Sequence[Any]) -> None:
    """Have the shapes appear together on a click, fading in."""
    if shapes:
        _add_click(slide, [("appear", shape) for shape in shapes])
        _settle(slide)


def reveal_clicks(slide: Any, clicks: Sequence[Sequence[Any]]) -> None:
    """Have each group of shapes appear on a click of its own, in order (the first group on the slide's next click),
    fading in together: what a deck's elements that appear on a click are drawn with (such as a quiz's answer)."""
    for shapes in clicks:
        if shapes:
            _add_click(slide, [("appear", shape) for shape in shapes])
    _settle(slide)


def reveal_columns(slide: Any, columns: Sequence[Sequence[Any]]) -> None:
    """Show the columns (each the shapes it's drawn with) click by click, as the 2019 template's column slides do: of
    two, the first is there from the start, and the second appears on the click as the first dims; of three, each
    appears on a click, the one before dimming. They fade in (where the template's appear at once)."""
    first = 1 if len(columns) == 2 else 0
    before: Sequence[Any] = columns[0] if first else ()
    for column in columns[first:]:
        if not column:
            continue  # (nothing to show: the one before stays as it is)
        _add_click(slide, [("appear", shape) for shape in column] + [("dim", shape) for shape in before])
        before = column
    _settle(slide)


def play_videos(slide: Any) -> None:
    """Have the slide's videos play by themselves, looping and without sound: as the slide comes up, or as the effect
    that shows them plays. (The timing python-pptx gives a video plays it once it's clicked.)"""
    if slide.element.xpath(_VIDEOS):
        _timing(slide)
        _settle(slide)


def animate_as(slide: Any, timing: Any, ids: Mapping[str, str]) -> None:
    """Give the slide a copy of a layout's animation (ids: the slide's shapes' ids, by the layout's), without what
    animates shapes the slide doesn't have (such as an empty caption)."""
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
    for target in list(copied.iter(qn("p:spTgt"))):
        spid = ids.get(target.get("spid"))
        if spid is None:
            _drop_effect(target)
        else:
            target.set("spid", spid)
    sequence = _sequence(copied)
    if sequence is None:
        return
    steps = [step for step in sequence if any(node.get("presetClass") for node in step.iter(qn("p:cTn")))]
    if not steps:
        return  # (every click would show nothing)
    own = _timing(slide)
    _sequence(own).extend(steps)
    builds = copied.find(qn("p:bldLst"))
    if builds is not None and len(builds):
        _builds(own).extend(list(builds))
    _settle(slide)


# THE SLIDE'S TIMING


def _timing(slide: Any) -> Any:
    """The slide's timing, with its main sequence: a new one, if it has none (or only what python-pptx gave a video
    it added: the media, without a sequence). It goes after the slide's colour map and transition, before its
    extensions."""
    timing = slide.element.find(qn("p:timing"))
    if timing is None:
        timing = _parsed(_TIMING)
        extensions = slide.element.find(qn("p:extLst"))
        if extensions is not None:
            extensions.addprevious(timing)
        else:
            slide.element.append(timing)
    if _sequence(timing) is None:
        _root(timing).insert(0, _parsed(_MAIN_SEQUENCE))
    return timing


def _root(timing: Any) -> Any:
    """The root's list: the main sequence, then the media."""
    return timing.find(f"{qn('p:tnLst')}/{qn('p:par')}/{qn('p:cTn')}/{qn('p:childTnLst')}")


def _sequence(timing: Any) -> Any:
    """The main sequence's list of steps (None if the timing has no main sequence)."""
    return timing.find(f".//{qn('p:cTn')}[@nodeType='mainSeq']/{qn('p:childTnLst')}")


def _builds(timing: Any) -> Any:
    """The timing's build list: a new one, after its time nodes, if it has none."""
    builds = timing.find(qn("p:bldLst"))
    if builds is None:
        builds = _parsed("<p:bldLst/>")
        timing.find(qn("p:tnLst")).addnext(builds)
    return builds


def _add_click(slide: Any, effects: Sequence[tuple[Effect, Any]]) -> None:
    """Add a click to the end of the slide's main sequence, which does each effect to its shape: the first as the
    click's own, the others with it."""
    timing = _timing(slide)
    step = _parsed(_STEP.format(start=_ON_A_CLICK, effects=""))
    _sequence(timing).append(step)
    together = step.find(f"./{qn('p:cTn')}/{qn('p:childTnLst')}/{qn('p:par')}/{qn('p:cTn')}/{qn('p:childTnLst')}")
    for index, (effect, shape) in enumerate(effects):
        spid = str(shape.shape_id)
        group = _next_group(timing, spid)
        node = "clickEffect" if index == 0 else "withEffect"
        together.append(_parsed(_EFFECTS[effect].format(spid=spid, group=group, node=node)))
        if shape.element.tag == qn("p:sp"):  # (a shape that can hold text; a picture builds as it is)
            _builds(timing).append(_parsed(_SHAPE_BUILD.format(spid=spid, group=group)))


def _next_group(timing: Any, spid: str) -> int:
    """The shape's build group for a new effect on it: one more than for its last (as its appearing's, then its
    dimming's)."""
    groups = [
        int(node.get("grpId"))
        for node in timing.find(qn("p:tnLst")).iter(qn("p:cTn"))
        if node.get("grpId") is not None and node.find(f".//{qn('p:spTgt')}[@spid='{spid}']") is not None
    ]
    return max(groups, default=-1) + 1


def _settle(slide: Any) -> None:
    """Finish the slide's timing after a change: its videos play with the effects that show them now (or as the slide
    comes up), every time node has a number of its own, and a timing that would do nothing goes."""
    timing = slide.element.find(qn("p:timing"))
    if timing is None or _sequence(timing) is None:
        return
    sequence, root = _sequence(timing), _root(timing)
    for play in [node for node in sequence.iter(qn("p:cTn")) if node.get("presetClass") == "mediacall"]:
        _remove_effect(play.getparent())
    for media in root.findall(qn("p:video")):
        root.remove(media)
    _play_where_they_appear(slide, sequence)
    builds = timing.find(qn("p:bldLst"))
    if builds is not None and not len(builds):
        timing.remove(builds)
    if not len(sequence):
        slide.element.remove(timing)
        return
    for number, node in enumerate(timing.find(qn("p:tnLst")).iter(qn("p:cTn")), 1):  # (root 1, main sequence 2)
        node.set("id", str(number))


def _play_where_they_appear(slide: Any, sequence: Any) -> None:
    """Play the slide's videos with the effects that make them appear, or (those that are there from the start) as the
    slide comes up; looping and without sound."""
    videos = slide.element.xpath(_VIDEOS)
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
        play = _PLAY.format(node="withEffect", duration=duration, spid=spid)
        entrance.getparent().addnext(_parsed(play))  # (in the group of the effect that shows it)
    if from_the_start:
        effects = "".join(
            _PLAY.format(node="afterEffect" if number == 0 else "withEffect", duration=duration, spid=spid)
            for number, (spid, duration) in enumerate(from_the_start)
        )
        sequence.insert(0, _parsed(_STEP.format(start=_AS_THE_SLIDE_COMES_UP, effects=effects)))
    root = sequence.getparent().getparent().getparent()  # (the main sequence's seq, in the root's list)
    for video in videos:
        root.append(_parsed(_MEDIA.format(spid=video.xpath("./p:nvPicPr/p:cNvPr/@id")[0])))


def _drop_effect(target: Any) -> None:
    """Take out the effect that animates the target, and what's left empty around it."""
    node = target.getparent()
    while node is not None and not (node.tag == qn("p:par") and _is_effect(node)):
        node = node.getparent()
    if node is None or node.getparent() is None:
        return  # (taken out already: an effect can name its shape twice, as a dimming does)
    _remove_effect(node)


def _remove_effect(effect: Any) -> None:
    """Take the effect (its par) out of its group, and the group and step it leaves empty."""
    node = effect
    while node is not None and node.tag == qn("p:par"):
        parent = node.getparent()
        parent.remove(node)
        if len(parent) or parent.tag != qn("p:childTnLst"):
            return
        node = parent.getparent().getparent()  # (the empty list's time node, and its par)


def _is_effect(par: Any) -> bool:
    node = par.find(qn("p:cTn"))
    return node is not None and node.get("presetClass") is not None


_TAG_NAME: Final = re.compile(r"<[\w:]+")


def _parsed(xml: str) -> Any:
    """A part of a timing (as the templates above have it, without namespaces), parsed."""
    name = _TAG_NAME.match(xml)
    if name is None:
        raise ValueError(f"Not an element: {xml[:40]!r}")
    return parse_xml(f"{xml[: name.end()]} {nsdecls('p', 'a')}{xml[name.end() :]}")


def _video_bytes(slide: Any, video: Any) -> bytes:
    """The video file a slide's video shape plays."""
    part_id = video.xpath("./p:nvPicPr/p:nvPr/a:videoFile/@r:link")[0]
    return bytes(slide.part.related_part(part_id).blob)
