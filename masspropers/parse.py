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
# Same pattern, but keeping the whole span (not just its inner text) as a
# split delimiter, so the prose between two consecutive spans stays
# recoverable — used to find which citation an 'Allelúia' trails.
_REDITALIC_SPLIT_RE = re.compile(r"(<FONT COLOR=\"red\"><I>.*?</I></FONT>)", re.S)
# DivinumOfficium prints 'Allelúia'/'Alleluia' (never accented in English
# rendering, but this parses the Latin page, which always accents it) once
# after an Alleluia verse and twice after the Gradual verse it follows.
_ALLELUIA_RE = re.compile(r"allel[uú]ia", re.I)
# A red-italic label that's just a bare versicle/response letter ('℣.',
# '℟.', 'S.') — punctuation *within* a single oration (e.g. the Ember-day
# "℣. Flectamus genua. ℟. Levate." exchange before the prayer text), never
# the start of a second, separate oration. See parse_propers_prose().
_RUBRIC_LABEL_RE = re.compile(r"^[℣℟SVR]\.?$")
# The Collect/Postcommunion (never the Secret) re-print this stock "let us
# pray" call before *every* oration in the block, including the first —
# so it doesn't by itself count as the primary oration's real content when
# deciding whether a later label starts a second, separate oration. Covers
# only the two languages parse_propers_prose is ever run against.
_OREMUS_RE = re.compile(r"\b(oremus|let us pray|oremos)\.?", re.I)

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
    # Latin prose for this same non-scriptural proper, set only when the
    # --latin CLI flag requests it for this section. Parsed the same way as
    # prayer_text (parse_propers_prose(), same commemoration-dropping
    # behaviour) but run against the plain Latin page that's already fetched
    # for citations, so no extra fetch is needed. Scriptural sections don't
    # use this field — their Latin verse text is looked up straight from the
    # Vulgate CSV at EPUB-build time via the same Citations already on hand.
    latin_text: str | None = None
    # 'Allelúia, allelúia' sung *before* the first citation — the refrain
    # that opens a double-Alleluia Graduale block (Eastertide/the Pentecost
    # octave, where the Gradual proper is replaced by two Alleluia verses).
    # 0 outside those weeks. Each citation's own *trailing* Alleluia(s) — the
    # ordinary case, e.g. after the Gradual verse or after each Alleluia
    # verse — live on Citation.alleluia_after instead, since they belong to
    # one specific verse rather than the section as a whole.
    leading_alleluia: int = 0


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


