#!/usr/bin/env python3
"""
Download every source file into data/raw/ (skipped when the file is already there).

    python scripts/download.py              # all sources
    python scripts/download.py worldpop     # only the named ones

Writes data/raw/SOURCES.json with the URL, size, SHA-256 and download date of each
file, so a result can always be traced back to the exact input.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import urllib.request

from config import RAW, SOURCES

UA = "opendata-disaster-ankara (https://github.com/MustafaBugraBEKDEMiR/opendata-disaster-ankara)"


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url: str, dest) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while block := r.read(1 << 20):
            f.write(block)
            done += len(block)
            if total and done % (50 << 20) < (1 << 20):
                print(f"    {done / 2**20:,.0f} / {total / 2**20:,.0f} MB")
    tmp.replace(dest)


def main(names: list[str]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    log_path = RAW / "SOURCES.json"
    log = json.loads(log_path.read_text("utf-8")) if log_path.exists() else {}
    for key in names or SOURCES:
        src = SOURCES[key]
        dest = RAW / src["file"]
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  cached  {dest.name}")
        else:
            print(f"  fetch   {src['url']}")
            fetch(src["url"], dest)
        if data_is_html(dest):
            sys.exit(f"{dest.name}: the server returned an HTML page instead of the file")
        digest = sha256(dest)
        old = log.get(key, {})
        log[key] = {
            "url": src["url"], "file": src["file"], "licence": src["licence"],
            "bytes": dest.stat().st_size, "sha256": digest,
            "downloaded": old["downloaded"] if old.get("sha256") == digest else dt.date.today().isoformat(),
        }
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", "utf-8")


def data_is_html(path) -> bool:
    with open(path, "rb") as f:
        head = f.read(512).lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


if __name__ == "__main__":
    main(sys.argv[1:])
