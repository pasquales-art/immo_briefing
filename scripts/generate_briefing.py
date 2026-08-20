#!/usr/bin/env python3
"""Daily briefing generator.

Reads the newest SFP "Soupe du Jour" PDF, has Claude research a fixed
checklist of Swiss real-estate/economy/politics topics via web search,
and writes it up in the app's Markdown convention (a leading blockquote
as "Kurzfassung", then `## Eyebrow` / `### Headline` / paragraph / link
sections, ordered by how newsworthy each topic is today — not a fixed
order, and topics with nothing to report are dropped or cut to one
sentence). Writes docs/posts/<date>.md plus a matching
docs/posts/index.json entry.

On Sundays, an extra "## Wochenrückblick" section is added, built from
the last 7 days of already-published posts.

Run manually with:  ANTHROPIC_API_KEY=... python scripts/generate_briefing.py

Modes (env var BRIEFING_MODE, default "full"):
  full  - normal behavior: (re)writes today's post and index.json entry.
  merge - if today's post already exists, only APPENDS sections that
          aren't already present (matched by eyebrow label) and leaves
          existing sections and the index.json title untouched. Meant
          for a manual same-day re-run that shouldn't clobber a post
          someone may have already read or hand-edited. Falls back to
          normal "full" behavior if no post exists yet for today.

NOTE on the scraping step: the sandbox this script was written in has no
network access to sfp.ch (an unrelated sandbox-only restriction — the GitHub
Actions runner that actually executes this has normal internet access), so
`find_download_links` / `pick_newest_pdf` below are written for TYPO3's
`eID=download&t=f&f=<id>&token=...` download links (confirmed as this
site's actual mechanism, verified against a real run's log) plus plain
`*.pdf` hrefs as a fallback.
"""

import io
import json
import os
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
MODEL = "claude-sonnet-5"
WEEKLY_CONTEXT_DAYS = 7

# Swiss outlets Claude is allowed to pull links from via web search, in the
# priority order from the brief: NZZ first, then Inside Paradeplatz / Tsüri,
# then the rest. (SFP itself isn't a search domain — its PDF text is given
# directly.) Edit freely to add more.
ALLOWED_NEWS_DOMAINS = [
    "nzz.ch",
    "insideparadeplatz.ch",
    "tsri.ch",
    "tagesanzeiger.ch",
    "fuw.ch",
    "bilanz.ch",
    "handelszeitung.ch",
    "20min.ch",
    "cash.ch",
    "watson.ch",
    "snb.ch",
]

DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-_.](\d{2})[-_.](\d{2})"),  # 2026-08-17
    re.compile(r"(\d{2})[-_.](\d{2})[-_.](20\d{2})"),  # 17-08-2026
]

