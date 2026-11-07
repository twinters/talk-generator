"""License classes, and the policies that pick the classes a talk allows (docs/v5-plan.md, section 10.2).

Every image source declares the class of its images (some per image, such as Openverse and Wikimedia Commons, whose
images have licenses of their own), as it declares how a browser may show them:

| Class | What |
| --- | --- |
| `public-domain` | public domain and CC0 |
| `open` | Creative Commons BY and BY-SA |
| `stock` | the Unsplash, Pexels and Pixabay licenses |
| `generated` | AI images, under the provider's terms |
| `fair-use` | Reddit, GIPHY, meme templates, InspiroBot, ShitpostBot |

A talk's license policy picks the classes it allows, and the image search keeps to it: `all` (the default) allows
every class, and `open` everything but fair use, for decks shown in public (what v4's `ted` schema did with its own
copyright-free slide generators). A policy can also name its classes, as "public-domain,open".

Images without a class are files of talkgenerator's own, or a plan's own pictures: every policy allows them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, get_args

from talkgenerator.models.deck import LicenseClass

CLASSES: Final[tuple[LicenseClass, ...]] = get_args(LicenseClass)
DESCRIPTIONS: Final[dict[LicenseClass, str]] = {
    "public-domain": "public domain and CC0",
    "open": "Creative Commons BY and BY-SA",
    "stock": "the Unsplash, Pexels and Pixabay licenses",
    "generated": "AI images, under the provider's terms",
    "fair-use": "Reddit's posts, GIPHY's gifs, Imgflip's meme templates, InspiroBot's posters and ShitpostBot's images",
}
# The classes whose credits name the license: Creative Commons licenses ask for it (and a public domain mark tells
# what may be done with the image). Stock photos are credited to their photographer and platform, as the platforms'
# guidelines ask, and fair use has no license to name.
SHOWN: Final[frozenset[LicenseClass]] = frozenset({"public-domain", "open", "generated"})

# The stock licenses: what an image's credit and its deck say it's under
UNSPLASH_LICENSE: Final = ("Unsplash License", "https://unsplash.com/license")
PEXELS_LICENSE: Final = ("Pexels License", "https://www.pexels.com/license/")
PIXABAY_LICENSE: Final = ("Pixabay Content License", "https://pixabay.com/service/license-summary/")
CC0: Final = ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/")
PUBLIC_DOMAIN_MARK: Final = ("public domain", "https://creativecommons.org/publicdomain/mark/1.0/")


@dataclass(frozen=True)
class LicensePolicy:
    """The license classes a talk allows, by name ("all", "open", or its classes, as "public-domain,open")."""

    name: str
    classes: frozenset[LicenseClass]
    description: str = ""

    def allows(self, license_class: LicenseClass | None) -> bool:
        """Whether an image of the class may go in the talk (one without a class, a file of its own, always may)."""
        return license_class is None or license_class in self.classes

    def narrowed(self, classes: Iterable[LicenseClass] | None) -> LicensePolicy:
        """The policy, allowing only the given classes of its own (all of them, without any)."""
        if classes is None:
            return self
        kept = self.classes & frozenset(classes)
        return LicensePolicy(_name(kept), kept)


ALL: Final = LicensePolicy("all", frozenset(CLASSES), "every image: public domain, open, stock, generated and fair use")
OPEN: Final = LicensePolicy(
    "open",
    frozenset(CLASSES) - {"fair-use"},
    "everything but fair use (memes, gifs, Reddit's posts): public domain, Creative Commons BY and BY-SA, stock and "
    "generated images, for decks shown in public",
)
POLICIES: Final[dict[str, LicensePolicy]] = {ALL.name: ALL, OPEN.name: OPEN}
DEFAULT: Final = ALL.name


def policy(spec: str | Iterable[str] | LicensePolicy | None) -> LicensePolicy:
    """The policy a spec names: "all", "open", or license classes (as a list, or separated by commas). None is "all".
    A ValueError for a class or policy there isn't."""
    if isinstance(spec, LicensePolicy):
        return spec
    if spec is None:
        return ALL
    names = [part.strip() for part in spec.split(",")] if isinstance(spec, str) else [str(part) for part in spec]
    names = [name for name in names if name]
    if len(names) == 1 and names[0] in POLICIES:
        return POLICIES[names[0]]
    unknown = [name for name in names if name not in CLASSES]
    if unknown or not names:
        raise ValueError(
            f"There's no license policy {spec!r}: it's one of {', '.join(POLICIES)}, or license classes separated by "
            f"commas ({', '.join(CLASSES)})"
        )
    classes = frozenset(name for name in CLASSES if name in names)
    return _named(classes)


