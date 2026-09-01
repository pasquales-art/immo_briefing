"""Persistenter Zustand: welche Dateien sind fertig / geladen / gelöscht.

Zweck: Colab ist flüchtig -> nach Abbruch fortsetzbar; keine Doppel-Uploads;
saubere Trennung der 3 Lösch-Stufen. JSON-Datei im Google Drive (überlebt Neustart).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .logging_setup import get_logger

log = get_logger()

# Status-Werte pro Datei
PENDING = "pending"
READY = "ready"          # konvertiert + im Fertig-Ordner (bereit für iPhone-Import)
DELETED_TRASH = "trashed"
DELETED_PERM = "deleted"
ERROR = "error"


class State:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                log.info("State geladen: %d Einträge aus %s", len(self.data), self.path.name)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("State-Datei unlesbar (%s), starte leer.", e)
                self.data = {}

    def save(self) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def status(self, key: str) -> str | None:
        rec = self.data.get(key)
        return rec.get("status") if rec else None

    def is_ready_or_done(self, key: str) -> bool:
        return self.status(key) in (READY, DELETED_TRASH, DELETED_PERM)

    def update(self, key: str, **fields) -> None:
        with self._lock:
            rec = self.data.setdefault(key, {})
            rec.update(fields)
            rec["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for rec in self.data.values():
            s = rec.get("status", "?")
            out[s] = out.get(s, 0) + 1
        return out
