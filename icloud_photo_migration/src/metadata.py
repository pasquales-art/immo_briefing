"""EXIF-/Metadaten-Handling via exiftool.

Strategie für vollständigen Erhalt:
  1. Pixel/Frames konvertieren (siehe convert.py).
  2. ALLE Metadaten vom Original in die Zieldatei kopieren (-all:all).
  3. Aufnahmedatum prüfen; fehlt es -> Fallback-Datum in die Datumsfelder schreiben.
  4. Dateisystem-Zeit (mtime) auf das Aufnahmedatum setzen (Sortier-Fallback).

exiftool ist das robusteste Werkzeug hierfür (GPS, Kamera, alle Hersteller-Tags).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

from .logging_setup import get_logger

log = get_logger()

# Datumsfelder je Medientyp
_IMAGE_DATE_TAGS = ("DateTimeOriginal", "CreateDate", "ModifyDate")
_VIDEO_DATE_TAGS = ("CreateDate", "ModifyDate", "TrackCreateDate", "MediaCreateDate")
# Reihenfolge beim LESEN – erstes gefundenes gewinnt
_READ_PRIORITY = (
    "DateTimeOriginal",
    "CreateDate",
    "CreationDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "ModifyDate",
    "GPSDateTime",
)


def has_exiftool() -> bool:
    return shutil.which("exiftool") is not None


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["exiftool", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def copy_all_metadata(src: Path, dst: Path) -> bool:
    """Kopiert ALLE Metadaten (inkl. GPS, Kamera) von src nach dst. True bei Erfolg."""
    if not has_exiftool():
        log.warning("exiftool nicht gefunden – Metadaten werden NICHT kopiert.")
        return False
    res = _run(
        [
            "-overwrite_original",
            "-preserve",          # Dateisystem-Zeiten beibehalten
            "-TagsFromFile",
            str(src),
            "-all:all",
            "-icc_profile",
            str(dst),
        ]
    )
    if res.returncode != 0:
        log.warning("Metadaten-Kopie fehlgeschlagen (%s): %s", dst.name, res.stderr.strip())
        return False
    return True


def read_capture_datetime(path: Path) -> datetime | None:
    """Liest bestes verfügbares Aufnahmedatum. None wenn keins vorhanden."""
    if not has_exiftool():
        return None
    res = _run(["-j", "-time:all", "-G", "-a", "-s", str(path)])
    if res.returncode != 0 or not res.stdout.strip():
        return None
    try:
        data = json.loads(res.stdout)[0]
    except (json.JSONDecodeError, IndexError):
        return None

    # exiftool liefert Tags teils mit Gruppenpräfix (z.B. "EXIF:DateTimeOriginal")
    flat: dict[str, str] = {}
    for k, v in data.items():
        short = k.split(":")[-1]
        if isinstance(v, str):
            flat.setdefault(short, v)

    for tag in _READ_PRIORITY:
        if tag in flat:
            dt = _parse_exif_dt(flat[tag])
            if dt:
                return dt
    return None


def _parse_exif_dt(value: str) -> datetime | None:
    value = value.strip()
    # gängige exiftool-Formate
    for fmt in (
        "%Y:%m:%d %H:%M:%S",
        "%Y:%m:%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y:%m:%d",
    ):
        try:
            # Zeitzonen-Doppelpunkt (+02:00) entfernen für %z
            v = value
            if fmt.endswith("%z") and len(v) >= 6 and v[-3] == ":":
                v = v[:-3] + v[-2:]
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def ensure_capture_date(
    path: Path, fallback: date, is_video: bool
) -> tuple[datetime, bool]:
    """Stellt sicher, dass ein Aufnahmedatum vorhanden ist.

    Returns (verwendetes_datum, war_fallback).
    """
    existing = read_capture_datetime(path)
    if existing is not None:
        _set_file_times(path, existing)
        return existing, False

    # Fallback schreiben
    dt = datetime(fallback.year, fallback.month, fallback.day, 12, 0, 0)
    stamp = dt.strftime("%Y:%m:%d %H:%M:%S")
    tags = _VIDEO_DATE_TAGS if is_video else _IMAGE_DATE_TAGS
    if has_exiftool():
        args = ["-overwrite_original"]
        args += [f"-{t}={stamp}" for t in tags]
        args.append(str(path))
        res = _run(args)
        if res.returncode != 0:
            log.warning("Fallback-Datum schreiben fehlgeschlagen (%s): %s",
                        path.name, res.stderr.strip())
    _set_file_times(path, dt)
    log.info("Fallback-Datum %s gesetzt: %s", fallback.isoformat(), path.name)
    return dt, True


def _set_file_times(path: Path, dt: datetime) -> None:
    try:
        ts = dt.timestamp()
        os.utime(path, (ts, ts))
    except OSError as e:
        log.debug("os.utime fehlgeschlagen für %s: %s", path.name, e)
