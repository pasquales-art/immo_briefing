"""Konvertierung -> iPhone-taugliche Formate (JPEG / MP4) mit Metadaten-Erhalt.

Bilder: HEIC/PNG/TIFF/... -> JPEG (Qualität 95). Bereits-JPEG wird unverändert
        übernommen (perfekter EXIF-Erhalt). Danach werden ALLE Metadaten vom
        Original kopiert und ggf. Fallback-Datum gesetzt.
Videos: alles -> MP4 (H.264/AAC, yuv420p, +faststart). Bereits kompatible MP4
        werden per Stream-Copy remuxed. Danach Metadaten wie oben.
"""
from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

from PIL import Image

from config import IMAGE_EXTS, VIDEO_EXTS
from . import metadata as meta
from .logging_setup import get_logger

log = get_logger()

try:  # HEIC/HEIF-Support für Pillow
    import pillow_heif

    pillow_heif.register_heif_opener()
    _HEIF_OK = True
except Exception:  # pragma: no cover
    _HEIF_OK = False
    log.warning("pillow-heif nicht verfügbar – HEIC/HEIF können nicht gelesen werden.")


class ConversionError(Exception):
    pass


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def convert_file(src: Path, out_dir: Path, fallback: date) -> dict:
    """Konvertiert eine Datei. Returns dict mit Ergebnis-Infos.

    Wirft ConversionError bei nicht behebbaren Fehlern.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if is_image(src):
        dst = _convert_image(src, out_dir)
        video = False
    elif is_video(src):
        dst = _convert_video(src, out_dir)
        video = True
    else:
        raise ConversionError(f"Nicht unterstützter Typ: {src.suffix}")

    # ALLE Metadaten übernehmen (bei Bereits-JPEG/-MP4-Copy schon vorhanden, schadet nicht)
    meta.copy_all_metadata(src, dst)
    used_date, was_fallback = meta.ensure_capture_date(dst, fallback, is_video=video)

    return {
        "dst": dst,
        "is_video": video,
        "capture_date": used_date,
        "used_fallback": was_fallback,
    }


# --------------------------------------------------------------------------- #
# Bilder
# --------------------------------------------------------------------------- #
def _convert_image(src: Path, out_dir: Path) -> Path:
    ext = src.suffix.lower()
    dst = out_dir / (src.stem + ".jpg")

    if ext in (".jpg", ".jpeg"):
        # Original 1:1 übernehmen -> EXIF bleibt garantiert erhalten
        shutil.copy2(src, dst)
        return dst

    try:
        with Image.open(src) as im:
            im = _flatten_to_rgb(im)
            # exif=... aus Pillow ist unvollständig; das echte Kopieren macht exiftool danach.
            im.save(dst, format="JPEG", quality=95, subsampling=0)
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"Bild-Konvertierung fehlgeschlagen ({src.name}): {e}") from e
    return dst


def _flatten_to_rgb(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        background.paste(im, mask=im.split()[-1])
        return background
    if im.mode != "RGB":
        return im.convert("RGB")
    return im


# --------------------------------------------------------------------------- #
# Videos
# --------------------------------------------------------------------------- #
def _convert_video(src: Path, out_dir: Path) -> Path:
    if not has_ffmpeg():
        raise ConversionError("ffmpeg nicht installiert – Video-Konvertierung unmöglich.")
    dst = out_dir / (src.stem + ".mp4")

    if src.suffix.lower() == ".mp4" and _is_iphone_ready(src):
        # nur remuxen (schnell, verlustfrei), Metadaten mitnehmen
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-c", "copy", "-map_metadata", "0",
            "-movflags", "+faststart", str(dst),
        ]
        if _run_ffmpeg(cmd):
            return dst
        log.info("Stream-Copy fehlgeschlagen, transcodiere %s neu.", src.name)

    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.2",
        "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-map_metadata", "0", "-movflags", "+faststart",
        str(dst),
    ]
    if not _run_ffmpeg(cmd):
        raise ConversionError(f"Video-Konvertierung fehlgeschlagen: {src.name}")
    return dst


def _is_iphone_ready(path: Path) -> bool:
    """Grobe Prüfung: H.264-Video + AAC-Audio => nur remuxen nötig."""
    if not shutil.which("ffprobe"):
        return False
    try:
        v = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=False,
        ).stdout.strip().lower()
        return v == "h264"
    except Exception:  # noqa: BLE001
        return False


def _run_ffmpeg(cmd: list[str]) -> bool:
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        log.debug("ffmpeg-Fehler: %s", res.stderr.strip()[-800:])
        return False
    return True
