# iPhone-Kurzbefehl – Fertig_iCloud → iCloud Photos

Ziel: Fertige Dateien aus dem Google-Drive-Ordner `Fertig_iCloud` in die
**Fotos-App** importieren. Von dort synct alles automatisch in **iCloud Photos**,
sortiert nach dem (von Colab gesetzten) EXIF-Datum.

## Voraussetzung
- App **Google Drive** am iPhone installiert und angemeldet.
- iCloud Photos aktiv: Einstellungen → [dein Name] → iCloud → Fotos → **ein**.

---

## Variante A – Ohne Kurzbefehl (am einfachsten, empfohlen zum Start)

1. Google-Drive-App → Ordner `Fertig_iCloud` öffnen.
2. Dateien auswählen (oder ganzen Ordner) → **Teilen** → **Bild/Video sichern**
   (bzw. „In Fotos sichern").
3. Fotos-App öffnen → prüfen: korrekt nach Datum einsortiert.
4. iCloud lädt automatisch hoch (WLAN + Strom empfohlen).

> Nachteil: bei sehr vielen Dateien mühsam. Dann Variante B.

---

## Variante B – Kurzbefehl (Batch)

App **Kurzbefehle** → **+** (neuer Kurzbefehl) → diese Aktionen:

1. **Dateien abrufen** (Get File) → Dienst: *Google Drive* → Ordner `Fertig_iCloud`,
   „Mehrere auswählen" **ein**.
2. **Wiederholen mit jedem** (Repeat with Each) über das Ergebnis:
   - **In Fotoalbum speichern** (Save to Photo Album) → *Aktuelles Foto* aus der Wiederholung.
3. Kurzbefehl benennen (z.B. „Import iCloud") → ausführen.

> Hinweis: Die Aktion „In Fotos speichern" übernimmt das im Datei-EXIF gespeicherte
> Aufnahmedatum als Fotodatum → korrekte Sortierung. Genau dafür setzt Colab das
> Datum (echtes EXIF oder Fallback `01.12.2022`).

---

## Kontrolle nach dem Import

- Fotos-App → „Zuletzt" und nach Datum: stimmen Reihenfolge/Jahre?
- Einzelnes Foto → nach oben wischen → **Ort/Karte** vorhanden? (= GPS erhalten)
- Erst wenn alles passt: in Drive/OneDrive löschen (Stufe `trash` → `permanent`).

## Wenn Datum/GPS fehlt
- Prüfen, ob im Colab-Log `exiftool` lief (Metadaten kopiert).
- Bilder ohne jedes Datum bekommen bewusst `01.12.2022` → landen gebündelt dort.
