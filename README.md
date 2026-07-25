# Mass Propers → Spanish Scripture EPUB

Given a Gregorian date, this tool resolves the liturgical day of the **1962
Missale Romanum** (Tridentine / Extraordinary Form), collects **every Scripture
citation** used in that day's Mass Propers (readings *and* chant antiphons),
fetches the corresponding **Spanish Bible text** (Biblia Platense /
Straubinger), and assembles a minimal **EPUB** suitable for the Xteink X3
e-reader (CrossPoint firmware).

## Usage

```bash
# Generate the EPUB for a date (written to output/<date>_<day-slug>.epub)
python3 -m masspropers.cli 2026-06-07

# Choose the output path
python3 -m masspropers.cli 2026-06-07 -o /tmp/propers.epub

# Just resolve the day and print its citations (no EPUB)
python3 -m masspropers.cli 2026-06-07 --list

# Query the public divinumofficium.com instead of the local Perl CGI
python3 -m masspropers.cli 2026-06-07 --source remote
```

Requirements: Python ≥ 3.10 (stdlib only), Perl 5 with `CGI.pm`
(`apt install libcgi-pm-perl`) for the default local backend, and the two data
repos checked out beside this file (as in this workspace):

* `divinum-officium/` — github.com/DivinumOfficium/divinum-officium
* `bible_databases/`  — github.com/scrollmapper/bible_databases

Validation tooling (optional): `apt install epubcheck`,
`pip install ebooklib`.

### Upload to the device (manual step, run from a network with the X3 reachable)

```bash
curl -X POST -F "file=@output/2026-06-07_dominica-ii-post-pentecosten.epub" \
  "http://crosspoint.local/upload?path=/Books"
```

Not run here: this sandbox has no network route to the device.

## How it works

### Stage 1 — Resolve the day (DivinumOfficium)

The Tridentine calendar (movable feasts, precedence, octaves, commemorations)
is **not reimplemented**; the tool runs DivinumOfficium's own engine.

* **`local` backend (default):** executes the checked-out Perl CGI
  (`divinum-officium/web/cgi-bin/missa/missa.pl`) as a subprocess with
  `QUERY_STRING`/`REQUEST_METHOD` set, i.e. a CGI request without a web
  server. No Docker needed.
* **`remote` backend:** the same query against
  `https://divinumofficium.com/cgi-bin/missa/missa.pl`. **Caveat:** as of
  2026-07 the site sits behind a Cloudflare JavaScript challenge that blocks
  non-browser clients, so this backend fails from this sandbox (the tool
  detects the challenge page and says so). It is kept because the query
  string is identical and works wherever the site is directly reachable.

Responses are cached in `cache/` keyed by `(date, version, backend)`; a date is
never fetched twice. Remote fetches are additionally rate-limited (2 s).

#### Query-string quirks worked out empirically

```
missa.pl?date=MM-DD-YYYY&version=Rubrics+1960+-+1960&lang1=Latin&lang2=Latin&command=pray&content=1&Propers=1
```

* `version=Rubrics 1960 - 1960` is DivinumOfficium's name for the 1962-Missal
  rubric set (their default).
* `command=pray&content=1` emits the bare content and exits without the
  surrounding page chrome.
* **`Propers=1`** (undocumented, found in `ordo.pl:getordinarium`) swaps the
  full Order of Mass for `Latin/Ordo/Propers.txt`, so the output contains only
  Introitus … Postcommunio. This is the key to a clean page.
* Setting **`lang1 == lang2`** triggers missa.pl's `$only` mode: a single
  column instead of the bilingual table.
* The "Rubrics 1960" renderer applies classical-Latin **J→I normalisation**,
  so source citations like `1 John`/`Joann`/`Jer` arrive as `1 Iohn`/`Ioann`/
  `Ier`. The book-name normaliser folds J and I together.
