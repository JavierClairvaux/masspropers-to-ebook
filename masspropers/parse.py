"""Parse the missa.pl Propers=1 HTML page into structured sections.

The page produced by ``command=pray&content=1&Propers=1&lang1=lang2`` is very
regular machine-generated HTML:

* day header:   <P ALIGN="CENTER"><FONT COLOR="green">NAME ~ RANK</FONT></P>
* one <TR><TD> block per proper part, whose heading is
                <FONT SIZE='+1' COLOR="red"><B><I>Lectio</I></B></FONT>
* citations (the source files' ``!`` lines) render as
                <FONT COLOR="red"><I>Ps 17:19-20</I></FONT><br/>

The same red-italic markup is also used for non-citation labels ('℣.',
'de sanctissima Trinitate', 'Commemoratio ...', 'Antiphona 2'), so each
candidate is classified with the citation grammar:

* parses as a citation with a known book        -> keep;
* citation-shaped with verse punctuation (:,-)
  but unknown book                              -> hard error (extend BOOK_MAP);
* anything else                                 -> label, skip.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field

from .citations import (
    Citation,
    CitationSyntaxError,
    UnknownBookError,
    looks_like_citation,
    parse_citation,
)

# The FONT color is the liturgical colour of the day and may be absent
# entirely on white-vestment days (renders as '<FONT >').
_DAY_RE = re.compile(
    r"<P ALIGN=\"CENTER\"><FONT[^>]*>(.*?)</FONT>", re.S
)
_TITLE_RE = re.compile(
    r"<FONT SIZE='\+1' COLOR=\"red\"><B><I>\s*(.*?)\s*</I></B></FONT>", re.S
)
_REDITALIC_RE = re.compile(r"<FONT COLOR=\"red\"><I>(.*?)</I></FONT>", re.S)

# The page-navigation "Top / Next / Prev" links each block starts with —
# boilerplate UI, not content. Strip before extracting prose or checking
# whether a block has any real content.
_NAV_RE = re.compile(r"<DIV ALIGN='right'>.*?</DIV>", re.S)

# Fixed Ordinary-of-the-Mass parts (same text every day, not day-specific
# Propers) — excluded even though they now have prose text like the real
# Propers do, since they're not what this tool is for. Confirmed exact
# DivinumOfficium section names from divinum-officium/.../Ordo/Prayers.txt.
_ORDINARY_SECTIONS = {"Gloria", "Gloria1", "Credo"}


@dataclass
class Section:
    name: str                       # e.g. 'Introitus', 'Lectio'
    citations: list[Citation] = field(default_factory=list)
    # Set only for non-scriptural propers (Oratio/Secreta/Postcommunio etc.)
    # that have no Scripture citation to look up — DivinumOfficium's own
    # target-language prose is used verbatim instead. See parse_propers_prose().
    prayer_text: str | None = None


@dataclass
class DayPropers:
    day_name: str                   # e.g. 'Dominica II Post Pentecosten'
    rank: str                       # e.g. 'II. classis'
    sections: list[Section] = field(default_factory=list)

    def all_citations(self) -> list[tuple[str, Citation]]:
        return [(s.name, c) for s in self.sections for c in s.citations]


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return _html.unescape(text).strip()


def _classify(candidate: str, lang: str = "es") -> Citation | None:
    """Return a Citation, None for a label, or raise for unknown books."""
    if not looks_like_citation(candidate):
        return None
    try:
        return parse_citation(candidate, lang)
    except UnknownBookError:
        # 'Antiphona 2' or 'c. 12' are labels: a lone trailing number with no
        # verse punctuation. Anything with :,- in its reference part really
        # is a citation whose book we failed to map — fail loudly.
        refs_part = re.sub(r"^\s*[\dIV]{0,4}\.?\s*[^\d]+", "", candidate)
        if re.search(r"\d\s*[:,\-]\s*\d", refs_part):
            raise
        return None
    except CitationSyntaxError:
        return None


def parse_propers_html(body: str, lang: str = "es") -> DayPropers:
    """Parse the Latin-language propers page. *lang* only sets the display
    language of the extracted Citations; parsing itself is unaffected."""
    m = _DAY_RE.search(body)
    day_name, rank = "Unknown day", ""
    if m:
        header = _clean(m.group(1))
        if "~" in header:
            day_name, rank = (p.strip() for p in header.split("~", 1))
        else:
            day_name = header

    day = DayPropers(day_name=day_name, rank=rank)

    # Split into <TD> blocks; each proper part lives in its own block.
    blocks = re.split(r"<TR><TD[^>]*>", body)
    for block in blocks[1:]:
        tm = _TITLE_RE.search(block)
        if not tm:
            continue
        name = _clean(tm.group(1))
        if name in _ORDINARY_SECTIONS:
            continue
        section = Section(name=name)
        for cand in _REDITALIC_RE.findall(block):
            cand = _clean(cand)
            cit = _classify(cand, lang)
            if cit is not None:
                section.citations.append(cit)
        rest = _NAV_RE.sub("", _TITLE_RE.sub("", block, count=1))
        if section.citations or _clean(rest):
            day.sections.append(section)
    return day


def parse_propers_prose(body: str) -> dict[str, str]:
    """Map section name -> plain prose text, for every proper part on the page.

    No citation parsing/classification at all (deliberately) — this is meant
    to run against DivinumOfficium's own vernacular rendering (Espanol,
    English, ...), whose citation abbreviations aren't in BOOK_MAP and would
    otherwise risk an UnknownBookError for sections we don't even need
    citations from. Callers only use the prose for sections that came back
    with zero citations from the Latin-language parse (Oratio/Secreta/
    Postcommunio) — the actual Scripture text still comes from the Bible CSV
    via the Latin-parsed citations, never from here.

    Note the section headings in the returned dict are themselves translated
    by DivinumOfficium's renderer (Oratio -> 'Colecta' on the Spanish page,
    'Collect' on the English one), so callers must look up by the rendered
    name; see epub.SECTION_ES / epub.SECTION_EN.
    """
    prose: dict[str, str] = {}
    blocks = re.split(r"<TR><TD[^>]*>", body)
    for block in blocks[1:]:
        tm = _TITLE_RE.search(block)
        if not tm:
            continue
        name = _clean(tm.group(1))
        rest = _NAV_RE.sub("", _TITLE_RE.sub("", block, count=1))
        text = re.sub(r"\s+", " ", _clean(rest)).strip()
        if text:
            prose[name] = text
    return prose


# Ordered (pattern, season) checks against day_name/rank text. Order matters:
# e.g. "post Pentecosten" must be checked before a bare "Pentecost" match
# (Pentecost Sunday itself is Paschaltide, but every following Sunday's name
# also contains "Pentecosten" as part of "post Pentecosten"/"post Octavam
# Pentecostes"); likewise "post Epiphaniam" (its own season) before a bare
# "Epiphania" match (the feast day itself, within Christmastide). This is a
# heuristic over DivinumOfficium's rendered day name, not a lookup into its
# own calendar engine — treat edge cases (unusual octave/vigil names) as
# discoverable-by-testing rather than guaranteed correct.
_SEASON_PATTERNS: list[tuple[str, str]] = [
    (r"post\s+(octavam\s+)?pentecost", "Tempus post Pentecosten"),
    (r"post\s+epiphaniam", "Tempus post Epiphaniam"),
    (r"quadragesim", "Quadragesima"),
    (r"in\s+palmis|in\s+cena\s+domini|in\s+parasceve|sabbato\s+sancto", "Quadragesima"),
    (r"adventus|adventu\b", "Adventus"),
    (r"pascha|resurrectionis|ascensionis|pentecost", "Tempus Paschale"),
    (r"nativitat|epiphania", "Tempus Nativitatis"),
]


def classify_season(day_name: str, rank: str = "") -> str:
    """Best-effort Latin liturgical-season label from the resolved day name.

    Falls back to 'Sanctorale' for fixed feast/saints' days that don't fall
    within a named Tempora season (the common case for Sancti-calendar days).
    """
    haystack = f"{day_name} {rank}".lower()
    for pattern, season in _SEASON_PATTERNS:
        if re.search(pattern, haystack):
            return season
    return "Sanctorale"
