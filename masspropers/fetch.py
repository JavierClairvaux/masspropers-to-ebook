"""Fetch the Mass propers page from DivinumOfficium for a given date.

Two backends:

* ``local`` (default): runs the DivinumOfficium Perl CGI (``missa.pl``) from the
  checked-out repo directly via a subprocess, emulating a CGI request with
  ``QUERY_STRING``/``REQUEST_METHOD``. This uses the project's own calendar and
  precedence code (Directorium.pm etc.) without reimplementing anything, and
  needs no Docker and no network.

* ``remote``: queries the public hosted site over HTTPS. Note: as of 2026-07,
  https://divinumofficium.com sits behind a Cloudflare JavaScript challenge
  that blocks plain HTTP clients, so this backend may return an error page in
  sandboxed environments. It is kept for completeness/portability.

Responses are cached on disk keyed by (date, version, backend); a cached page
is never re-fetched. Remote fetches sleep POLITE_DELAY seconds first.
"""

from __future__ import annotations

import datetime as _dt
import os
import subprocess
import time
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_HERE)
DO_MISSA_CGI_DIR = os.path.join(
    PROJECT_ROOT, "divinum-officium", "web", "cgi-bin", "missa"
)
CACHE_DIR = os.path.join(PROJECT_ROOT, "cache")

VERSION_1962 = "Rubrics 1960 - 1960"  # DO's name for the 1962-Missal rubrics
REMOTE_BASE = "https://divinumofficium.com/cgi-bin/missa/missa.pl"
POLITE_DELAY = 2.0  # seconds between remote requests

_last_remote_fetch = 0.0


def _query_string(date: _dt.date, version: str, lang: str = "Latin") -> str:
    """Build the missa.pl query string for a propers-only, single-column page.

    Empirically determined parameter set (see README):
      * date is MM-DD-YYYY;
      * lang1 == lang2 makes missa.pl emit a single column ($only mode);
      * command=pray&content=1 emits the bare content without page chrome;
      * Propers=1 substitutes the propers-only Ordo (Ordo/Propers.txt), so the
        output contains just Introitus..Postcommunio instead of the whole
        Order of Mass.

    *lang* defaults to "Latin" (used for citation extraction — the ``!``
    citation grammar is identical across language files). Pass "Espanol" to
    get DivinumOfficium's own Spanish prose instead, used for the
    non-scriptural propers (Oratio/Secreta/Postcommunio) that have no
    Scripture citation to look up in SpaPlatense.
    """
    params = {
        "date": date.strftime("%m-%d-%Y"),
        "version": version,
        "lang1": lang,
        "lang2": lang,
        "command": "pray",
        "content": "1",
        "Propers": "1",
    }
    return urllib.parse.urlencode(params)


def _cache_path(date: _dt.date, version: str, backend: str, lang: str = "Latin") -> str:
    slug = version.replace(" ", "_").replace("-", "").replace("__", "_")
    lang_suffix = "" if lang == "Latin" else f"_{lang}"
    return os.path.join(
        CACHE_DIR, f"{date.isoformat()}_{slug}_{backend}{lang_suffix}.html"
    )


def _fetch_local(date: _dt.date, version: str, lang: str = "Latin") -> str:
    env = dict(os.environ)
    env["QUERY_STRING"] = _query_string(date, version, lang)
    env["REQUEST_METHOD"] = "GET"
    # missa.pl relies on FindBin, so run it from its own directory.
    proc = subprocess.run(
        ["perl", "missa.pl"],
        cwd=DO_MISSA_CGI_DIR,
        env=env,
        capture_output=True,
        timeout=120,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    if proc.returncode != 0 or "\n\n" not in out:
        raise RuntimeError(
            f"missa.pl failed for {date} (rc={proc.returncode}):\n"
            f"{proc.stderr.decode('utf-8', errors='replace')[:2000]}"
        )
    # Strip the CGI header block (up to the first blank line).
    body = out.split("\n\n", 1)[1]
    if "Introitus" not in body and "error" in body.lower():
        raise RuntimeError(f"missa.pl returned an error page for {date}")
    return body


def _fetch_remote(date: _dt.date, version: str, lang: str = "Latin") -> str:
    global _last_remote_fetch
    wait = POLITE_DELAY - (time.monotonic() - _last_remote_fetch)
    if wait > 0:
        time.sleep(wait)
    url = f"{REMOTE_BASE}?{_query_string(date, version, lang)}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "mass-propers-epub/1.0 (polite; cached)"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    _last_remote_fetch = time.monotonic()
    if "challenge" in body and "cloudflare" in body.lower():
        raise RuntimeError(
            "divinumofficium.com returned a Cloudflare JS challenge; the "
            "remote backend is not usable from this network. Use --source local."
        )
    return body


def fetch_propers_html(
    date: _dt.date,
    version: str = VERSION_1962,
    backend: str = "local",
    use_cache: bool = True,
    lang: str = "Latin",
) -> str:
    """Return the propers-only HTML page for *date*, using the cache if possible."""
    path = _cache_path(date, version, backend, lang)
    if use_cache and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    if backend == "local":
        body = _fetch_local(date, version, lang)
    elif backend == "remote":
        body = _fetch_remote(date, version, lang)
    else:
        raise ValueError(f"unknown backend {backend!r}")
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return body