* The day-name header is `<P ALIGN="CENTER"><FONT COLOR="...">Name ~ Rank`,
  where the FONT colour is the liturgical colour and is **absent entirely on
  white-vestment days** (`<FONT >`), and the `<P>` may contain further lines
  (e.g. All Souls' *Scriptura* cross-reference).

#### Citation extraction

In the rendered page, each proper part is a `<TD>` block headed by
`<FONT SIZE='+1' COLOR="red"><B><I>SectionName</I></B></FONT>`, and every `!`
citation line of the source files renders as
`<FONT COLOR="red"><I>Ps 17:19-20</I></FONT>`. The same red-italic markup is
also used for non-citation labels (`℣.`, `de sanctissima Trinitate`,
`Antiphona 2`, `Commemoratio …`), so each candidate is classified:

* parses as a citation with a known book → kept (a section keeps **all** its
  citations, e.g. the Gradual's Alleluia verse);
* citation-shaped **with verse punctuation** (`:`/`,`/`-` between digits) but
  an unknown book → **hard error** naming the abbreviation, so `BOOK_MAP` can
  be extended;
* anything else → label, skipped.

Reference grammar handled (all forms occur in the corpus):
`Ps 17:19-20` · `Rom 8:18,22-23` (non-contiguous list) ·
`Isa 54:17; 55:1-11` (multi-chapter) · `Act 1, 15-26` (European
chapter-comma-verses, disambiguated by the absence of a colon) ·
`Ps. 116` (whole chapter) · `Ps:79:2-3` (stray colon) · `1. Tim 4:8-16.`
(stray dots) · trailing `a`/`b` verse-letters.

### Stage 2 — Spanish text (scrollmapper `SpaPlatense`)

`bible_databases/formats/csv/SpaPlatense.csv` — the Biblia Platense
(Mons. Juan Straubinger), the only Spanish translation in the repo with the
full **Catholic canon**. Properties verified empirically and relied upon:

* **Book names are English** (`Psalms`, `I Maccabees`, `Sirach`, …) although
  the text is Spanish.
* **Psalms use Vulgate/Septuagint numbering** (CSV Ps 17 = *Diligam te* =
  Vulgate Ps 17), and the psalm title counts as verse 1 — so DivinumOfficium's
  Vulgate citations map **1:1, no renumbering**. (Verified: Ps 17:19-20 →
  "…me trajo a la anchura; me salvó porque me ama" = *edúxit me in
  latitúdinem: salvum me fecit, quóniam vóluit me*.)
* Deuterocanonical sections are present (Daniel 3 runs to v. 100 — the Ember
  Saturday canticle Dan 3:47-59 resolves; Esther has the Vulgate chapters
  11–16).
* The apocryphal **4 Esdras** (scrollmapper `II Esdras`) has only *empty
  placeholder rows*: the Requiem introit `4 Esdr 2:34-35` (All Souls, Requiem
  Masses) cannot be filled. The tool prints a warning and puts a visible
  *[Texto no disponible en la Biblia Platense]* note in the EPUB instead.

### The book-name mapping table and how to extend it

`masspropers/citations.py: BOOK_MAP` maps a *normalised* abbreviation to
`(CSV book key, Spanish display name)`. Normalisation: lowercase, strip dots,
`j→i`, `ë/æ/é` folded, roman ordinals (`I`–`IV`) → arabic — so one entry
covers `Joann`/`Ioann`/`Joann.`, and `1 John`/`1 Iohn`/`I John` etc.

Notable Vulgate→CSV mappings (the traps):

| Citation abbrev. | CSV book | Spanish |
|---|---|---|
| `Eccli`, `Sir`, **and** `Eccles`/`Eccle`/`Eccl` | Sirach | Eclesiástico |
| `Sap` | Wisdom | Sabiduría |
| `Cant` | Song of Solomon | Cantar de los Cantares |
| `Thren`, `Lam` | Lamentations | Lamentaciones |
| `1/2 Reg` | I/II Samuel | 1/2 Samuel |
| `3/4 Reg` | I/II Kings | 1/2 Reyes |
| `1/2 Par` | I/II Chronicles | 1/2 Crónicas |
| `1 Esdr`/`Esdr`, `2 Esdr`/`Neh` | Ezra, Nehemiah | Esdras, Nehemías |
| `4 Esdr` | II Esdras (apocryphal; empty in Platense) | 4 Esdras |
| `Osee`/`Hos` | Hosea | Oseas |
| `Jud` | Jude (confirmed from Sancti/06-20: `Jud 1:17-21`) | Judas |
| `Apoc`/`Apo`/`Ap` | Revelation of John | Apocalipsis |
| `Act`/`Acts`/`Acta` | Acts | Hechos de los Apóstoles |
| `Ia` | James — the renderer mangles source `Jac` into `Ia` | Santiago |
| `Tractus` | Psalms — Palm Sunday's `!Tractus 21:2-9,…` leaves the book implicit | Salmos |

Every `Eccl*` citation in the corpus is really Ecclesiasticus (Sirach) — each
was verified against the quoted Latin (chapters 24/44/49/50 don't exist in
Qoheleth; `Eccle 11:13` = *Oculus Dei respexit illum* = Sir 11:13). Qoheleth
is not cited in the 1962 Mass propers.

### Upstream data corrections (`citations.py: CORRECTIONS`)

A sweep of **every day of 2026** surfaced seven citation typos in
DivinumOfficium's data files. Each was verified against the Latin text printed
under the citation, and each original reference is *impossible* (verse beyond
the chapter's end), so the exact-string rewrite can never misfire:

| DO citation | Actually | Evidence (Latin incipit) |
|---|---|---|
| `Ps 7:26-27` | Ps 117:26-27 | *Benedictus qui venit in nomine Domini* |
| `Ps 31:20` | Prov 31:20 | *Manum suam aperuit inopi* |
| `Ps 39:17-19` | Eccli 39:17-19 | *Quasi rosa plantata* |
| `Ps 14:9` | John 14:9 | *Tanto tempore vobiscum sum* |
| `Ps 14:26` | John 14:26 | *Spiritus Sanctus docebit vos* |
| `Dan 5:58` | Dan 3:58 | *Benedicite omnes Angeli Domini Dominum* |
| `Dan 3:31; 31:29; 31:35` | Dan 3:31; 3:29; 3:35 | *Omnia quæ fecisti* |

One verse-numbering remap (`bible.py: VERSE_REMAP`): Vulgate **Ps 10:8**'s
text sits in the CSV's Ps 10:7 row (Straubinger follows Hebrew verse
divisions there; scrollmapper pads with a blank 10:8 row).

To extend: on an unmapped abbreviation the tool aborts with
`unrecognised book abbreviation 'X' (normalised: 'x') … add it to
masspropers/citations.py BOOK_MAP`. Add one `_add("CSV key", "Spanish name",
"Abbrev", …)` line (any J/I/dot/ordinal spelling; it is normalised on
registration).

### Stage 3 — EPUB

Minimal EPUB 2 built with the stdlib `zipfile` (no dependencies, no fonts, no
images, ~15-line CSS): a title page (day name, rank, date) plus one chapter
per proper part in liturgical order, each headed by the Spanish section name
(Introito, Epístola, Gradual, Evangelio, Ofertorio, Comunión, …) and the
human-readable Spanish citation (e.g. *Epístola: 1 Juan 3:13-18*), followed by
the verse text with superscript verse numbers (chapter,verse labels when a
citation spans chapters).

Sections whose text is not Scripture (Collect, Secret, Postcommunion, Preface
— they carry no `!` citations) are omitted: the book is the *Scripture* of the
day's propers, per the task definition.

### Stage 4 — Validation

* `epubcheck` — all 16 generated test EPUBs pass with **0 errors, 0 warnings**
  (EPUB 2.0.1 rules).
* `ebooklib` round-trip — titles, language and chapter structure parse back
  correctly.

## Acceptance test (verified end-to-end)

`python3 -m masspropers.cli 2026-06-07` resolves to **Dominica II Post
Pentecosten** and extracts exactly the citations of
`missa/Latin/Tempora/Pent02-0.txt`:

| Section | Citation |
|---|---|
| Introitus | Ps 17:19-20 · Ps 17:2-3 |
| Lectio | 1 John 3:13-18 |
| Graduale | Ps 119:1-2 · Ps 7:2 (Alleluia verse) |
| Evangelium | Luc 14:16-24 |
| Offertorium | Ps 6:5 |
| Communio | Ps 12:6 |

Also exercised: Epiphany, Ash Wednesday, Good Friday (Passion), Holy Saturday
(prophecies), Easter, Pentecost, SS. Peter & Paul, Assumption (`Judith 13,
22-25; 15:10` European style), September Ember Saturday (five lessons +
Dan 3:47-59), All Souls (4 Esdr warning path), Gaudete Sunday, Christmas
midnight Mass — plus a full sweep of every day of 2026.

## Assumptions & known limitations

* **The DivinumOfficium engine is the source of truth** for the calendar; the
  tool renders whatever Mass `missa.pl` serves for the date. On days with
  several Masses (Christmas, All Souls) that is the *first* Mass (in nocte /
  ad primam Missam); other Masses of the day are not fetched.
* The Propers-only Ordo interleaves Ember-day lessons inside the `Oratio`
  block, so those citations are attributed to that section heading; nothing
  is lost, only the label is coarse.
* Whole-chapter citations (`Ps. 116`) expand to every verse of the chapter.
* Red-italic labels that are a word plus a *bare* number (`Antiphona 2`) are
  treated as labels, not citations; genuine whole-chapter citations survive
  because their book abbreviation is in `BOOK_MAP`.
* Two verified translation gaps remain after the full-2026 sweep, both handled
  with a stderr warning and a visible note in the EPUB: **4 Esdras 2:34-35**
  (Requiem introit/gradual/communion — Straubinger never translated the
  apocryphal 4 Esdras) and **Acts 8:37** (a verse Straubinger, like most
  modern editions, omits on text-critical grounds; the rest of Acts 8:26-40 is
  included with a note).
* Dates in past years work (checked: 1962-06-17 → Dominica Sanctissimæ
  Trinitatis).
* The EPUB uses the Latin day name as its title (stable, rank-accurate);
  section headings are Spanish.
* DivinumOfficium's own Spanish propers (`web/www/missa/Espanol/…`) are a
  liturgical paraphrase and are deliberately **not** used as Bible text.

## Layout

```
masspropers/
  fetch.py       # Stage 1a: local Perl-CGI / remote HTTP fetch + cache
  parse.py       # Stage 1b: HTML -> sections + citations
  citations.py   # citation grammar + BOOK_MAP (extend here)
  bible.py       # Stage 2: SpaPlatense lookup
  epub.py        # Stage 3: EPUB 2 assembly
  cli.py         # entry point
cache/           # fetched pages (never re-fetched)
output/          # generated EPUBs
```
