# Push notifications — one-time setup

This wires up iPhone push notifications with a settable delivery time,
using a small Cloudflare Worker as the only backend (free tier). Do this
once; after that, every code change deploys automatically.

## 1. Cloudflare account

If you don't have one: https://dash.cloudflare.com/sign-up (free, no
credit card needed for what we use here).

## 2. Create the KV namespace (stores your subscription + settings)

Dashboard → **Workers & Pages** → **KV** → **Create a namespace**.
Name it e.g. `immo-briefing-push-settings`. Copy the **Namespace ID** it
shows you.

Open `worker/wrangler.toml` in this repo and replace
`REPLACE_WITH_KV_NAMESPACE_ID` with that ID, then commit/push (or tell me
the ID and I'll do it).

## 3. Set up your workers.dev subdomain (first time only)

Dashboard → **Workers & Pages** → **Overview** → it'll prompt you to pick
a subdomain (e.g. `yourname`) if you don't have one yet. Your Worker will
then be reachable at:

```
https://immo-briefing-push.<your-subdomain>.workers.dev
```

Put that exact URL into `docs/index.html`, replacing the
`PUSH_WORKER_URL` placeholder near the top of the `<script>` block (or
tell me the subdomain and I'll do it).

## 4. Create an API token

Dashboard → your profile icon → **My Profile** → **API Tokens** →
**Create Token** → use the **"Edit Cloudflare Workers"** template →
create. Copy the token (shown once).

## 5. Note your Account ID

Dashboard → **Workers & Pages** → **Overview** → Account ID is shown in
the right sidebar.

## 6. Choose a passphrase

Pick any passphrase (this is what the Settings page in the PWA asks for
before it can read/write your push subscription — it's the "login" that
stops a stranger with your app's URL from touching your notification
settings). Not your Cloudflare password — a separate one, just for this.

## 7. Add repo secrets and variables

GitHub repo → **Settings → Secrets and variables → Actions**:

**Secrets** tab — add:
| Name | Value |
|---|---|
| `CLOUDFLARE_API_TOKEN` | the token from step 4 |
| `CLOUDFLARE_ACCOUNT_ID` | the ID from step 5 |
| `PUSH_AUTH_PASSPHRASE` | the passphrase from step 6 |
| `VAPID_PRIVATE_KEY` | see below — I generated this already |
| `VAPID_CLAIM_EMAIL` | optional, e.g. `mailto:you@example.com` (defaults to a placeholder if omitted) |

**Variables** tab — add:
| Name | Value |
|---|---|
| `PUSH_WORKER_URL` | the URL from step 3 |

The VAPID keypair (generated once, already used to fill in
`VAPID_PUBLIC_KEY` in `docs/index.html`):

```
VAPID_PUBLIC_KEY=BCJZ8K3cMvIF18RHXky2gQy0ZgbhG8kD101Fy0FAVV0hTodvNDeaNK6JD-GqsiP74qClL2h0S8LMVFwDpuFAT-U
VAPID_PRIVATE_KEY=hPWxMinDgnHo1kMVOxnhmLcG-A2OaI11V7BzH5HAX88
```

Only the private key needs to go into GitHub Secrets (as
`VAPID_PRIVATE_KEY`) — the public key is already committed in
`docs/index.html` since, unlike the private key, it's meant to be public.

## 8. Deploy

Push to `main` (any commit touching `worker/**` triggers
`.github/workflows/deploy-worker.yml`), or run it manually from the
**Actions** tab → **Deploy push worker** → **Run workflow**.

## 9. Turn it on

Open the PWA on your iPhone (must be installed via **Share → Add to Home
Screen** first — Web Push only works for installed PWAs on iOS) → **⋮ →
Settings** → enter your passphrase, pick a time, tap **Aktivieren /
Speichern**, allow notifications when prompted.

`.github/workflows/send-push.yml` polls every 15 minutes and sends once
your chosen time comes around, using today's already-published briefing
title.
