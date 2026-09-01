#!/usr/bin/env python3
"""Einstiegspunkt (CLI und Colab).

Ablauf:
  1. Config aus Umgebung/.env laden
  2. Logging + Ordner vorbereiten
  3. (optional) OneDrive-Login
  4. Pipeline starten
  5. Zusammenfassung ausgeben

Aufruf lokal:   python run.py
Aufruf Colab:   siehe notebook_colab.ipynb (ruft main() auf)
"""
from __future__ import annotations

import sys
from pathlib import Path

# .env laden, falls vorhanden (lokaler Test); in Colab kommen Werte aus Secrets.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass

from config import Config  # noqa: E402
from src.logging_setup import setup_logging  # noqa: E402
from src.metadata import has_exiftool  # noqa: E402
from src.convert import has_ffmpeg  # noqa: E402
from src.sources.onedrive import OneDriveClient  # noqa: E402
from src import pipeline  # noqa: E402


def preflight(cfg: Config, log) -> bool:
    """Prüft Voraussetzungen. Gibt False zurück, wenn Abbruch nötig."""
    ok = True
    problems = cfg.validate()
    for p in problems:
        log.error("KONFIG: %s", p)
        ok = False
    if not has_exiftool():
        log.error("exiftool fehlt -> Metadaten-Erhalt unmöglich. Bitte installieren.")
        ok = False
    if not has_ffmpeg():
        log.warning("ffmpeg fehlt -> Videos können NICHT konvertiert werden (Bilder ok).")
    log.info(
        "Konfig: test_mode=%s limit=%s delete_stage=%s fallback=%s gdrive=%s onedrive=%s",
        cfg.test_mode, cfg.test_limit, cfg.delete_stage, cfg.fallback_date,
        cfg.use_gdrive, cfg.use_onedrive,
    )
    return ok


def main() -> int:
    cfg = Config()
    cfg.ensure_dirs()
    log = setup_logging(cfg.logs_dir)

    if not preflight(cfg, log):
        log.error("Preflight fehlgeschlagen -> Abbruch. Bitte Meldungen oben beheben.")
        return 2

    onedrive = None
    if cfg.use_onedrive:
        try:
            onedrive = OneDriveClient(
                client_id=cfg.ms_client_id,       # type: ignore[arg-type]
                tenant=cfg.ms_tenant,
                cache_path=cfg.state_dir / "token_cache.bin",
            )
            onedrive.login()
        except Exception as e:  # noqa: BLE001
            log.error("OneDrive-Login fehlgeschlagen: %s", e)
            log.warning("Fahre nur mit Google Drive fort.")
            onedrive = None
            cfg.use_onedrive = False

    summary = pipeline.run(cfg, onedrive)

    print("\n================= ZUSAMMENFASSUNG =================")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("===================================================")
    print(f"\nFertige Dateien liegen in: {cfg.ready_dir}")
    print("Nächster Schritt: iPhone-Kurzbefehl ausführen (siehe SHORTCUT.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
