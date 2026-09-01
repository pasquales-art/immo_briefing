# Datenschutz-Checkliste

## Fazit
Sicher, wenn: Repo **privat**, Secrets nur im **Colab-Secrets-Panel**, Löschen
erst nach Verifikation und stufenweise. Nichts davon verlässt deine eigenen Konten
(Google, Microsoft, Apple) ausser du gibst es frei.

## Was ist sicher ✅

- **Repo privat** → nur du siehst den Code. Code enthält keine persönlichen Daten.
- **Secrets im Colab-Panel** → nicht im Code, nicht im Repo, nicht im Notebook-Output.
- **`.gitignore`** blockt `.env`, Tokens, Logs, State, Arbeits-/Ausgabeordner.
- **GitHub-Token** fein-granular, nur *dieses* Repo, nur *Read* → minimaler Schaden bei Verlust.
- **OneDrive-App** nur `Files.ReadWrite` auf *dein* Konto, Login via Device-Code (kein Passwort im Code).
- **Google Drive** via offiziellen Colab-Mount (Googles eigener OAuth) — kein Token gespeichert.
- **iCloud** wird gar nicht von Code angefasst → keine Apple-Zugangsdaten irgendwo. Import macht dein iPhone.
- **Datenfluss** bleibt in deinen Konten: Drive/OneDrive → Colab (Google, dein Konto) → Drive → iPhone.

## Worauf achten ⚠️

- **Colab läuft auf Google-Servern.** Deine Fotos werden dort kurz verarbeitet.
  Wer das nicht will, muss lokal statt Colab arbeiten. Für Google-Drive-Fotos ohnehin schon bei Google.
- **Token-Ablauf** setzen (GitHub 90 Tage). Nach dem Projekt Token/OneDrive-App **widerrufen**.
- **Notebook-Output nicht committen** — könnte Pfade/Dateinamen zeigen. `.ipynb` besser ohne Output speichern.
- **`Fertig_iCloud`-Ordner** enthält Kopien deiner Fotos in Drive → nach iPhone-Import aufräumen.
- **Papierkorb leeren** (Drive + OneDrive) erst, wenn alles sicher in iCloud Photos ist.

## Aufräumen nach Projektende

1. GitHub-Token löschen (Developer settings).
2. OneDrive-App-Registrierung entfernen (entra.microsoft.com) oder Berechtigung widerrufen.
3. Colab-Secrets löschen.
4. `Fertig_iCloud` + `_ZuLoeschen` in Drive leeren (nach Kontrolle in iCloud).
5. Repo behalten oder archivieren — enthält keine Daten.

## Löschen — Sicherheitsstufen (nie überspringen)

| Stufe | Wirkung | Reversibel? |
|---|---|---|
| `dry_run` | nur Log, nichts gelöscht | – (Default) |
| `trash` | Drive → `_ZuLoeschen`-Ordner; OneDrive → Papierkorb | ✅ ja |
| `permanent` | endgültig gelöscht | ❌ nein |

Regel im Code: Gelöscht wird **nur**, wenn die konvertierte Datei verifiziert im
`Fertig_iCloud`-Ordner liegt (Status `READY`). Sonst nie.
