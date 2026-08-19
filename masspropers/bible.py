"""Look up verse text in a scrollmapper bible_databases CSV.

Two editions are wired up, one per output language:

* ``es`` — **SpaPlatense**, the Biblia Platense (Mons. Juan Straubinger), the
  only Spanish translation in scrollmapper/bible_databases with the full
  Catholic canon.
* ``en`` — **DRC**, the Douay-Rheims Challoner revision: the traditional
  English Catholic Bible, translated from the Vulgate, hence the closest
  English match to DivinumOfficium's Vulgate citations. (CPDV is the only
  other full-canon English translation in the repo, but it is a modern
  translation.)

Empirically verified properties relied on here (checked for *both* CSVs
independently — see the per-edition notes on VERSE_REMAP_* below):

* Book names in the CSVs are English ('Psalms', 'I Maccabees', 'Sirach', ...)
  in every language file, so ``Citation.book_key`` is shared.
* Both files share scrollmapper's single (book, chapter, verse) skeleton —
  each has exactly 37255 rows and the identical 78-book set, including the
  deuterocanon (Baruch, Judith, Tobit, Sirach, Wisdom, 1-2 Maccabees, the
  Vulgate Esther 11-16 and Daniel 3:24-90/13/14). Where a translation merges
  two verses, scrollmapper leaves the surplus row blank rather than
  renumbering, so the numbering never drifts from the citation scheme.
* Both use the Vulgate/Septuagint Psalm numbering, not the Hebrew/KJV one
  (Ps 17 == Vulgate 'Diligam te' == DRC 'I will love thee, O Lord' ==
  Platense 'Te amo, Yahvé'; Ps 22 == 'Dominus regit me' == DRC 'The Lord
  ruleth me'), and the Hebrew title counts as verse 1, exactly matching
  DivinumOfficium's citations — no renumbering needed for either.
"""

from __future__ import annotations

import csv
import os

from .citations import Citation

_HERE = os.path.dirname(os.path.abspath(__file__))
_CSV_DIR = os.path.join(os.path.dirname(_HERE), "bible_databases", "formats", "csv")
DEFAULT_CSV = os.path.join(_CSV_DIR, "SpaPlatense.csv")
DRC_CSV = os.path.join(_CSV_DIR, "DRC.csv")
# The Clementine Vulgate itself — same scrollmapper skeleton as the other two
# (37255 rows, identical 78-book set incl. deuterocanon), confirmed to already
# carry real text at both SpaPlatense's and DRC's respective merge points
# (Ps 10:8, Ps 150:6), so no VERSE_REMAP is needed for it. Used for the
# optional --latin CLI flag (cli.py), which prints this text ahead of the
# translation instead of DivinumOfficium's own citation-only Latin page.
VULGATE_CSV = os.path.join(_CSV_DIR, "Vulgate.csv")


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

# DRC's merge points are *not* SpaPlatense's — checked, not assumed. DRC has
# real, correctly-placed text at Ps 10:8 ('For the Lord is just, and hath
# loved justice: his countenance hath beheld righteousness'), so the Spanish
# remap above must not be applied to it. Sweeping the whole 1962 corpus of
# citations (every '!' line under divinum-officium/.../missa/Latin) against
# DRC turns up exactly two verses DRC leaves blank where SpaPlatense does not:
#
#   * Ps 150:6 'Omnis spiritus laudet Dominum' — DRC merges it into 150:5
#     ('...praise him on cymbals of joy: let every spirit praise the Lord.
#     Alleluia.'), so it is remapped below; since 150 is only ever cited as a
#     whole chapter, the remap target is already in the passage and the verse
#     is silently dropped rather than duplicated.
#   * 3 Reg (I Kings) 17:19 'Da mihi filium tuum' — genuinely absent from the
#     DRC data (17:18 and 17:20 both align with the Vulgate, so it is a
#     dropped verse, not a merge). Cited by '3 Reg 17:17-24'. No remap is
#     possible; it surfaces as the usual in-book "no text" note.
VERSE_REMAP_DRC: dict[tuple[str, int, int], tuple[str, int, int]] = {
    ("Psalms", 150, 6): ("Psalms", 150, 5),
}

# lang -> (CSV path, verse remap, translation name used in on-page notes).
# "la" isn't an *output* language (cli.py's --lang only offers es/en — there's
# no Spanish/English chrome string for it) — it's only ever loaded directly
# via Bible.for_lang("la") for the --latin flag's side-by-side Vulgate text.
EDITIONS: dict[str, tuple[str, dict, str]] = {
    "es": (DEFAULT_CSV, VERSE_REMAP, "Biblia Platense"),
    "en": (DRC_CSV, VERSE_REMAP_DRC, "Douay-Rheims Bible"),
    "la": (VULGATE_CSV, {}, "Vulgata"),
}


class Bible:
    def __init__(
        self,
        csv_path: str = DEFAULT_CSV,
        remap: dict[tuple[str, int, int], tuple[str, int, int]] | None = None,
        name: str = "Biblia Platense",
    ):
        self.csv_path = csv_path
        self.remap = VERSE_REMAP if remap is None else remap
        self.name = name
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

    @classmethod
    def for_lang(cls, lang: str) -> "Bible":
        """Load the translation configured for output language *lang*."""
        try:
            csv_path, remap, name = EDITIONS[lang]
        except KeyError:
            raise ValueError(f"no Bible edition configured for lang {lang!r}") from None
        return cls(csv_path, remap, name)

    def get_passage(
        self, cit: Citation
    ) -> tuple[list[tuple[int, int, str]], list[str]]:
        """Return ([(chapter, verse, text), ...], missing_refs) in citation order.

        Individual verses absent from the translation (or present only as the
        blank placeholder rows scrollmapper uses for untranslated apocrypha
        and for verse splits a translator merged — e.g. Acts 8:37 and Ps 10:8
        in SpaPlatense, 3 Reg 17:19 in DRC) are reported in *missing_refs*
        rather than aborting the passage. Raises MissingVerseError only when
        the citation yields no text at all.
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
                if not (text and text.strip()) and key in self.remap:
                    rb, rc, rv = self.remap[key]
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
