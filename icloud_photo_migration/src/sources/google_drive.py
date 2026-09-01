"""Google Drive über den Colab-Mount (kein API-Token nötig).

Lesen  : rekursiv im Quellordner nach Bildern/Videos suchen.
Löschen: Stufe 2 (trash) = in "_ZuLoeschen"-Ordner verschieben (reversibel).
         Stufe 3 (permanent) = os.remove (endgültig aus dem Mount/Drive).
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator

from ..logging_setup import get_logger
from . import SourceItem
from config import SUPPORTED_EXTS

log = get_logger()


def list_items(mount: Path, subdir: str) -> Iterator[SourceItem]:
    root = mount / subdir
    if not root.exists():
        log.warning("Google-Drive-Quellordner fehlt: %s", root)
        return
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_EXTS:
            continue
        rel = p.relative_to(mount)
        yield SourceItem(
            source="gdrive",
            key=f"gdrive:{rel.as_posix()}",
            name=p.name,
            size=p.stat().st_size,
            local_path=p,
        )


def to_trash(item: SourceItem, trash_dir: Path, mount: Path) -> None:
    """Stufe 2: Original in Papierkorb-Ordner verschieben (reversibel)."""
    assert item.local_path is not None
    rel = item.local_path.relative_to(mount)
    target = trash_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(item.local_path), str(target))
    log.info("[trash] %s -> %s", item.name, target)


def delete_permanent(item: SourceItem) -> None:
    """Stufe 3: endgültig löschen."""
    assert item.local_path is not None
    if item.local_path.exists():
        item.local_path.unlink()
    log.info("[permanent] gelöscht: %s", item.name)
