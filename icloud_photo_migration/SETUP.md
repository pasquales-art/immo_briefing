# SETUP – Schritt für Schritt

Ziel: In ~30 Min startklar. Reihenfolge einhalten.

---

## Schritt 1 – Privates GitHub-Repo

1. github.com → **New repository**
2. Name: `foto-migration-icloud`
3. **Private** wählen ✅ (nur du)
4. Erstellen. → Code aus diesem Ordner hochladen (oder Repo wird für dich befüllt).

**Warum privat:** Code ist harmlos, aber Repo bleibt privat = null Risiko.
Secrets kommen NIE ins Repo (siehe `.gitignore`).

---

## Schritt 2 – GitHub-Token (damit Colab das private Repo laden kann)

1. github.com → Settings → Developer settings → **Fine-grained tokens** → *Generate*
2. Nur dieses Repo, Berechtigung **Contents: Read-only**
3. Ablauf z.B. 90 Tage
4. Token kopieren (nur 1x sichtbar) → in Colab-Secret `GH_TOKEN` (Schritt 5).

---

## Schritt 3 – Google Drive vorbereiten

- Quellordner heisst `Bilder` (unter „Meine Ablage"). Sonst `GDRIVE_SUBDIR` anpassen.
- Kein Token nötig: Colab mountet Drive nativ (OAuth-Fenster bestätigen).

---

## Schritt 4 – OneDrive-App registrieren (nur wenn OneDrive genutzt)

Microsoft Graph braucht eine (kostenlose) App-Registrierung:

1. https://entra.microsoft.com → **App registrations** → *New registration*
2. Name frei, „Accounts in any org directory and personal Microsoft accounts"
3. **Redirect URI:** Typ *Public client/native* → `https://login.microsoftonline.com/common/oauth2/nativeclient`
4. Nach Erstellen: **Application (client) ID** kopieren → Colab-Secret `MS_CLIENT_ID`.
5. *Authentication* → **Allow public client flows: Yes** (für Device-Code-Login).
6. Quellordner in OneDrive heisst `Meine Daten/Bilder`. Sonst `ONEDRIVE_PATH` anpassen.

> Kein OneDrive? In Zelle 4 des Notebooks `USE_ONEDRIVE='false'` setzen → Schritt 4 überspringen.

---

## Schritt 5 – Colab-Secrets setzen

Colab öffnen → linke Leiste **Schlüssel-Symbol** (Secrets) → je „Add new secret",
Zugriff für Notebook aktivieren:

| Name | Wert |
|---|---|
| `GH_TOKEN` | GitHub-Token aus Schritt 2 |
| `MS_CLIENT_ID` | Client-ID aus Schritt 4 (leer lassen ohne OneDrive) |

**Secrets landen NIE im Code oder Repo.** Genau dafür ist das Secrets-Panel da.

---

## Schritt 6 – Testlauf (Pflicht vor Vollversion)

1. `notebook_colab.ipynb` in Colab öffnen.
2. In Zelle 3 `REPO_URL` auf dein Repo setzen.
3. Zellen 1–5 der Reihe nach ausführen. Einstellungen in Zelle 4:
   - `TEST_MODE='true'`, `TEST_LIMIT='100'`
   - `DELETE_STAGE='dry_run'` (löscht **nichts**)
4. Zelle 5 startet den Lauf. OneDrive: einmal Login-Code bestätigen.
5. Zelle 6/Log prüfen: 100 Dateien in `MyDrive/Fertig_iCloud`? Datum korrekt?

---

## Schritt 7 – iPhone-Import testen

- `SHORTCUT.md` befolgen → Kurzbefehl importiert `Fertig_iCloud` in Fotos.
- In Fotos prüfen: Bilder korrekt nach Datum? GPS/Ort vorhanden?

---

## Schritt 8 – Vollversion + Löschen (stufenweise)

Nacheinander, jeweils Log prüfen:

1. `TEST_MODE='false'` → alle Dateien konvertieren (noch `DELETE_STAGE='dry_run'`).
2. Import am iPhone kontrollieren (alles in iCloud Photos angekommen?).
3. `DELETE_STAGE='trash'` → Originale in Papierkorb/`_ZuLoeschen` (reversibel).
4. Ein paar Tage prüfen. Dann `DELETE_STAGE='permanent'` → endgültig, Speicher frei.

---

## Ist dieses Setup geeignet? – Ja, mit diesen Hinweisen

- ✅ Colab reicht für Zehntausende Fotos (in Schüben; State erlaubt Wiederaufnahme).
- ✅ Kein lokaler Rechner nötig, funktioniert vom Arbeitslaptop (nur Browser).
- ⚠️ Colab-Sitzung kann nach Stunden/Inaktivität trennen → Notebook erneut ab
  Zelle 5 starten; dank State werden erledigte Dateien übersprungen.
- ⚠️ Grosse Videos brauchen Zeit/CPU. Bei sehr vielen Videos in Schüben laufen lassen.
- ⚠️ `BASE_DIR` liegt in Drive → Logs/State überleben Sitzungsende.

## Häufige Fehler

| Meldung | Ursache / Lösung |
|---|---|
| „Google-Drive-Mount nicht gefunden" | Zelle 1 (mount) nicht ausgeführt |
| „exiftool fehlt" | Zelle 2 (apt install) nicht ausgeführt |
| „MS_CLIENT_ID fehlt" | Secret nicht gesetzt, oder `USE_ONEDRIVE='false'` |
| OneDrive-Login schlägt fehl | Schritt 4.5 „public client flows: Yes" fehlt |
| Repo clone 403 | `GH_TOKEN` falsch / abgelaufen / keine Contents-Read-Rechte |
