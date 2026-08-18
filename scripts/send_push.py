#!/usr/bin/env python3
"""Sends a Web Push notification once per day, at the user's configured time.

Polled every 15 minutes by .github/workflows/send-push.yml. The Cloudflare
Worker (worker/) is this single-user app's tiny settings backend — it
holds the browser's push subscription, the preferred delivery time
("HH:MM", Europe/Zurich) and the date a push was last sent, all set from
the Settings page in the PWA.

Sends only when: a subscription + time are configured, the current
15-minute window contains the target time, today's briefing post already
exists, and nothing has been sent yet today (so overlapping/late polls
never double-send).

Run manually with:
  PUSH_WORKER_URL=... PUSH_AUTH_PASSPHRASE=... VAPID_PRIVATE_KEY=... \
  python scripts/send_push.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from pywebpush import WebPushException, webpush

TZ = ZoneInfo("Europe/Zurich")
REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO_ROOT / "docs" / "posts" / "index.json"
POLL_WINDOW_MINUTES = 15


def worker_request(method, path, **kwargs):
    worker_url = os.environ["PUSH_WORKER_URL"].rstrip("/")
    passphrase = os.environ["PUSH_AUTH_PASSPHRASE"]
    resp = requests.request(
        method,
        worker_url + path,
        headers={"Authorization": f"Bearer {passphrase}"},
        timeout=15,
        **kwargs,
    )
    resp.raise_for_status()
    return resp.json()


def parse_hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def main():
    settings = worker_request("GET", "/settings")
    subscription = settings.get("subscription")
    target_time = settings.get("time")
    last_sent = settings.get("lastSentDate")

    if not subscription or not target_time:
        print("No push subscription/time configured — nothing to do.")
        return

    now = datetime.now(TZ)
    today_str = now.date().isoformat()

    if last_sent == today_str:
        print("Already sent today — nothing to do.")
        return

    window_start = (now.hour * 60 + now.minute) // POLL_WINDOW_MINUTES * POLL_WINDOW_MINUTES
    target_minute = parse_hhmm(target_time)
    if not (window_start <= target_minute < window_start + POLL_WINDOW_MINUTES):
        print(f"Not yet time (target {target_time}, now {now.strftime('%H:%M')}).")
        return

    if not INDEX_PATH.exists():
        print("No posts/index.json yet — nothing to do.")
        return

    entries = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    today_entry = next((e for e in entries if e["date"] == today_str), None)
    if not today_entry:
        print(f"No post for {today_str} yet — will retry next window.")
        return

    payload = json.dumps(
        {
            "title": "Morgenbriefing",
            "body": today_entry["title"],
            "url": "/",
        }
    )

    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": os.environ.get("VAPID_CLAIM_EMAIL", "mailto:push@example.com")},
        )
    except WebPushException as e:
        print(f"Push failed: {e}", file=sys.stderr)
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            print("Subscription is gone (404/410) — clearing it so Settings shows disabled.")
            worker_request("POST", "/unsubscribe")
        sys.exit(1)

    worker_request("POST", "/mark-sent", json={"date": today_str})
    print(f"Sent push for {today_str}: {today_entry['title']}")


if __name__ == "__main__":
    main()
