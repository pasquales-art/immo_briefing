"""OneDrive über Microsoft Graph (Device-Code-Login, kein Passwort im Code).

Auth: MSAL Device-Code-Flow -> du öffnest 1x eine URL + Code am Handy/Browser.
Token wird lokal gecacht (token_cache.bin, gitignored).

Lesen  : Dateien im Zielordner auflisten (nur Bilder/Videos).
Download: Datei-Inhalt holen.
Löschen: Graph DELETE -> landet im OneDrive-Papierkorb (= Stufe "trash").
         Für "permanent" muss der OneDrive-Papierkorb manuell geleert werden
         (Graph bietet für private Konten kein sicheres Hard-Delete).
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import msal
import requests

from ..logging_setup import get_logger
from . import SourceItem
from config import SUPPORTED_EXTS

log = get_logger()

_GRAPH = "https://graph.microsoft.com/v1.0"
_SCOPES = ["Files.ReadWrite"]


class OneDriveClient:
    def __init__(self, client_id: str, tenant: str, cache_path: Path):
        self._cache = msal.SerializableTokenCache()
        self._cache_path = cache_path
        if cache_path.exists():
            self._cache.deserialize(cache_path.read_text())
        self._app = msal.PublicClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant}",
            token_cache=self._cache,
        )
        self._token: str | None = None

    # --- Auth ---
    def login(self) -> None:
        result = None
        accounts = self._app.get_accounts()
        if accounts:
            result = self._app.acquire_token_silent(_SCOPES, account=accounts[0])
        if not result:
            flow = self._app.initiate_device_flow(scopes=_SCOPES)
            if "user_code" not in flow:
                raise RuntimeError(f"Device-Flow fehlgeschlagen: {flow}")
            print("\n=== OneDrive-Login ===")
            print(flow["message"])  # enthält URL + Code
            print("======================\n")
            result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"OneDrive-Login fehlgeschlagen: {result.get('error_description')}")
        self._token = result["access_token"]
        self._persist_cache()
        log.info("OneDrive-Login erfolgreich.")

    def _persist_cache(self) -> None:
        if self._cache.has_state_changed:
            self._cache_path.write_text(self._cache.serialize())

    def _headers(self) -> dict:
        if not self._token:
            self.login()
        return {"Authorization": f"Bearer {self._token}"}

    # --- Auflisten ---
    def list_items(self, folder_path: str) -> Iterator[SourceItem]:
        # Ordner per Pfad ansprechen
        url = f"{_GRAPH}/me/drive/root:/{folder_path.strip('/')}:/children"
        while url:
            r = requests.get(url, headers=self._headers(), timeout=60)
            if r.status_code == 404:
                log.warning("OneDrive-Ordner nicht gefunden: %s", folder_path)
                return
            r.raise_for_status()
            payload = r.json()
            for it in payload.get("value", []):
                if "folder" in it:
                    continue  # (nur oberste Ebene; für Rekursion hier erweitern)
                name = it.get("name", "")
                if Path(name).suffix.lower() not in SUPPORTED_EXTS:
                    continue
                yield SourceItem(
                    source="onedrive",
                    key=f"onedrive:{it['id']}",
                    name=name,
                    size=int(it.get("size", 0)),
                    remote_id=it["id"],
                )
            url = payload.get("@odata.nextLink")

    # --- Download ---
    def download(self, item: SourceItem, dest: Path) -> Path:
        assert item.remote_id
        url = f"{_GRAPH}/me/drive/items/{item.remote_id}/content"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, headers=self._headers(), stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
        return dest

    # --- Löschen (-> Papierkorb) ---
    def delete(self, item: SourceItem) -> None:
        assert item.remote_id
        url = f"{_GRAPH}/me/drive/items/{item.remote_id}"
        r = requests.delete(url, headers=self._headers(), timeout=60)
        if r.status_code not in (204, 404):
            r.raise_for_status()
        log.info("[trash] OneDrive gelöscht (Papierkorb): %s", item.name)