SYSTEM_PROMPT_TEMPLATE = """\
Du bist Redaktor für ein tägliches Schweizer Immobilien- und \
Wirtschafts-Morgenbriefing. Zielgruppe: professionell, hohe Ansprüche an \
Informationsqualität. Ton: ruhig, sachlich, Schweizer Hochdeutsch — kein \
Boulevard, keine Übertreibungen.

UMFANG: 400–700 Wörter für den Tagesteil (ohne Wochenrückblick, falls \
vorhanden). Kompakt schreiben, nicht künstlich strecken.

THEMEN-PRÜFLISTE (für jedes prüfen: gibt es heute/gestern echte, konkrete \
News dazu?):
1. Leitzinsen & Geldpolitik (SNB/EZB/Fed, SARON, Hypozinsen)
2. Immobilienmarkt Schweiz
3. Mietrecht & Baurecht Schweiz
4. Kapitalmarkt mit Immobilien-Fokus
5. SFP Soupe du Jour (Inhalt wird dir unten als Text gegeben)
6. Wohnpolitik Schweiz (national/kantonal)
7. Kantonale Wirtschaftspolitik
8. Politik Stadt Zürich (inkl. Wohnpolitik)
9. Verkehrspolitik
10. Schweizer Volkswirtschaft & Arbeitsmarkt (inkl. Meinungen/Kommentare)
11. Weltgeschehen kompakt (grosse Titelseiten-Themen, max. 2–3 Sätze)

REGELN:
- Nur Themen mit echten, aktuellen News bekommen einen vollen Abschnitt. \
Themen ohne Neuigkeiten heute: ganz weglassen, oder — nur falls \
irgendetwas Erwähnenswertes vorliegt — in einem knappen Satz abhandeln.
- Reihenfolge der Abschnitte nach TAGESRELEVANZ (wichtigstes/aktuellstes \
zuerst). Die Liste oben ist eine Prüfliste, kein Ranking und keine feste \
Reihenfolge für den Output.
- Jeder volle Abschnitt braucht mindestens einen echten Link. \
Ein-Satz-Abschnitte dürfen ohne Link auskommen, wenn kein guter Beleg \
existiert.
- QUELLEN-PRIORITÄT für Links: 1. NZZ (bevorzugt — auch wenn Paywall: nur \
Titel/Snippet aus der Websuche zitieren, niemals versuchen, den \
Volltext hinter der Paywall abzurufen), 2. SFP Soupe du Jour (oft \
Volltext ohne Paywall), 3. Inside Paradeplatz / Tsüri.ch, 4. weitere \
seriöse Schweizer Medien (Tages-Anzeiger, Finanz und Wirtschaft, Bilanz, \
Handelszeitung, 20 Minuten, cash, watson). Keine automatisierten \
Paywall-Abrufe — nutze ausschliesslich, was die Websuche an \
Titel/Snippet/URL liefert.
- Für den Abschnitt "SFP Soupe du Jour" fügst du selbst KEINEN Link \
hinzu — das übernimmt das aufrufende Programm automatisch mit dem \
echten PDF-Link.
- Erfinde nie einen Link, Titel oder Fakt. Findest du zu einem Thema \
nichts Verlässliches, lass den Abschnitt weg oder kürze ihn auf einen \
Satz ohne Link.
- Dieselbe zugrundeliegende Story/denselben Artikel nicht in mehreren \
Abschnitten mehrfach zitieren.
{weekly_instruction}

Antworte NUR in exakt diesem Format, ohne zusätzliche Erklärungen davor \
oder danach:

TITLE: <kurzer, prägnanter Titel, max. 80 Zeichen>
---
> <Kurzfassung des gesamten Briefings in 2-3 Sätzen>

## <Eyebrow-Label, 1-3 Wörter>
### <Prägnante Schlagzeile>
<Fliesstext>
[<Medium>: <Artikeltitel>](<URL>)

(usw. für weitere Abschnitte — so viele wie es heute relevante Themen \
gibt, in Reihenfolge der Tagesrelevanz){weekly_section_format}

Regeln zum Format:
- Der Blockquote (Kurzfassung) kommt genau einmal, direkt nach der \
TITLE-Zeile.
- Jeder Abschnitt beginnt mit "## " (Eyebrow) gefolgt von "### " \
(Headline).
- Der Link (falls vorhanden) ist die letzte Zeile des Abschnitts.
- Kein H1, keine weitere Formatierung ausserhalb der oben gezeigten \
Struktur.
"""

WEEKLY_INSTRUCTION = """\
- Heute ist Sonntag: Füge nach den Tagesabschnitten einen zusätzlichen \
Abschnitt "## Wochenrückblick" hinzu (200–300 Wörter): fasse die \
wichtigsten Entwicklungen der vergangenen 7 Tage zusammen (Kontext der \
letzten Briefings wird dir unten gegeben) und schliesse mit einem \
kurzen Ausblick auf die kommende Woche."""

WEEKLY_SECTION_FORMAT = """

## Wochenrückblick
### <Schlagzeile für den Wochenrückblick>
<Fliesstext, 200-300 Wörter, endet mit einem kurzen Ausblick>"""


def build_system_prompt(is_weekly):
    return SYSTEM_PROMPT_TEMPLATE.format(
        weekly_instruction=WEEKLY_INSTRUCTION if is_weekly else "",
        weekly_section_format=WEEKLY_SECTION_FORMAT if is_weekly else "",
    )


