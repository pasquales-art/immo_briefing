"""Orchestrierung: sammeln -> konvertieren -> in Fertig-Ordner -> verifizieren
-> State speichern -> (Lösch-Stufe anwenden).

Robust: pro Datei gekapselte Fehlerbehandlung; Wiederaufnahme über State;
Test-Modus begrenzt auf TEST_LIMIT Dateien.
"""
from __future__ import annotations

import shutil
from itertools import islice
from pathlib import Path
from typing import Iterator

from config import Config
from . import state as st
from .config_types import DeleteContext
from .convert import ConversionError, convert_file
from .delete import apply_deletion
from .logging_setup import get_logger
from .sources import SourceItem
from .sources import google_drive as gd
from .sources.onedrive import OneDriveClient

log = get_logger()


def gather_items(cfg: Config, onedrive: OneDriveClient | None) -> Iterator[SourceItem]:
    if cfg.use_gdrive:
        yield from gd.list_items(cfg.gdrive_mount, cfg.gdrive_subdir)
    if cfg.use_onedrive and onedrive is not None:
        yield from onedrive.list_items(cfg.onedrive_path)


def run(cfg: Config, onedrive: OneDriveClient | None) -> dict:
    cfg.ensure_dirs()
    state = st.State(cfg.state_dir / "state.json")

    ready_dir = cfg.ready_dir
    ready_dir.mkdir(parents=True, exist_ok=True)

    del_ctx = DeleteContext(
        stage=cfg.delete_stage,
        state=state,
        gdrive_mount=cfg.gdrive_mount,
        trash_dir=cfg.trash_dir,
        onedrive=onedrive,
    )

    items = gather_items(cfg, onedrive)
    if cfg.test_mode:
        items = islice(items, cfg.test_limit)
        log.info("TEST-MODUS aktiv: max. %d Dateien.", cfg.test_limit)

    processed = ok = skipped = failed = 0

    for item in items:
        processed += 1
        # Wiederaufnahme: bereits fertige/gelöschte überspringen
        if state.is_ready_or_done(item.key):
            skipped += 1
            log.debug("übersprungen (schon erledigt): %s", item.name)
            continue
        try:
            _process_one(item, cfg, state, del_ctx)
            ok += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            log.error("FEHLER bei %s: %s", item.name, e)
            state.update(item.key, status=st.ERROR, error=str(e), name=item.name)
        finally:
            if processed % 10 == 0:
                state.save()

    state.save()
    summary = {
        "verarbeitet": processed,
        "erfolgreich": ok,
        "übersprungen": skipped,
        "fehler": failed,
        "status_counts": state.counts(),
        "delete_stage": cfg.delete_stage,
        "test_mode": cfg.test_mode,
    }
    log.info("FERTIG. Zusammenfassung: %s", summary)
    return summary


def _process_one(item: SourceItem, cfg: Config, state: st.State, del_ctx: DeleteContext) -> None:
    # 1) lokale Kopie beschaffen
    if item.source == "gdrive":
        src_local = item.local_path
        assert src_local is not None
    else:  # onedrive
        src_local = cfg.work_dir / item.name
        del_ctx.onedrive.download(item, src_local)  # type: ignore[union-attr]

    # 2) konvertieren (+ EXIF/Datum)
    try:
        result = convert_file(src_local, cfg.work_dir, cfg.fallback_date)
    except ConversionError as e:
        raise e

    converted: Path = result["dst"]

    # 3) in Fertig-Ordner (Google Drive) verschieben -> für iPhone-Import
    ready_path = _unique_path(cfg.ready_dir / converted.name)
    shutil.move(str(converted), str(ready_path))

    # 4) verifizieren
    if not ready_path.exists() or ready_path.stat().st_size == 0:
        raise RuntimeError(f"Verifikation fehlgeschlagen: {ready_path}")

    state.update(
        item.key,
        status=st.READY,
        name=item.name,
        source=item.source,
        ready_path=str(ready_path),
        capture_date=result["capture_date"].isoformat(),
        used_fallback=result["used_fallback"],
        is_video=result["is_video"],
    )
    log.info("READY: %s -> %s%s", item.name, ready_path.name,
             "  [Fallback-Datum]" if result["used_fallback"] else "")

    # 5) OneDrive-Arbeitsdatei aufräumen (Original bleibt in der Quelle)
    if item.source == "onedrive" and src_local.exists():
        src_local.unlink()

    # 6) Lösch-Stufe auf Original anwenden (nur wenn READY erreicht)
    apply_deletion(item, del_ctx)


def _unique_path(path: Path) -> Path:
    """Verhindert Überschreiben bei Namensgleichheit."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 1
    while True:
        cand = path.with_name(f"{stem}_{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1
