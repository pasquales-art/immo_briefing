# Foto-Migration → iCloud Photos

Google Drive + OneDrive Bilder/Videos → iPhone-tauglich konvertieren (JPEG/MP4,
EXIF/GPS erhalten) → **iCloud Photos**, sauber nach Datum. Speicher auf
Drive/OneDrive freiräumen.

## Fazit / Funktionsweise (Hybrid)

1. **Colab** (läuft online, kein PC nötig): lädt aus Google Drive + OneDrive,
   konvertiert, erhält alle EXIF-Daten (Fallback-Datum `01.12.2022`), legt
   fertige Dateien in Google-Drive-Ordner `Fertig_iCloud`.
2. **iPhone-Kurzbefehl**: importiert `Fertig_iCloud` in die Fotos-App →
   synct automatisch in **iCloud Photos**, korrekt nach Datum.
3. **Löschen** der Originale in 3 Stufen: `dry_run` → `trash` → `permanent`.

> Bewusst **kein** pyicloud: Der iCloud-Upload läuft nativ am iPhone (zuverlässig),
> statt über eine fragile inoffizielle Schnittstelle.

## Schnellstart

1. `SETUP.md` durcharbeiten (Repo, Colab-Secrets, OneDrive-App).
2. `notebook_colab.ipynb` in Google Colab öffnen, Zellen der Reihe nach ausführen.
3. Testlauf mit 100 Dateien (`TEST_MODE=true`, `DELETE_STAGE=dry_run`).
4. iPhone-Kurzbefehl aus `SHORTCUT.md` ausführen.
5. Wenn gut: `TEST_MODE=false`, dann `DELETE_STAGE=trash`, zuletzt `permanent`.

## Dateien

| Datei | Zweck |
|---|---|
| `notebook_colab.ipynb` | Einstieg in Colab (hier startest du) |
| `run.py` | Programm-Einstieg (`main()`) |
| `config.py` | Einstellungen (aus Secrets/.env) |
| `src/convert.py` | JPEG/MP4-Konvertierung |
| `src/metadata.py` | EXIF/GPS erhalten, Fallback-Datum |
| `src/sources/` | Google Drive (Mount) + OneDrive (Graph) |
| `src/delete.py` | 3-Stufen-Löschung |
| `src/pipeline.py` | Ablaufsteuerung, Wiederaufnahme, Logging |
| `SETUP.md` | Einrichtung Schritt für Schritt |
| `DATENSCHUTZ.md` | Datenschutz-Checkliste |
| `SHORTCUT.md` | iPhone-Kurzbefehl |

## Sicherheit

- Repo **privat**. Keine Secrets im Code — nur Colab-Secrets / `.env` (gitignored).
- Löschen erst nach verifizierter fertiger Datei; Default ist `dry_run` (löscht nichts).
- Details: `DATENSCHUTZ.md`.
