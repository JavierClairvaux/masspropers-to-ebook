"""Assemble a minimal EPUB 2 for an e-ink reader (Xteink X3 / CrossPoint).

Deliberately spartan: no embedded fonts, no images, tiny CSS, XHTML 1.1
content documents. Built with the stdlib zipfile module.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sys
import uuid
import zipfile
from xml.sax.saxutils import escape

from .bible import Bible, MissingVerseError
from .parse import DayPropers, classify_season, compact_name

# Traditional Spanish names for the proper parts, in their liturgical order.
# Unmapped section names fall back to the Latin name as-is.
SECTION_ES = {
    "Introitus": "Introito",
    "Oratio": "Colecta",
    "Lectio": "Epístola",
    "Graduale": "Gradual",
    "GradualeP": "Aleluya",
    "Tractus": "Tracto",
    "Sequentia": "Secuencia",
    "Evangelium": "Evangelio",
    "Offertorium": "Ofertorio",
    "Secreta": "Secreta",
    "Prefatio": "Prefacio",
    "Communio": "Comunión",
    "Postcommunio": "Poscomunión",
}

# Traditional English names for the same parts. Double duty, exactly like
# SECTION_ES: display names in the book, *and* the key cli.py looks the
# non-scriptural prose up by in DivinumOfficium's English rendering.
#
# The rendered headings were verified empirically against the English page
# (missa.pl lang1=lang2=English, the <FONT SIZE='+1' COLOR="red"><B><I>...
# headings) over a sample of ~70 days spanning Advent through Pentecost:
# DivinumOfficium translates only Oratio -> 'Collect', Lectio -> 'Lesson',
# Graduale -> 'Gradual' and Evangelium -> 'Gospel', and leaves Introitus,
# Offertorium, Secreta, Prefatio, Communio and Postcommunio in Latin. The
# entries below that differ from those rendered strings (Introit, Epistle,
# Secret, Preface, Communion, Postcommunion) are therefore display-only; the
# prose lookup for those falls through to cli.py's Latin-name fallback, which
# is what DivinumOfficium actually emits. Verified that every section that can
# occur without citations (Oratio, Secreta, Prefatio, Postcommunio, and
# occasionally Graduale/Offertorium/Communio) resolves under one of the two.
SECTION_EN = {
    "Introitus": "Introit",
    "Oratio": "Collect",
    "Lectio": "Epistle",
    "Graduale": "Gradual",
    "GradualeP": "Alleluia",
    "Tractus": "Tract",
    "Sequentia": "Sequence",
    "Evangelium": "Gospel",
    "Offertorium": "Offertory",
    "Secreta": "Secret",
    "Prefatio": "Preface",
    "Communio": "Communion",
    "Postcommunio": "Postcommunion",
}

SECTIONS = {"es": SECTION_ES, "en": SECTION_EN}
_COMMEMORATIO = {"es": "Conmemoración", "en": "Commemoration"}


def _section_display(name: str, lang: str = "es") -> str:
    table = SECTIONS[lang]
    if name in table:
        return table[name]
    m = re.match(r"^Commemoratio\s+(.*)$", name)
    if m:
        inner = table.get(m.group(1), m.group(1))
        return f"{_COMMEMORATIO[lang]} ({inner})"
    return name


# Language-dependent chrome. `bible` is filled with Bible.name so the notes
# name the actual translation in use.
_STRINGS = {
    "es": {
        "subject": "Español",
        "colophon": (
            '<p class="meta">Propios de la Misa<br/>'
            "(Misal Romano de 1962)<br/>"
            "Lecturas: {bible_credit}<br/>"
            "Oraciones: Divinum Officium</p>\n"
        ),
        "bible_credit": "Biblia Platense (Mons. Straubinger)",
        "no_text": "[Texto no disponible en la {bible}: {detail}]",
        "some_missing": "[Sin texto en la {bible}: {detail}]",
        "alleluia": "Aleluya",
    },
    "en": {
        "subject": "English",
        "colophon": (
            '<p class="meta">Proper of the Mass<br/>'
            "(Roman Missal of 1962)<br/>"
            "Readings: {bible_credit}<br/>"
            "Prayers: Divinum Officium</p>\n"
        ),
        "bible_credit": "Douay-Rheims Bible (Challoner revision)",
        "no_text": "[No text in the {bible}: {detail}]",
        "some_missing": "[Verses without text in the {bible}: {detail}]",
        "alleluia": "Alleluia",
    },
}


_CSS = """\
body { font-family: serif; margin: 0.5em; line-height: 1.4; }
h1 { font-size: 1.4em; text-align: center; margin: 0.5em 0; }
h2 { font-size: 1.2em; margin: 1em 0 0.2em 0; }
h3 { font-size: 1em; font-style: italic; margin: 0.8em 0 0.2em 0; }
p.meta { text-align: center; font-style: italic; margin: 0.2em 0; }
p.passage { margin: 0.2em 0 0.6em 0; text-align: justify; }
p.alleluia { margin: 0.2em 0 0.6em 0; font-style: italic; }
sup.v { font-size: 0.7em; }
"""

_XHTML_HEAD = """\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>{title}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
"""


def _passage_html(bible: Bible, citation, lang: str = "es") -> str:
    """Verse text as one justified paragraph with superscript verse numbers."""
    s = _STRINGS[lang]
    try:
        rows, missing = bible.get_passage(citation)
    except MissingVerseError as e:
        # Loud but non-fatal: some citations (e.g. the Requiem introit from
        # 4 Esdras) reference apocrypha neither translation ever rendered.
        print(f"WARNING: {e}", file=sys.stderr)
        return (
            '<p class="passage"><em>'
            + escape(s["no_text"].format(bible=bible.name, detail=citation.source))
            + "</em></p>"
        )
    note = ""
    if missing:
        print(
            f"WARNING: citation {citation.source!r}: verses without text in "
            f"the {bible.name}: {', '.join(missing)}", file=sys.stderr,
        )
        note = (
            '<p class="passage"><em>'
            + escape(
                s["some_missing"].format(bible=bible.name, detail=", ".join(missing))
            )
            + "</em></p>"
        )
    multi_chapter = len({ch for ch, _, _ in rows}) > 1
    parts: list[str] = []
    for ch, v, text in rows:
        label = f"{ch},{v}" if multi_chapter else str(v)
        parts.append(f'<sup class="v">{label}</sup>&#160;{escape(text)}')
    return '<p class="passage">' + " ".join(parts) + "</p>" + note


def _alleluia_html(count: int, lang: str = "es") -> str:
    """'Aleluya, aleluya.' (count=2) / 'Aleluya.' (count=1); '' for count<=0.

    Matches the source's own capitalisation convention (e.g. 'Allelúia,
    allelúia.'): capitalised once, lower-case on every repeat.
    """
    if count <= 0:
        return ""
    word = _STRINGS[lang]["alleluia"]
    words = [word] + [word.lower()] * (count - 1)
    return f'<p class="alleluia">{escape(", ".join(words))}.</p>\n'


def build_epub(
    day: DayPropers,
    date: _dt.date,
    bible: Bible,
    out_path: str,
    lang: str = "es",
) -> str:
    """Write the EPUB for *day* to *out_path* and return the path."""
    s = _STRINGS[lang]
    # Short title for Calibre's library/OPDS view — the in-book title page
    # below still shows the full Latin day name for readers.
    short = compact_name(day.day_name, day.rank, lang).upper().replace("-", " ")
    title = f"[{lang.upper()}] {short} ({date.isoformat()})"
    book_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mass-propers/{date.isoformat()}"))
    season = classify_season(day.day_name, day.rank)

    chapters: list[tuple[str, str, str]] = []  # (file name, toc label, xhtml)

    # Title page
    tp = _XHTML_HEAD.format(title=escape(title))
    tp += f"<h1>{escape(day.day_name)}</h1>\n"
    if day.rank:
        tp += f'<p class="meta">{escape(day.rank)}</p>\n'
    tp += f'<p class="meta">{date.isoformat()}</p>\n'
    tp += s["colophon"].format(bible_credit=s["bible_credit"])
    tp += "</body>\n</html>\n"
    chapters.append(("title.xhtml", escape(title), tp))

    for i, section in enumerate(day.sections, 1):
        disp = _section_display(section.name, lang)
        fname = f"s{i:02d}.xhtml"
        if section.citations:
            page_title = f"{disp}: {section.citations[0].display}"
        else:
            page_title = disp
        x = _XHTML_HEAD.format(title=escape(page_title))
        x += f"<h2>{escape(disp)}</h2>\n"
        x += _alleluia_html(section.leading_alleluia, lang)
        for cit in section.citations:
            x += f"<h3>{escape(cit.display)}</h3>\n"
            x += _passage_html(bible, cit, lang) + "\n"
            x += _alleluia_html(cit.alleluia_after, lang)
        if not section.citations and section.prayer_text:
            x += f'<p class="passage">{escape(section.prayer_text)}</p>\n'
        x += "</body>\n</html>\n"
        chapters.append((fname, escape(page_title), x))

    # --- OPF ---
    manifest_items, spine_items, navpoints = [], [], []
    for i, (fname, label, _) in enumerate(chapters):
        cid = f"c{i}"
        manifest_items.append(
            f'<item id="{cid}" href="{fname}" media-type="application/xhtml+xml"/>'
        )
        spine_items.append(f'<itemref idref="{cid}"/>')
        navpoints.append(
            f'<navPoint id="np{i}" playOrder="{i + 1}">'
            f"<navLabel><text>{label}</text></navLabel>"
            f'<content src="{fname}"/></navPoint>'
        )
    manifest_items.append('<item id="css" href="style.css" media-type="text/css"/>')
    manifest_items.append(
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
    )

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{escape(title)}</dc:title>
    <dc:language>{lang}</dc:language>
    <dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>
    <dc:creator opf:role="edt">mass-propers</dc:creator>
    <dc:date>{date.isoformat()}</dc:date>
    <dc:subject>{s["subject"]}</dc:subject>
    <dc:subject>{escape(season)}</dc:subject>
  </metadata>
  <manifest>
    {chr(10).join('    ' + m for m in manifest_items).strip()}
  </manifest>
  <spine toc="ncx">
    {chr(10).join('    ' + s for s in spine_items).strip()}
  </spine>
</package>
"""

    ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_id}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{escape(title)}</text></docTitle>
  <navMap>
    {chr(10).join('    ' + n for n in navpoints).strip()}
  </navMap>
</ncx>
"""

    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w") as z:
        z.writestr(
            zipfile.ZipInfo("mimetype"), "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        z.writestr("META-INF/container.xml", container, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", _CSS, zipfile.ZIP_DEFLATED)
        for fname, _, content in chapters:
            z.writestr(f"OEBPS/{fname}", content, zipfile.ZIP_DEFLATED)
    return out_path