def _count_alleluias(html_fragment: str) -> int:
    return len(_ALLELUIA_RE.findall(_clean(html_fragment)))


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
        # Nav links/title stripped first so pieces[0] below is pure prose —
        # otherwise the boilerplate 'Top / Next' DIV and the title's own
        # <FONT> markup (a different tag shape, so _REDITALIC_SPLIT_RE
        # doesn't split on it) would sit in front of the first real citation.
        content = _NAV_RE.sub("", _TITLE_RE.sub("", block, count=1))
        # On every day with a Sequence (Easter, Pentecost, Corpus Christi,
        # Requiem, ...), DivinumOfficium smuggles 'Sequentia' into the same
        # <TD> as 'Graduale' with no <TR><TD> boundary between them — the
        # block-split above can't separate them. Truncate at that embedded
        # title so the Sequence's own prose (which ends "Amen. Allelúia.")
        # can't be mistaken for this section's content, e.g. bleeding an
        # extra Alleluia onto the Gradual's last citation.
        next_title = _TITLE_RE.search(content)
        if next_title:
            content = content[: next_title.start()]
        pieces = _REDITALIC_SPLIT_RE.split(content)
        # pieces alternates prose, span, prose, span, ...; even indices are
        # prose, odd indices are the '<FONT COLOR="red"><I>...</I></FONT>'
        # spans themselves (citations and labels like '℣.' alike).
        last_citation: Citation | None = None
        section.leading_alleluia += _count_alleluias(pieces[0])
        for i in range(1, len(pieces), 2):
            cand = _clean(_REDITALIC_RE.search(pieces[i]).group(1))
            cit = _classify(cand, lang)
            if cit is not None:
                section.citations.append(cit)
                last_citation = cit
            trailing = pieces[i + 1] if i + 1 < len(pieces) else ""
            count = _count_alleluias(trailing)
            if last_citation is not None:
                last_citation.alleluia_after += count
            else:
                # An Alleluia refrain (or one trailing a label) before any
                # citation has been seen yet — belongs to the section, same
                # as the pieces[0] case above.
                section.leading_alleluia += count
        if section.citations or _clean(content):
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

    A day with a commemoration (of a lesser feast, an octave, an alternate
    votive collect, ...) gets a *second* oration appended into the same
    block, introduced by its own red-italic label (e.g. 'Conmemoración S.
    Joachim...', 'Pro S. Petro'). DivinumOfficium's non-English translations
    are frequently incomplete for exactly these secondary orations — even
    the vernacular-language page then silently falls back to English text
    for just that part — so rather than risk emitting a stray other-language
    paragraph, only the day's primary oration is kept; anything after such a
    label is dropped. This is distinct from the '℣.'/'℟.' versicle markers
    that punctuate a single oration (e.g. Ember-day "℣. Flectamus genua. ℟.
    Levate."), which are never a boundary — see _RUBRIC_LABEL_RE.
    """
    prose: dict[str, str] = {}
    blocks = re.split(r"<TR><TD[^>]*>", body)
    for block in blocks[1:]:
        tm = _TITLE_RE.search(block)
        if not tm:
            continue
        name = _clean(tm.group(1))
        rest = _NAV_RE.sub("", _TITLE_RE.sub("", block, count=1))
        # As in parse_propers_html: some days pack more than one proper part
        # into a single <TD> with no boundary between them (e.g. Ember days,
        # where a Collect is immediately followed by the next Lesson) --
        # truncate at that embedded title so its text can't bleed into this
        # section's prose. _TITLE_RE also matches the SIZE='+1' drop-cap
        # opening a prayer's closing doxology ('<FONT SIZE=\'+1\'...>P</...>
        # or nuestro Señor...'), so only a multi-character match is a real
        # title -- a drop cap is always a single letter.
        for next_title in _TITLE_RE.finditer(rest):
            if len(next_title.group(1).strip()) > 1:
                rest = rest[: next_title.start()]
                break
        pieces = _REDITALIC_SPLIT_RE.split(rest)
        kept = [pieces[0]]
        accumulated = _clean(pieces[0])
        i = 1
        while i < len(pieces):
            label = _clean(_REDITALIC_RE.search(pieces[i]).group(1))
            trailing = pieces[i + 1] if i + 1 < len(pieces) else ""
            has_real_content = bool(_OREMUS_RE.sub("", accumulated).strip())
            if not _RUBRIC_LABEL_RE.match(label) and has_real_content:
                # A real second-oration heading, appearing after the primary
                # oration's own text -- stop here and drop the rest.
                break
            kept.append(pieces[i])
            kept.append(trailing)
            accumulated += _clean(trailing)
            i += 2
        text = re.sub(r"\s+", " ", _clean("".join(kept))).strip()
        # A dropped second oration usually left its own "Oremus."/"Let us
        # pray." call-to-prayer dangling at the very end (it's plain prose,
        # not a red-italic label, so the loop above already committed it to
        # `kept` before spotting the label that triggered the break) -- trim
        # it so the text doesn't trail off mid-thought.
        matches = list(_OREMUS_RE.finditer(text))
        if matches and matches[-1].end() == len(text):
            text = text[: matches[-1].start()].strip()
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


# Short slug per season, per output language — used for the compact
# filename/title (see compact_name()). Deliberately not the same strings as
# classify_season()'s Latin labels, which are used for the Calibre tag.
_SEASON_SLUG: dict[str, dict[str, str]] = {
    "Adventus": {"es": "adviento", "en": "advent"},
    "Tempus Nativitatis": {"es": "navidad", "en": "christmastide"},
    "Tempus post Epiphaniam": {"es": "epifania", "en": "epiphany"},
    "Quadragesima": {"es": "cuaresma", "en": "lent"},
    "Tempus Paschale": {"es": "pascua", "en": "eastertide"},
    "Tempus post Pentecosten": {"es": "postpentecostes", "en": "postpentecost"},
}

_ROMAN_RE = re.compile(r"\b([IVXLCDM]+)\b")


def _slug_ascii(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[àáâã]", "a", s)
    s = re.sub(r"[èéê]", "e", s)
    s = re.sub(r"[ìíî]", "i", s)
    s = re.sub(r"[òóô]", "o", s)
    s = re.sub(r"[ùúû]", "u", s)
    s = re.sub(r"æ", "ae", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def compact_name(day_name: str, rank: str, lang: str = "es") -> str:
    """A short, human-readable name for the filename and EPUB title.

    Examples: 'ix-postpentecostes' (Dominica IX Post Pentecosten), 'ii-adviento'
    (Dominica II Adventus), 'sanctorale-pantaleonis' (a fixed feast with no
    numbered season — first significant word of the name, genitive form as
    DivinumOfficium writes it, not prettified to the nominative).

    Note: within a numbered Tempora week, this collides across different
    weekdays (e.g. every day of "Hebdomadam IX post Pentecosten" produces the
    same slug) — fine for this tool's actual use (the cron job only ever
    generates Sundays), but if you start generating weekday dates too, you'll
    need to disambiguate further.

    Heuristic over the rendered day name, same caveat as classify_season() —
    verify unusual/new day names by testing rather than assuming this is exact.
    """
    season = classify_season(day_name, rank)
    if season == "Sanctorale":
        # Skip title abbreviations (S., Ss., In, etc.) and short connectors
        # so e.g. "Ss. Petri et Pauli" slugs to "petri", not "ss".
        stop = {"et", "de", "in", "festo"}
        words = [
            w for w in re.split(r"\s+", day_name)
            if not w.endswith(".") and w.lower() not in stop and len(w) > 1
        ]
        first = words[0] if words else day_name
        return f"sanctorale-{_slug_ascii(first)}"

    m = _ROMAN_RE.search(day_name)
    ordinal = m.group(1).lower() if m else "x"
    return f"{ordinal}-{_SEASON_SLUG[season][lang]}"
