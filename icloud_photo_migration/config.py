"""Zentrale Konfiguration. Liest aus Umgebungsvariablen (Colab-Secrets oder .env).

Keine Secrets im Code. Werte kommen aus:
  - Colab: google.colab.userdata (Secrets-Panel)  -> via os.environ gespiegelt (siehe Notebook)
  - Lokal: .env  (python-dotenv optional)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


def _get(key: str, default: str | None = None) -> str | None:
    val = os.environ.get(key)
    return val if val not in (None, "") else default


def _get_bool(key: str, default: bool) -> bool:
    val = _get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "ja", "y")


@dataclass
class Config:
    # --- Basis-Verzeichnisse (in Colab unter /content, lokal relativ) ---
    base_dir: Path = field(default_factory=lambda: Path(_get("BASE_DIR", ".")).resolve())

    # Google-Drive-Quellordner (Colab-Mount). "Bilder" laut Aufgabenstellung.
    gdrive_mount: Path = field(
        default_factory=lambda: Path(_get("GDRIVE_MOUNT", "/content/drive/MyDrive"))
    )
    gdrive_subdir: str = field(default_factory=lambda: _get("GDRIVE_SUBDIR", "Bilder"))

    # Hybrid-Ziel: fertige, iPhone-taugliche Dateien landen hier (in Google Drive),
    # damit der iPhone-Kurzbefehl sie in die Fotos-App / iCloud Photos importieren kann.
    ready_subdir: str = field(default_factory=lambda: _get("READY_SUBDIR", "Fertig_iCloud"))

    # OneDrive-Quellpfad (relativ zum Konto-Root), laut Aufgabe "Meine Daten/Bilder".
    onedrive_path: str = field(
        default_factory=lambda: _get("ONEDRIVE_PATH", "Meine Daten/Bilder")
    )

    # --- Test-Modus ---
    test_mode: bool = field(default_factory=lambda: _get_bool("TEST_MODE", True))
    test_limit: int = field(default_factory=lambda: int(_get("TEST_LIMIT", "100")))

    # --- Metadaten ---
    fallback_date: date = field(
        default_factory=lambda: datetime.strptime(
            _get("FALLBACK_DATE", "2022-12-01"), "%Y-%m-%d"
        ).date()
    )

    # --- Löschen: dry_run | trash | permanent ---
    delete_stage: str = field(default_factory=lambda: _get("DELETE_STAGE", "dry_run"))

    # --- Secrets (Hybrid braucht KEINE iCloud-Zugangsdaten) ---
    ms_client_id: str | None = field(default_factory=lambda: _get("MS_CLIENT_ID"))
    ms_tenant: str = field(default_factory=lambda: _get("MS_TENANT", "consumers"))

    # --- Quellen an/aus (falls du nur eine nutzen willst) ---
    use_gdrive: bool = field(default_factory=lambda: _get_bool("USE_GDRIVE", True))
    use_onedrive: bool = field(default_factory=lambda: _get_bool("USE_ONEDRIVE", True))

    # --- abgeleitete Arbeitspfade ---
    @property
    def work_dir(self) -> Path:
        return self.base_dir / "work"

    @property
    def ready_dir(self) -> Path:
        # Fertige Dateien für den iPhone-Import (liegt in Google Drive).
        return self.gdrive_mount / self.ready_subdir

    @property
    def trash_dir(self) -> Path:
        # "Papierkorb" für Google-Drive-Originale (Stufe 2), reversibel.
        return self.gdrive_mount / (self.ready_subdir + "_ZuLoeschen")

    @property
    def output_dir(self) -> Path:
        # lokaler Arbeits-Ausgabeordner (vor Verschieben in ready_dir).
        return self.base_dir / "output"

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def state_dir(self) -> Path:
        return self.base_dir / "state"

    def ensure_dirs(self) -> None:
        for d in (self.work_dir, self.output_dir, self.logs_dir, self.state_dir):
            d.mkdir(parents=True, exist_ok=True)
        # ready_dir/trash_dir liegen in Google Drive – nur anlegen, wenn Mount da ist.
        if self.gdrive_mount.exists():
            self.ready_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """Gibt Liste von Problemen zurück (leer = ok)."""
        problems: list[str] = []
        if self.delete_stage not in ("dry_run", "trash", "permanent"):
            problems.append(
                f"DELETE_STAGE ungültig: {self.delete_stage!r} "
                "(erlaubt: dry_run | trash | permanent)"
            )
        if self.use_gdrive and not self.gdrive_mount.exists():
            problems.append(
                f"Google-Drive-Mount nicht gefunden: {self.gdrive_mount} "
                "(im Colab-Notebook drive.mount() ausführen)."
            )
        if self.use_onedrive and not self.ms_client_id:
            problems.append("USE_ONEDRIVE=true aber MS_CLIENT_ID fehlt.")
        return problems


# unterstützte Dateiendungen (klein)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp", ".gif", ".bmp"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".3gp", ".mpg", ".mpeg", ".wmv", ".webm"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS
