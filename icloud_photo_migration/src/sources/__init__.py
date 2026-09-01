"""Quellen: Google Drive (Colab-Mount) und OneDrive (Microsoft Graph)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


@dataclass
class SourceItem:
    """Eine Quelldatei, quellenunabhängig beschrieben."""
    source: Literal["gdrive", "onedrive"]
    key: str            # stabiler eindeutiger Schlüssel (für State)
    name: str           # Dateiname inkl. Endung
    size: int           # Bytes
    # gdrive: lokaler Pfad im Mount; onedrive: None (erst downloaden)
    local_path: Optional[Path] = None
    # onedrive: Graph-Item-ID zum Download/Löschen
    remote_id: Optional[str] = None
