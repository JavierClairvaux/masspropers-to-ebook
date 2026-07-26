"""Parse DivinumOfficium scripture citations and map book names.

DivinumOfficium citation strings are not written with one consistent
abbreviation scheme; the corpus mixes Vulgate Latin abbreviations (``Eccli``,
``Sap``, ``3 Reg``, ``Thren``, ``Apoc``), English ones (``1 John``, ``Acts``),
and spelling variants (``Is``/``Isa``, ``Ex``/``Exod``/``Exodi``). On top of
that, the "Rubrics 1960 - 1960" renderer applies classical-Latin J->I
normalisation to the text, so ``Joann`` arrives as ``Ioann`` and ``1 John`` as
``1 Iohn``. The map below is keyed by a *normalised* form (lowercase, j->i,
dots stripped, roman numerals -> arabic) so one entry covers several surface
spellings.

Reference-list grammar (all seen in the corpus):

  Ps 17:19-20            chapter:verse-range
  Rom 8:18,22-23         comma-separated verse/range list (non-contiguous)
  Isa 54:17; 55:1-11     semicolon-separated multi-chapter reference
  Act 1, 15-26           European style: chapter COMMA verses (no colon)
  Ps:79:2-3              stray colon between book and chapter
  1. Tim 4:8-16.         stray dots

Values are (scrollmapper CSV book key, Spanish display name). The CSV book key
doubles as the *English* display name — scrollmapper names books in English in
every language file — so no parallel English table is needed; ``Citation.lang``
just selects which of the two the ``display`` property renders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class UnknownBookError(KeyError):
    """Raised when a citation's book abbreviation is not in BOOK_MAP."""


class CitationSyntaxError(ValueError):
    """Raised when a string looks like a citation but cannot be parsed."""


# Normalised abbreviation -> (CSV book key, Spanish name).
BOOK_MAP: dict[str, tuple[str, str]] = {}


def _add(csv_key: str, spanish: str, *abbrevs: str) -> None:
    for a in abbrevs:
        BOOK_MAP[_norm_book(a)] = (csv_key, spanish)


