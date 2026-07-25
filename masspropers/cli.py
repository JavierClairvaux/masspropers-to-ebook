"""CLI: Gregorian date -> Spanish-scripture EPUB of the day's Mass propers."""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys

from .bible import Bible
from .epub import build_epub
from .fetch import VERSION_1962, fetch_propers_html
from .parse import parse_propers_html


def _parse_date(s: str) -> _dt.date:
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%d.%m.%Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"unrecognised date {s!r} (use YYYY-MM-DD)")


def _slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[àáâã]", "a", s)
    s = re.sub(r"[èéê]", "e", s)
    s = re.sub(r"[ìíî]", "i", s)
    s = re.sub(r"[òóô]", "o", s)
    s = re.sub(r"[ùúû]", "u", s)
    s = re.sub(r"æ", "ae", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="mass-propers",
        description="Generate a Spanish-scripture EPUB of the 1962-Missal Mass "
        "propers for a Gregorian date.",
    )
    ap.add_argument("date", type=_parse_date, help="Gregorian date, YYYY-MM-DD")
    ap.add_argument(
        "-o", "--output", default=None,
        help="output EPUB path (default: output/<date>_<day>.epub)",
    )
    ap.add_argument(
        "--source", choices=("local", "remote"), default="local",
        help="local: run the checked-out DivinumOfficium Perl CGI (default); "
        "remote: query divinumofficium.com (may be blocked by Cloudflare)",
    )
    ap.add_argument("--no-cache", action="store_true", help="ignore the fetch cache")
    ap.add_argument(
        "--list", action="store_true", dest="list_only",
        help="only print the resolved day and its citations; no EPUB",
    )
    args = ap.parse_args(argv)

    body = fetch_propers_html(
        args.date, VERSION_1962, backend=args.source, use_cache=not args.no_cache
    )
    day = parse_propers_html(body)
    print(f"{args.date.isoformat()}  ->  {day.day_name}"
          + (f" ({day.rank})" if day.rank else ""))
    for sec_name, cit in day.all_citations():
        print(f"  [{sec_name}] {cit.source}  ->  {cit.display}")

    if not day.sections:
        print("No scripture citations found for this day; no EPUB generated.",
              file=sys.stderr)
        return 1
    if args.list_only:
        return 0

    bible = Bible()
    out = args.output or f"output/{args.date.isoformat()}_{_slug(day.day_name)}.epub"
    build_epub(day, args.date, bible, out)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