def _named(classes: frozenset[LicenseClass]) -> LicensePolicy:
    for known in POLICIES.values():
        if known.classes == classes:
            return known
    return LicensePolicy(_name(classes), classes, "only " + ", ".join(DESCRIPTIONS[name] for name in _ordered(classes)))


def _name(classes: frozenset[LicenseClass]) -> str:
    for known in POLICIES.values():
        if known.classes == classes:
            return known.name
    return ",".join(_ordered(classes))


def _ordered(classes: frozenset[LicenseClass]) -> list[LicenseClass]:
    return [name for name in CLASSES if name in classes]


def catalog() -> list[dict[str, str]]:
    """The policies, and the policies of one license class, for a settings menu or an agent: name, what it allows.
    (The class "open" alone isn't one: "open" names the policy, as in the plan, docs/v5-plan.md 10.2.)"""
    entries = [{"name": known.name, "description": known.description} for known in POLICIES.values()]
    entries += [{"name": name, "description": f"only {DESCRIPTIONS[name]}"} for name in CLASSES if name not in POLICIES]
    return entries


# READING LICENSES


# A Creative Commons license's code, as Openverse gives it ("by-sa") or in a name ("CC BY-SA 4.0")
_CC_NAME: Final = re.compile(r"\bcc[\s-]+(by(?:[\s-]+(?:sa|nc|nd))*)\b(?:[\s-]+(\d(?:\.\d)?))?", re.IGNORECASE)


def creative_commons(code: str, version: str | None = None) -> tuple[LicenseClass, str, str] | None:
    """A Creative Commons license (or public domain mark), by its code ("by", "by-sa", "cc0", "pdm") and version: its
    class, its name as a credit shows it, and its deed. None for a license that isn't open: one that forbids
    commercial use or adaptations (NC, ND), which a deck shown at a paid show, in a theme's colours, can't keep to."""
    code = code.strip().lower().replace(" ", "-")
    if code in ("cc0", "zero"):
        return ("public-domain", *CC0)
    if code in ("pdm", "pd", "publicdomain", "public-domain"):
        return ("public-domain", *PUBLIC_DOMAIN_MARK)
    if code in ("by", "by-sa"):
        version = (version or "4.0").strip()
        name = f"CC {code.upper()} {version}"
        return "open", name, f"https://creativecommons.org/licenses/{code}/{version}/"
    return None


def from_name(name: str | None, code: str | None = None, url: str | None = None) -> tuple[LicenseClass, str] | None:
    """The class of a license by its short name (as Wikimedia Commons names them: "CC BY-SA 4.0", "Public domain",
    "CC0"), or its code ("cc-by-sa-4.0", "pd"), and the name to show. None when neither says: a license that isn't
    open (NC, ND), or none at all."""
    text = " ".join(part for part in (name, code, url) if part).lower()
    if not text.strip():
        return None
    shown = (name or code or "").strip()
    if "cc0" in text or "cc-zero" in text or "publicdomain/zero" in text:
        return "public-domain", "CC0"
    if "public domain" in text or re.search(r"(?:^|[\s(/_-])pd(?:$|[\s)/_-])", text) or "publicdomain" in text:
        return "public-domain", shown or "public domain"
    found = _CC_NAME.search(text) or re.search(r"\b(by(?:-(?:sa|nc|nd))*)-(\d(?:\.\d)?)\b", text)
    if found is not None:
        parts = re.split(r"[\s-]+", found.group(1).lower())
        if "nc" in parts or "nd" in parts:
            return None
        return "open", shown or f"CC {'-'.join(parts).upper()}"
    if "gfdl" in text or "free art" in text or "attribution" in text:  # (free licenses that ask for credit)
        return "open", shown
    return None
