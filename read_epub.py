#!/usr/bin/env python3
"""Quick inline EPUB text dump — no dependencies. Usage: python3 read_epub.py file.epub"""
import re
import sys
import zipfile

path = sys.argv[1]
with zipfile.ZipFile(path) as z:
    for name in sorted(z.namelist()):
        if name.endswith(".xhtml"):
            text = z.read(name).decode("utf-8")
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
            print(f"\n===== {name} =====\n{text}")
