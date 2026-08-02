"""CLI: Gregorian date -> vernacular-scripture EPUB of the day's Mass propers."""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys

from .bible import Bible
from .epub import SECTIONS, build_epub
from .fetch import VERSION_1962, fetch_propers_html
from .parse import compact_name, parse_propers_html, parse_propers_prose

# Output language -> DivinumOfficium language-folder name, i.e. the value
# missa.pl takes for lang1/lang2. Both folders exist under
# divinum-officium/web/www/missa/ and were verified to render.
DO_LANG = {"es": "Espanol", "en": "English"}


def _parse_date(s: str) -> _dt.date:
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%d.%m.%Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"unrecognised date {s!r} (use YYYY-MM-DD)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="mass-propers",
        description="Generate a vernacular-scripture EPUB of the 1962-Missal "
        "Mass propers for a Gregorian date.",
    )
    ap.add_argument("date", type=_parse_date, help="Gregorian date, YYYY-MM-DD")
    ap.add_argument(
        "--lang", choices=("es", "en"), default="es",
        help="output language: es = Spanish, Biblia Platense (default); "
        "en = English, Douay-Rheims Challoner",
    )
    ap.add_argument(
        "-o", "--output", default=None,
        help="output EPUB path (default: output/<lang>-<feast>.epub, e.g. "
        "output/es-ix-postpentecostes.epub)",
    )
    ap.add_argument(
        "--source", choices=("local", "remote"), default="local",
        help="local: run the checked-out DivinumOfficium Perl CGI (default); "
        "remote: query divinumofficium.com (may be blocked by Cloudflare)",
    )
    ap.add_argument("--no-cache", action="store_true", help="ignore the fetch cache")
    ap.add_argument(
        "--force", action="store_true",
        help="regenerate even if the target EPUB already exists (default: "
        "skip — filenames have no date in them, so the same liturgical day "
        "in a later year reuses the same filename)",
    )
    ap.add_argument(
        "--list", action="store_true", dest="list_only",
        help="only print the resolved day and its citations; no EPUB",
    )
    args = ap.parse_args(argv)

    body = fetch_propers_html(
        args.date, VERSION_1962, backend=args.source, use_cache=not args.no_cache
    )
    day = parse_propers_html(body, args.lang)
    print(f"{args.date.isoformat()}  ->  {day.day_name}"
          + (f" ({day.rank})" if day.rank else ""))
    for sec_name, cit in day.all_citations():
        print(f"  [{sec_name}] {cit.source}  ->  {cit.display}")

    out = args.output or (
        f"output/{args.lang}-{compact_name(day.day_name, day.rank, args.lang)}.epub"
    )
    if not args.list_only and not args.force and os.path.exists(out):
        print(f"{out} already exists; skipping (use --force to regenerate).")
        return 0

    # Non-scriptural propers (Oratio/Secreta/Postcommunio — original prayers,
    # not Scripture) have no citation to look up in the Bible CSV. For those
    # only, pull DivinumOfficium's own vernacular prose from a second fetch.
    prayer_sections = [s for s in day.sections if not s.citations]
    if prayer_sections:
        do_lang = DO_LANG[args.lang]
        vern_body = fetch_propers_html(
            args.date, VERSION_1962, backend=args.source,
            use_cache=not args.no_cache, lang=do_lang,
        )
        prose = parse_propers_prose(vern_body)
        section_names = SECTIONS[args.lang]
        for s in prayer_sections:
            # The rendered vernacular page translates the section heading
            # itself (Oratio -> Colecta on the Spanish page, -> Collect on the
            # English one), so look up by the same Latin->target name used for
            # display, not the Latin name directly. Fall back to the Latin
            # name for the sections DivinumOfficium leaves untranslated —
            # Secreta/Prefatio/Postcommunio on both pages, plus Offertorium
            # and Communio on the English one.
            vern_name = section_names.get(s.name, s.name)
            s.prayer_text = prose.get(vern_name) or prose.get(s.name)
            if not s.prayer_text:
                print(f"WARNING: no prose found for [{s.name}] in the "
                      f"{do_lang} DivinumOfficium page; section will be "
                      f"omitted.", file=sys.stderr)
        day.sections = [
            s for s in day.sections if s.citations or s.prayer_text
        ]

    if not day.sections:
        print("No scripture citations found for this day; no EPUB generated.",
              file=sys.stderr)
        return 1
    if args.list_only:
        return 0

    bible = Bible.for_lang(args.lang)
    build_epub(day, args.date, bible, out, args.lang)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
