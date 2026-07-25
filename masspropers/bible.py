"""Look up Spanish verse text in the scrollmapper SpaPlatense CSV.

SpaPlatense is the Biblia Platense (Mons. Juan Straubinger), the only Spanish
translation in scrollmapper/bible_databases with the full Catholic canon.
Empirically verified properties relied on here:

* Book names in the CSV are English ('Psalms', 'I Maccabees', 'Sirach', ...).
* Psalms use the Vulgate/Septuagint numbering (Ps 17 == 'Te amo, Yahvé...'
  == Vulgate 'Diligam te'), and the Hebrew title counts as verse 1, exactly
  matching DivinumOfficium's Vulgate citations — no renumbering needed.
* Deuterocanonical sections are present (Daniel 3 runs to v.100, Esther has
  the Vulgate chapters 11-16).
"""

from __future__ import annotations

import csv
import os

from .citations import Citation

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(
    os.path.dirname(_HERE), "bible_databases", "formats", "csv", "SpaPlatense.csv"
)


class MissingVerseError(KeyError):
    """Raised when a cited verse does not exist in the translation."""


# Straubinger occasionally follows the Hebrew verse divisions inside the
# Vulgate chapter numbering; scrollmapper pads the difference with blank rows.
# Where a Vulgate-cited verse's text demonstrably lives in a neighbouring row,
# remap it (verified against the Latin: Ps 10:8 'iustus Dominus, et iustitiam
# dilexit; aequitatem vidit vultus eius' == Platense 10:7 'Porque Yahvé es
# justo y ama la justicia; los rectos verán su rostro').
VERSE_REMAP: dict[tuple[str, int, int], tuple[str, int, int]] = {
    ("Psalms", 10, 8): ("Psalms", 10, 7),
}


class Bible:
    def __init__(self, csv_path: str = DEFAULT_CSV):
        self.csv_path = csv_path
        # (book, chapter, verse) -> text ; (book, chapter) -> max verse
        self._verses: dict[tuple[str, int, int], str] = {}
        self._chapter_max: dict[tuple[str, int], int] = {}
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                book = row["Book"]
                ch, v = int(row["Chapter"]), int(row["Verse"])
                self._verses[(book, ch, v)] = row["Text"]
                key = (book, ch)
                if v > self._chapter_max.get(key, 0):
                    self._chapter_max[key] = v

    def get_passage(
        self, cit: Citation
    ) -> tuple[list[tuple[int, int, str]], list[str]]:
        """Return ([(chapter, verse, text), ...], missing_refs) in citation order.

        Individual verses absent from the translation (or present only as the
        blank placeholder rows SpaPlatense uses for untranslated apocrypha and
        for verse splits Straubinger merged, e.g. Acts 8:37, Ps 10:8) are
        reported in *missing_refs* rather than aborting the passage. Raises
        MissingVerseError only when the citation yields no text at all.
        """
        out: list[tuple[int, int, str]] = []
        missing: list[str] = []
        for chapter, verses in cit.refs:
            if verses is None:  # whole chapter
                maxv = self._chapter_max.get((cit.book_key, chapter))
                if not maxv:
                    missing.append(f"{cit.book_key} {chapter} (whole chapter)")
                    continue
                verses = list(range(1, maxv + 1))
            for v in verses:
                key = (cit.book_key, chapter, v)
                text = self._verses.get(key)
                if not (text and text.strip()) and key in VERSE_REMAP:
                    rb, rc, rv = VERSE_REMAP[key]
                    text = self._verses.get((rb, rc, rv))
                    # skip if the remap target is already part of the passage
                    if any(r[0] == rc and r[1] == rv for r in out):
                        continue
                    v = rv
                if text is None or not text.strip():
                    missing.append(f"{cit.book_key} {chapter}:{v}")
                else:
                    out.append((chapter, v, text))
        if not out:
            raise MissingVerseError(
                f"no text for citation {cit.source!r}: "
                f"{', '.join(missing)} not in {os.path.basename(self.csv_path)}"
            )
        return out, missing
