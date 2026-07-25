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


@dataclass
class Section:
    name: str                       # e.g. 'Introitus', 'Lectio'
    citations: list[Citation] = field(default_factory=list)


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


def _classify(candidate: str) -> Citation | None:
    """Return a Citation, None for a label, or raise for unknown books."""
    if not looks_like_citation(candidate):
        return None
    try:
        return parse_citation(candidate)
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


def parse_propers_html(body: str) -> DayPropers:
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
        section = Section(name=name)
        for cand in _REDITALIC_RE.findall(block):
            cand = _clean(cand)
            cit = _classify(cand)
            if cit is not None:
                section.citations.append(cit)
        if section.citations:
            day.sections.append(section)
    return day
