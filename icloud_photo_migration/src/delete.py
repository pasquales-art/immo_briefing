"""3-Stufen-Löschung der Original-Dateien.

Stufe (config.delete_stage):
  dry_run   -> NUR loggen, was gelöscht würde. Nichts wird verändert. (Default)
  trash     -> Google Drive: Original in "_ZuLoeschen"-Ordner verschieben (reversibel).
               OneDrive: löschen -> landet im OneDrive-Papierkorb (reversibel).
  permanent -> Google Drive: endgültig entfernen.
               OneDrive: löschen -> Papierkorb (dort manuell leeren).

Gelöscht wird IMMER nur, wenn die Datei zuvor erfolgreich im Fertig-Ordner liegt
(Status READY im State). Sonst nie.
"""
from __future__ import annotations

from .config_types import DeleteContext
from .logging_setup import get_logger
from . import state as st
from .sources import SourceItem
from .sources import google_drive as gd

log = get_logger()


def apply_deletion(item: SourceItem, ctx: DeleteContext) -> None:
    """Wendet die konfigurierte Lösch-Stufe auf EIN bereits gesichertes Original an."""
    stage = ctx.stage

    if stage == "dry_run":
        log.info("[dry_run] würde löschen: %s (%s)", item.name, item.source)
        return

    try:
        if item.source == "gdrive":
            if stage == "trash":
                gd.to_trash(item, ctx.trash_dir, ctx.gdrive_mount)
                ctx.state.update(item.key, status=st.DELETED_TRASH)
            elif stage == "permanent":
                gd.delete_permanent(item)
                ctx.state.update(item.key, status=st.DELETED_PERM)

        elif item.source == "onedrive":
            # Graph-DELETE = Papierkorb (bei beiden Stufen).
            if ctx.onedrive is None:
                log.warning("OneDrive-Client fehlt, überspringe Löschung: %s", item.name)
                return
            ctx.onedrive.delete(item)
            ctx.state.update(
                item.key,
                status=st.DELETED_TRASH if stage == "trash" else st.DELETED_PERM,
            )
            if stage == "permanent":
                log.info("Hinweis: OneDrive endgültig -> Papierkorb manuell leeren.")

    except Exception as e:  # noqa: BLE001
        log.error("Löschen fehlgeschlagen (%s): %s", item.name, e)
        ctx.state.update(item.key, delete_error=str(e))