def find_download_links(html, base_url):
    """Find candidate document links: plain `*.pdf` hrefs, and TYPO3's
    `eID=download&...` handler (this site's actual mechanism — a link like
    `index.php?eID=download&t=f&f=17902&token=...`, no `.pdf` in the URL at
    all). Returns (url, context_text) pairs, where context_text is the
    anchor tag plus a little surrounding HTML with tags stripped, used to
    sniff a date/label near the link since the eID URLs carry no filename.
    """
    pattern = re.compile(
        r'<a\b[^>]*href="([^"]+(?:\.pdf|eID=download[^"]*))"[^>]*>(.*?)</a>',
        re.I | re.S,
    )
    results = []
    seen = set()
    for m in pattern.finditer(html):
        href, inner = m.group(1), m.group(2)
        url = urljoin(base_url, href.replace("&amp;", "&"))
        if url in seen:
            continue
        seen.add(url)
        window = html[max(0, m.start() - 150):m.end() + 150]
        context = re.sub(r"<[^>]+>", " ", inner + " " + window)
        context = re.sub(r"\s+", " ", context).strip()
        results.append((url, context))
    return results


def extract_date(url, context_text):
    for source in (url.rsplit("/", 1)[-1], context_text):
        for pat in DATE_PATTERNS:
            m = pat.search(source)
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
    """`links` is a list of (url, context_text) pairs from find_download_links."""
    dated = [(extract_date(u, ctx), u) for u, ctx in links]
    dated = [d for d in dated if d[0] is not None]
    if dated:
        dated.sort(key=lambda d: d[0], reverse=True)
        return dated[0][1], "picked by date found in the link URL or its surrounding text"
    if links:
        return links[0][0], "no date found near any link; used the first document link in page order"
    return None, None


