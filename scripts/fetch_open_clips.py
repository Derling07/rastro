#!/usr/bin/env python3
"""Download openly licensed camera clips into web/public/cameras.

This script does not commit the files. Run it locally when the clips are
missing. Chiang Mai is not in this list and must not be published: this
project does not redistribute that recording.

Each download is checked for a complete body (size matches Content-Length
when the server sends one, and the file starts with the format's magic
bytes). WebM and Ogg sources are converted to H.264 MP4 with ffmpeg.
Credits are written to web/public/cameras/CREDITS.md.

Sites that are not in this list, or whose file is missing, show
"Clip not available" in the app.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = ROOT / "web" / "public" / "cameras"
CREDITS = DEST_DIR / "CREDITS.md"
MIN_BYTES = 50_000

# Direct Wikimedia URLs for files whose licenses allow redistribution.
# Chiang Mai is intentionally absent.
# commons_file is the File: title. The script asks Wikimedia for the current URL.
# Chiang Mai is not listed.
CLIPS = [
    {
        "file": "wicker.mp4",
        "commons_file": "Wicker Park intersection changes.webm",
        "magic": b"\x1a\x45\xdf\xa3",
        "title": "Wicker Park intersection changes",
        "author": "Steven Vance",
        "license": "CC BY 3.0",
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Wicker_Park_intersection_changes.webm",
    },
    {
        "file": "gray-fox.mp4",
        "commons_file": "Gray fox (Urocyon cinereoargenteus) in New Mexico.webm",
        "magic": b"\x1a\x45\xdf\xa3",
        "title": "Gray fox (Urocyon cinereoargenteus) in New Mexico",
        "author": "Andy",
        "license": "CC BY 3.0",
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Gray_fox_(Urocyon_cinereoargenteus)_in_New_Mexico.webm",
    },
    {
        "file": "goats.mp4",
        "commons_file": "A video on goats going to home.ogv",
        "magic": b"OggS",
        "title": "A video on goats going to home",
        "author": "Thamizhpparithi Maari",
        "license": "CC BY-SA 3.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:A_video_on_goats_going_to_home.ogv",
    },
    {
        "file": "plaza.mp4",
        "commons_file": "Plaza Mayor (Madrid).ogv",
        "magic": b"OggS",
        "title": "Plaza Mayor (Madrid)",
        "author": "Michiel1972 (M.M. Minderhoud)",
        "license": "CC BY-SA 3.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Plaza_Mayor_(Madrid).ogv",
    },
]


def _commons_url(filename: str) -> str:
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "titles": f"File:{filename}",
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        }
    )
    request = urllib.request.Request(
        f"https://commons.wikimedia.org/w/api.php?{query}",
        headers={"User-Agent": "rastro-fetch-open-clips"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode())
    pages = (payload.get("query") or {}).get("pages") or {}
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("url")
        if url:
            return str(url)
    raise RuntimeError(f"Commons has no download URL for {filename}")


def _download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "rastro-fetch-open-clips"})
    with urllib.request.urlopen(request, timeout=120) as response:
        expected = response.headers.get("Content-Length")
        body = response.read()
        if expected is not None and len(body) != int(expected):
            raise RuntimeError(f"incomplete download for {url}: {len(body)} != {expected}")
    if len(body) < MIN_BYTES:
        raise RuntimeError(f"download too small for {url}: {len(body)} bytes")
    dest.write_bytes(body)


def _looks_like(path: Path, magic: bytes) -> bool:
    head = path.read_bytes()[: max(len(magic), 64)]
    if magic == b"ftyp":
        return b"ftyp" in head
    return head.startswith(magic)


def _to_mp4(source: Path, dest: Path) -> None:
    if _looks_like(source, b"ftyp"):
        dest.write_bytes(source.read_bytes())
        return
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-an",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not dest.exists() or not _looks_like(dest, b"ftyp"):
        raise RuntimeError(proc.stderr[-500:] or "ffmpeg did not write an mp4")
    if dest.stat().st_size < MIN_BYTES:
        raise RuntimeError(f"converted file is too small: {dest}")


def _write_credits() -> None:
    lines = [
        "# Camera clip credits",
        "",
        "Fetched by `scripts/fetch_open_clips.py`. Chiang Mai is not included.",
        "The forest-trail clip is a blurred derivative of a LILA file and is not downloaded here.",
        "If a file is missing, the cameras page says Clip not available.",
        "",
    ]
    for clip in CLIPS:
        lines.extend(
            [
                f"## {clip['file']}",
                "",
                f"- Title: {clip['title']}",
                f"- Author: {clip['author']}",
                f"- License: {clip['license']} ({clip['license_url']})",
                f"- Source: {clip['source_url']}",
                "",
            ]
        )
    CREDITS.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for clip in CLIPS:
        dest = DEST_DIR / str(clip["file"])
        raw = dest.with_suffix(".download")
        print(f"fetch {clip['file']}")
        _download(_commons_url(str(clip["commons_file"])), raw)
        if not _looks_like(raw, clip["magic"]) and not _looks_like(raw, b"ftyp"):
            raw.unlink(missing_ok=True)
            raise RuntimeError(f"unexpected file header for {clip['file']}")
        _to_mp4(raw, dest)
        raw.unlink(missing_ok=True)
        if not _looks_like(dest, b"ftyp"):
            raise RuntimeError(f"{dest} is not a complete mp4")
        print(f"  ok {dest.stat().st_size} bytes · {clip['license']} · {clip['author']}")
    _write_credits()
    print(f"credits {CREDITS}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI reports the failure and stops.
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