def _norm_book(s: str) -> str:
    """Normalise a book abbreviation for lookup."""
    s = s.strip().lower()
    s = s.replace(".", " ")
    s = s.replace("j", "i")
    s = s.replace("ë", "e").replace("æ", "ae").replace("é", "e")
    # roman numeral ordinal prefixes -> arabic
    s = re.sub(r"^(i{1,3}|iv)\b", lambda m: str({"i": 1, "ii": 2, "iii": 3, "iv": 4}[m.group(1)]), s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- Old Testament ---------------------------------------------------------
_add("Genesis", "Génesis", "Gen", "Genesis")
_add("Exodus", "Éxodo", "Ex", "Exod", "Exodi", "Exodus")
_add("Leviticus", "Levítico", "Lev", "Levit")
_add("Numbers", "Números", "Num")
_add("Deuteronomy", "Deuteronomio", "Deut")
_add("Joshua", "Josué", "Jos", "Josue")
_add("Judges", "Jueces", "Judic")
_add("Ruth", "Rut", "Ruth")
_add("I Samuel", "1 Samuel", "1 Reg", "1 Sam")
_add("II Samuel", "2 Samuel", "2 Reg", "2 Sam")
_add("I Kings", "1 Reyes", "3 Reg")
_add("II Kings", "2 Reyes", "4 Reg")
_add("I Chronicles", "1 Crónicas", "1 Par")
_add("II Chronicles", "2 Crónicas", "2 Par")
_add("Ezra", "Esdras", "Esdr", "1 Esdr")
_add("Nehemiah", "Nehemías", "Neh", "2 Esdr")
# Vulgate-appendix apocrypha: 4 Esdras (= scrollmapper 'II Esdras') supplies
# the Requiem introit 'Requiem aeternam' (4 Esdr 2:34-35). SpaPlatense carries
# only empty placeholder rows for it — see MissingVerseError handling.
_add("I Esdras", "3 Esdras", "3 Esdr")
_add("II Esdras", "4 Esdras", "4 Esdr")
_add("Tobit", "Tobías", "Tob")
_add("Judith", "Judit", "Judith", "Jdt")
_add("Esther", "Ester", "Esth")
_add("Job", "Job", "Job")
_add("Psalms", "Salmos", "Ps", "Psalm", "Psalmus", "Psalmi")
_add("Proverbs", "Proverbios", "Prov")
_add("Ecclesiastes", "Eclesiastés", "Ecclesiastes")
_add("Song of Solomon", "Cantar de los Cantares", "Cant")
_add("Wisdom", "Sabiduría", "Sap")
# Every Eccl/Eccle/Eccles citation in the missal corpus is actually
# Ecclesiasticus (Sirach), verified against the quoted text (e.g. 'Eccle
# 11:13' = 'Oculus Dei respexit illum' = Sir 11:13; 'Eccles. 49:3-4', ch. 49
# cannot be Qoheleth). Qoheleth is not cited in the 1962 Mass propers.
_add("Sirach", "Eclesiástico", "Eccli", "Sir", "Eccles", "Eccle", "Eccl")
_add("Isaiah", "Isaías", "Is", "Isa", "Isai")
_add("Jeremiah", "Jeremías", "Jer", "Jerem")
_add("Lamentations", "Lamentaciones", "Thren", "Lam")
_add("Baruch", "Baruc", "Bar", "Baruch")
_add("Ezekiel", "Ezequiel", "Ezech", "Ezek")
_add("Daniel", "Daniel", "Dan")
_add("Hosea", "Oseas", "Osee", "Hos")
_add("Joel", "Joel", "Joel", "Joël")
_add("Amos", "Amós", "Amos")
_add("Obadiah", "Abdías", "Abd")
_add("Jonah", "Jonás", "Jon", "Jonæ", "Jonae")
_add("Micah", "Miqueas", "Mich")
_add("Nahum", "Nahúm", "Nah", "Nahum")
_add("Habakkuk", "Habacuc", "Hab", "Habac")
_add("Zephaniah", "Sofonías", "Soph")
_add("Haggai", "Ageo", "Agg")
_add("Zechariah", "Zacarías", "Zach")
_add("Malachi", "Malaquías", "Mal", "Malach")
_add("I Maccabees", "1 Macabeos", "1 Mach", "1 Macc")
_add("II Maccabees", "2 Macabeos", "2 Mach", "2 Macc")

# --- New Testament ---------------------------------------------------------
_add("Matthew", "Mateo", "Matt", "Mt", "Matth")
_add("Mark", "Marcos", "Marc", "Mc")
_add("Luke", "Lucas", "Luc", "Lc")
_add("John", "Juan", "Joann", "Joannes", "Joh", "John", "Jo")
_add("Acts", "Hechos de los Apóstoles", "Act", "Acts", "Acta")
_add("Romans", "Romanos", "Rom")
_add("I Corinthians", "1 Corintios", "1 Cor")
_add("II Corinthians", "2 Corintios", "2 Cor")
_add("Galatians", "Gálatas", "Gal")
_add("Ephesians", "Efesios", "Eph", "Ephes")
_add("Philippians", "Filipenses", "Phil", "Philipp", "Philip")
_add("Colossians", "Colosenses", "Col", "Coloss")
_add("I Thessalonians", "1 Tesalonicenses", "1 Thess")
_add("II Thessalonians", "2 Tesalonicenses", "2 Thess")
_add("I Timothy", "1 Timoteo", "1 Tim")
_add("II Timothy", "2 Timoteo", "2 Tim")
_add("Titus", "Tito", "Tit")
_add("Philemon", "Filemón", "Philem", "Phlm")
_add("Hebrews", "Hebreos", "Hebr", "Heb")
# 'Ia' is what the 1960 renderer makes of source 'Jac' (James); verified from
# Commune text 'Beatus vir qui suffert tentationem' = Jas 1:12.
_add("James", "Santiago", "Jas", "Jac", "Jc", "Ia")
_add("I Peter", "1 Pedro", "1 Pet", "1 Petr", "1 Petri")
_add("II Peter", "2 Pedro", "2 Pet", "2 Petr", "2 Petri")
_add("I John", "1 Juan", "1 Joann", "1 Joannes", "1 Joannnes", "1 John", "1 Jo")
_add("II John", "2 Juan", "2 Joann", "2 Joannes", "2 John")
_add("III John", "3 Juan", "3 Joann", "3 Joannes", "3 John")
_add("Jude", "Judas", "Judæ", "Judae", "Jude", "Jud")
_add("Revelation of John", "Apocalipsis", "Apoc", "Apo", "Ap")

# Palm Sunday's tract is cited as '!Tractus 21:2-9, ...' with the book left
# implicit; the text ('Deus, Deus meus, respice in me') is Psalm 21. This is
# the only citation-with-references use of 'Tractus' in the corpus.
_add("Psalms", "Salmos", "Tractus")

# Verified typos in DivinumOfficium's data, keyed by the citation string as
# rendered (J->I applied). Each was confirmed against the Latin text printed
# under the citation, and each original reference is impossible (verse beyond
# the chapter's end), so the rewrite can never misfire on a valid citation.
CORRECTIONS: dict[str, str] = {
    # 'Benedictus qui venit in nomine Domini' = Ps 117:26-27 (Sat. in Albis)
    "Ps 7:26-27": "Ps 117:26-27",
    # 'Manum suam aperuit inopi' = Prov 31:20 (S. John Cantius)
    "Ps 31:20": "Prov 31:20",
    # 'Quasi rosa plantata' = Eccli 39:17-19 (S. Teresa of the Child Jesus;
    # the same file's GradualeP cites it correctly)
    "Ps 39:17-19": "Eccli 39:17-19",
    # 'Tanto tempore vobiscum sum' = John 14:9 (SS. Philip and James)
    "Ps 14:9": "Ioann 14:9",
    # 'Spiritus Sanctus docebit vos' = John 14:26 (Pentecost Tuesday)
    "Ps 14:26": "Ioann 14:26",
    # 'Benedicite omnes Angeli Domini Dominum' = Dan 3:58 (Michaelmas)
    "Dan 5:58": "Dan 3:58",
    # 'Omnia quae fecisti' introit = Dan 3:31, 29, 35 (19th Sun. after Pent.)
    "Dan 3:31; 31:29; 31:35": "Dan 3:31; 3:29; 3:35",
}


# English display names are derived from the scrollmapper CSV book key (which
# is already English), so no parallel 90-entry table is needed — only these
# few overrides, where the key is either misleading or not the traditional
# English-missal title:
#
#   * 'I Esdras'/'II Esdras' are scrollmapper's keys for the Vulgate-appendix
#     3 Esdras/4 Esdras; rendering the key verbatim would collide with the
#     canonical Ezra/Nehemiah, which the Douay tradition calls 1/2 Esdras.
#   * the rest are the Douay-Rheims' own book titles, matching the Latin
#     abbreviations DivinumOfficium cites them by (Eccli, Cant, Apoc).
BOOK_ENGLISH: dict[str, str] = {
    "I Esdras": "3 Esdras",
    "II Esdras": "4 Esdras",
    "Sirach": "Ecclesiasticus",
    "Song of Solomon": "Canticle of Canticles",
    "Revelation of John": "Apocalypse",
}

_ORDINAL_PREFIX_RE = re.compile(r"^(I{1,3})\s+")
_ROMAN_TO_ARABIC = {"I": "1", "II": "2", "III": "3"}


def _english_book(book_key: str) -> str:
    """'I John' -> '1 John'; 'Sirach' -> 'Ecclesiasticus'; 'Psalms' -> 'Psalms'."""
    if book_key in BOOK_ENGLISH:
        return BOOK_ENGLISH[book_key]
    return _ORDINAL_PREFIX_RE.sub(
        lambda m: _ROMAN_TO_ARABIC[m.group(1)] + " ", book_key
    )


@dataclass
class Citation:
    """A parsed scripture citation."""

    source: str                      # citation string as found in the page
    book_key: str                    # scrollmapper CSV book name
    book_spanish: str                # Spanish display name
    # Ordered (chapter, verses) pairs; verses == None means the whole chapter.
    refs: list[tuple[int, list[int] | None]] = field(default_factory=list)
    lang: str = "es"                 # which display name `display` renders

    @property
    def book_display(self) -> str:
        return self.book_spanish if self.lang == "es" else _english_book(self.book_key)

    @property
    def display(self) -> str:
        """Human-readable citation, e.g. '1 Juan 3:13-18' / '1 John 3:13-18'."""
        parts = []
        for ch, verses in self.refs:
            if verses is None:
                parts.append(str(ch))
            else:
                parts.append(f"{ch}:{_compress_verses(verses)}")
        return f"{self.book_display} {'; '.join(parts)}"


def _compress_verses(verses: list[int]) -> str:
    """[13,14,15,18] -> '13-15,18' (preserving citation order)."""
    out: list[str] = []
    i = 0
    while i < len(verses):
        j = i
        while j + 1 < len(verses) and verses[j + 1] == verses[j] + 1:
            j += 1
        out.append(str(verses[i]) if i == j else f"{verses[i]}-{verses[j]}")
        i = j + 1
    return ",".join(out)


# A string is *citation-shaped* if it starts with an optional ordinal + word(s)
# followed by digits (chapter/verse material). Labels like 'de sanctissima
# Trinitate' or '℣.' do not match.
_CITATION_RE = re.compile(
    r"""^\s*
        (?P<book>(?:[1-4]|I{1,3}V?|IV)?\.?\s*[A-Za-zÀ-ÿœÆæ]{2,}\.?)
        \s*[:\s]\s*
        (?P<refs>\d[\d\s:,;.\-–ab]*)
        \s*$""",
    re.VERBOSE,
)


def looks_like_citation(text: str) -> bool:
    return bool(_CITATION_RE.match(text.strip()))


def parse_citation(text: str, lang: str = "es") -> Citation:
    """Parse a citation string into a Citation, or raise.

    *lang* only selects the display language of the resulting Citation; the
    citation grammar and the CSV book key are language-independent.

    Raises UnknownBookError if the book abbreviation is not mapped (extend
    BOOK_MAP in that case) and CitationSyntaxError for unparseable references.
    """
    original = text.strip()
    text = CORRECTIONS.get(original, original)
    m = _CITATION_RE.match(text)
    if not m:
        raise CitationSyntaxError(f"not a recognisable citation: {text!r}")
    book_raw = m.group("book")
    norm = _norm_book(book_raw)
    if norm not in BOOK_MAP:
        raise UnknownBookError(
            f"unrecognised book abbreviation {book_raw!r} (normalised: {norm!r}) "
            f"in citation {text!r} — add it to masspropers/citations.py BOOK_MAP"
        )
    book_key, spanish = BOOK_MAP[norm]

    refs_str = m.group("refs").rstrip(" .")
    refs: list[tuple[int, list[int] | None]] = []
    last_chapter: int | None = None
    for chunk in refs_str.split(";"):
        chunk = chunk.strip().rstrip(".")
        if not chunk:
            continue
        ch, verses = _parse_chunk(chunk, last_chapter, text)
        last_chapter = ch
        refs.append((ch, verses))
    if not refs:
        raise CitationSyntaxError(f"no chapter/verse references in {text!r}")
    return Citation(source=original, book_key=book_key,
                    book_spanish=spanish, refs=refs, lang=lang)


def _parse_chunk(
    chunk: str, last_chapter: int | None, whole: str
) -> tuple[int, list[int] | None]:
    """Parse one semicolon-chunk into (chapter, verses|None)."""
    if ":" in chunk:
        ch_str, verse_str = chunk.split(":", 1)
        chapter = int(ch_str.strip())
        return chapter, _parse_verse_list(verse_str, whole)
    # European style 'CH, V-V' or 'CH, V, V-V': first number is the chapter.
    m = re.match(r"^(\d+)\s*,\s*(.+)$", chunk)
    if m:
        return int(m.group(1)), _parse_verse_list(m.group(2), whole)
    # Bare number: a whole chapter — unless a previous chunk set the chapter,
    # in which case e.g. 'Ps 96:1; 10' would mean more verses of chapter 96.
    m = re.match(r"^(\d+)\s*(?:-\s*(\d+))?$", chunk)
    if m and last_chapter is None and m.group(2) is None:
        return int(m.group(1)), None
    if last_chapter is not None:
        return last_chapter, _parse_verse_list(chunk, whole)
    raise CitationSyntaxError(f"cannot parse reference chunk {chunk!r} in {whole!r}")


def _parse_verse_list(s: str, whole: str) -> list[int]:
    """'18,22-23' -> [18, 22, 23]; tolerates letter suffixes ('24a')."""
    verses: list[int] = []
    for item in s.split(","):
        item = item.strip().rstrip(".").replace("–", "-")
        item = re.sub(r"(?<=\d)[ab]\b", "", item)  # 24a -> 24
        if not item:
            continue
        m = re.match(r"^(\d+)\s*(?:-\s*(\d+))?$", item)
        if not m:
            raise CitationSyntaxError(f"cannot parse verse item {item!r} in {whole!r}")
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if b < a:
            # e.g. 'Ps 44:3,2' style reversed lists come through split as
            # separate items; a genuinely reversed range is a data error.
            raise CitationSyntaxError(f"reversed range {item!r} in {whole!r}")
        verses.extend(range(a, b + 1))
    if not verses:
        raise CitationSyntaxError(f"empty verse list in {whole!r}")
    return verses
