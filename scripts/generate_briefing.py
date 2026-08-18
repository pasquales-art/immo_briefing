#!/usr/bin/env python3
"""Daily briefing generator.

Downloads the newest PDF from SOURCE_URL, has Claude read and summarize it
into the app's Markdown convention (a leading blockquote as "Kurzfassung",
then `## Eyebrow` / `### Headline` / paragraph / optional link sections),
and writes docs/posts/<date>.md plus a matching docs/posts/index.json entry.

Run manually with:  ANTHROPIC_API_KEY=... python scripts/generate_briefing.py

NOTE on the scraping step: the sandbox this script was written in could not
reach sfp.ch (network egress was blocked there), so `find_pdf_links` /
`pick_newest_pdf` below were written against the *general* shape of a page
that links out to dated PDFs, not against sfp.ch's actual markup. The first
real run's log line ("Using PDF: ... (<strategy>)") shows which heuristic
fired — check it against the real page and adjust the two functions if it
picked the wrong file.
"""

import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import anthropic
import requests
from pypdf import PdfReader

SOURCE_URL = "https://www.sfp.ch/soupe-du-jour"
REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "docs" / "posts"
INDEX_PATH = POSTS_DIR / "index.json"
TZ = ZoneInfo("Europe/Zurich")
MODEL = "claude-opus-5"

DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-_.](\d{2})[-_.](\d{2})"),  # 2026-08-17
    re.compile(r"(\d{2})[-_.](\d{2})[-_.](20\d{2})"),  # 17-08-2026
]

SYSTEM_PROMPT = """\
Du bist Redaktor für ein tägliches Morgenbriefing (Schweizer Publikum, \
professionell, ruhig, sachlich — kein Boulevard-Ton).

Dir wird der Rohtext eines PDF-Dokuments gegeben. Fasse seinen tatsächlichen \
Inhalt sachlich zusammen und strukturiere ihn in 2 bis 5 thematische \
Abschnitte, die sich natürlich aus dem Dokument ergeben — erfinde keine \
Themen wie Immobilienmarkt/Kapitalmarkt, wenn das Dokument etwas anderes \
behandelt. Schreibe auf Deutsch.

Antworte NUR in exakt diesem Format, ohne zusätzliche Erklärungen davor \
oder danach:

TITLE: <kurzer, prägnanter Titel, max. 80 Zeichen>
---
> <Kurzfassung des gesamten Inhalts in 2-3 Sätzen>

## <Eyebrow-Label Abschnitt 1, 1-3 Wörter, z.B. eine Kategorie oder ein Thema>
### <Prägnante Schlagzeile für Abschnitt 1>
<Fliesstext, 2-4 Sätze>

## <Eyebrow-Label Abschnitt 2>
### <Schlagzeile Abschnitt 2>
<Fliesstext>

(usw. für weitere Abschnitte, so viele wie inhaltlich sinnvoll sind)

Regeln:
- Der Blockquote (Kurzfassung) kommt genau einmal, direkt nach der TITLE-Zeile.
- Jeder Abschnitt beginnt mit "## " (Eyebrow) gefolgt von "### " (Headline).
- Keine Links erfinden. Nur wenn im Originaltext eine konkrete URL genannt \
wird, darfst du sie als "[Linktext →](URL)" ergänzen — sonst weglassen.
- Kein H1, keine weitere Formatierung ausserhalb der oben gezeigten Struktur.
"""


def find_pdf_links(html, base_url):
    hrefs = re.findall(r'href="([^"]+\.pdf)"', html, re.I)
    seen = []
    for h in hrefs:
        u = urljoin(base_url, h)
        if u not in seen:
            seen.append(u)
    return seen


def extract_date_from_url(url):
    name = url.rsplit("/", 1)[-1]
    for pat in DATE_PATTERNS:
        m = pat.search(name)
        if not m:
            continue
        groups = m.groups()
        y, mo, d = groups if len(groups[0]) == 4 else (groups[2], groups[1], groups[0])
        try:
            return datetime(int(y), int(mo), int(d))
        except ValueError:
            continue
    return None


def pick_newest_pdf(links):
    dated = [(extract_date_from_url(u), u) for u in links]
    dated = [d for d in dated if d[0] is not None]
    if dated:
        dated.sort(key=lambda d: d[0], reverse=True)
        return dated[0][1], "picked by date found in filename"
    if links:
        return links[0], "no dated filenames found on the page; used the first PDF link in document order"
    return None, None


def fetch_pdf_text(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    reader = PdfReader(io.BytesIO(resp.content))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def summarize(pdf_text, is_weekly):
    client = anthropic.Anthropic()
    user_note = (
        "Hinweis: Dies ist eine Wochenend-/Wochenrückblick-Ausgabe.\n\n"
        if is_weekly
        else ""
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_note + pdf_text}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")

    if not text.lstrip().startswith("TITLE:") or "---" not in text:
        raise ValueError("Unexpected model output shape:\n" + text[:500])

    title_line, _, body = text.partition("---")
    title = title_line.split("TITLE:", 1)[1].strip()
    return title, body.strip()


def load_index():
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return []


def save_index(entries):
    entries = sorted(entries, key=lambda e: e["date"], reverse=True)
    INDEX_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    today = datetime.now(TZ).date()
    is_weekly = today.weekday() == 6  # Monday=0 ... Sunday=6

    print(f"Fetching {SOURCE_URL} ...")
    html = requests.get(SOURCE_URL, timeout=30).text
    links = find_pdf_links(html, SOURCE_URL)
    pdf_url, strategy = pick_newest_pdf(links)
    if not pdf_url:
        print("No PDF link found on the source page — aborting.", file=sys.stderr)
        sys.exit(1)
    print(f"Using PDF: {pdf_url} ({strategy})")

    text = fetch_pdf_text(pdf_url)
    if not text.strip():
        print("Extracted PDF text is empty — aborting.", file=sys.stderr)
        sys.exit(1)

    title, body_md = summarize(text, is_weekly)

    date_str = today.isoformat()
    filename = f"{date_str}.md"
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    (POSTS_DIR / filename).write_text(body_md + "\n", encoding="utf-8")

    entries = [e for e in load_index() if e["date"] != date_str]
    entries.append(
        {"date": date_str, "title": title, "file": filename, "weekly": is_weekly}
    )
    save_index(entries)

    print(f"Wrote {filename} — \"{title}\"")


if __name__ == "__main__":
    main()
