"""Kleine Hilfs-Datentypen, um Zirkular-Importe zu vermeiden."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import state as st
from .sources.onedrive import OneDriveClient


@dataclass
class DeleteContext:
    stage: str
    state: st.State
    gdrive_mount: Path
    trash_dir: Path
    onedrive: Optional[OneDriveClient] = None