def fetch_pdf_text(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    reader = PdfReader(io.BytesIO(resp.content))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def load_index():
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return []


def load_recent_posts(before_date, days=WEEKLY_CONTEXT_DAYS):
    """Concatenated markdown of published posts strictly before `before_date`,
    within the last `days` days, oldest first — used as Wochenrückblick context.
    """
    posts = []
    for e in load_index():
        try:
            d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < before_date and (before_date - d).days <= days:
            path = POSTS_DIR / e["file"]
            if path.exists():
                posts.append((d, f"### {e['date']} — {e['title']}\n\n{path.read_text(encoding='utf-8')}"))
    posts.sort(key=lambda p: p[0])
    return "\n\n---\n\n".join(text for _, text in posts)


def summarize(pdf_text, is_weekly, weekly_context=""):
    client = anthropic.Anthropic()
    system_prompt = build_system_prompt(is_weekly)

    user_parts = [f"SFP SOUPE DU JOUR — PDF-Inhalt (Thema 5 der Prüfliste):\n\n{pdf_text}"]
    if is_weekly and weekly_context:
        user_parts.append(
            "KONTEXT FÜR WOCHENRÜCKBLICK — Briefings der letzten "
            f"{WEEKLY_CONTEXT_DAYS} Tage:\n\n" + weekly_context
        )

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system_prompt,
        output_config={"effort": "medium"},
        tools=[
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": 15,
                "allowed_domains": ALLOWED_NEWS_DOMAINS,
            }
        ],
        messages=[{"role": "user", "content": "\n\n---\n\n".join(user_parts)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")

    if not text.lstrip().startswith("TITLE:") or "---" not in text:
        raise ValueError("Unexpected model output shape:\n" + text[:500])

    title_line, _, body = text.partition("---")
    title = title_line.split("TITLE:", 1)[1].strip()
    return title, body.strip()


def split_sections(markdown):
    """Splits into (intro, [(eyebrow, section_block), ...]).

    `intro` is everything before the first "## " line (the blockquote /
    Kurzfassung). Each section_block is the full "## ..." chunk, including
    its own trailing newline, up to (not including) the next "## ".
    """
    parts = re.split(r"(?m)^## ", markdown)
    intro = parts[0].rstrip()
    sections = []
    for chunk in parts[1:]:
        eyebrow_line, _, _ = chunk.partition("\n")
        eyebrow = eyebrow_line.strip()
        block = "## " + chunk.rstrip() + "\n"
        sections.append((eyebrow, block))
    return intro, sections


def append_source_links(markdown, pdf_url):
    """Appends the deterministic "[📰 Quelle](pdf_url)" line to the SFP
    Soupe du Jour section only — always the real, known-good PDF URL,
    never something the model could get wrong or omit. Other sections
    carry whatever real research links the model found via web search.
    """
    intro, sections = split_sections(markdown)
    out = []
    for eyebrow, block in sections:
        low = eyebrow.lower()
        if "soupe" in low or low.strip() == "sfp":
            block = block.rstrip() + f"\n\n[📰 Quelle]({pdf_url})\n"
        out.append((eyebrow, block))
    body = intro + "\n\n" + "\n".join(block for _, block in out)
    return body.strip() + "\n"


def merge_markdown(existing_md, new_md):
    """Appends sections from new_md that aren't already present in
    existing_md (matched by eyebrow label, case-insensitive). Existing
    sections and the intro/Kurzfassung are left untouched. Returns
    (merged_markdown, [added_eyebrows]).
    """
    existing_intro, existing_sections = split_sections(existing_md)
    _, new_sections = split_sections(new_md)
    existing_keys = {e.lower() for e, _ in existing_sections}

    merged_sections = list(existing_sections)
    added = []
    for eyebrow, block in new_sections:
        if eyebrow.lower() in existing_keys:
            continue
        merged_sections.append((eyebrow, block))
        added.append(eyebrow)

    merged = existing_intro + "\n\n" + "\n".join(block for _, block in merged_sections)
    return merged.strip() + "\n", added


def save_index(entries):
    entries = sorted(entries, key=lambda e: e["date"], reverse=True)
    INDEX_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    mode = os.environ.get("BRIEFING_MODE", "full").strip().lower()
    today = datetime.now(TZ).date()
    is_weekly = today.weekday() == 6  # Monday=0 ... Sunday=6
    date_str = today.isoformat()
    filename = f"{date_str}.md"
    post_path = POSTS_DIR / filename

    print(f"Fetching {SOURCE_URL} ...")
    html = requests.get(SOURCE_URL, timeout=30).text
    links = find_download_links(html, SOURCE_URL)
    pdf_url, strategy = pick_newest_pdf(links)
    if not pdf_url:
        print("No PDF link found on the source page — aborting.", file=sys.stderr)
        sys.exit(1)
    print(f"Using PDF: {pdf_url} ({strategy})")

    text = fetch_pdf_text(pdf_url)
    if not text.strip():
        print("Extracted PDF text is empty — aborting.", file=sys.stderr)
        sys.exit(1)

    weekly_context = load_recent_posts(today) if is_weekly else ""
    if is_weekly:
        print(f"Sunday — building Wochenrückblick from {len(weekly_context)} chars of recent-post context.")

    title, body_md = summarize(text, is_weekly, weekly_context)
    body_md = append_source_links(body_md, pdf_url)

    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    if mode == "merge" and post_path.exists():
        existing_md = post_path.read_text(encoding="utf-8")
        merged_md, added = merge_markdown(existing_md, body_md)
        if not added:
            print("Merge mode: no new sections found — leaving existing file untouched.")
            return
        post_path.write_text(merged_md, encoding="utf-8")
        print(f"Merge mode: added {len(added)} new section(s) to {filename}: {', '.join(added)}")
        return

    post_path.write_text(body_md, encoding="utf-8")

    entries = [e for e in load_index() if e["date"] != date_str]
    entries.append(
        {"date": date_str, "title": title, "file": filename, "weekly": is_weekly}
    )
    save_index(entries)

    print(f"Wrote {filename} — \"{title}\"")


if __name__ == "__main__":
    main()
