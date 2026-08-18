// Tiny single-user settings backend for push notifications.
//
// Stores exactly one record (this app has one user) in a KV namespace:
// the browser's PushSubscription, the preferred delivery time ("HH:MM",
// Europe/Zurich), and the date a push was last sent (so the polling
// workflow doesn't double-send within the same day).
//
// Every request must carry `Authorization: Bearer <passphrase>` matching
// the AUTH_PASSPHRASE secret. This is deliberately simple — one shared
// passphrase, no accounts — appropriate for a single-user personal app;
// it exists to stop a stranger who finds the PWA's URL from being able
// to read/hijack the push subscription or delivery-time setting, not to
// protect anything else (the app's other secrets never leave GitHub
// Actions / this Worker's own secret store).

const SETTINGS_KEY = "settings";

function allowedOrigin(env) {
  return env.ALLOWED_ORIGIN || "https://pasquales-art.github.io";
}

function withCors(resp, env) {
  resp.headers.set("Access-Control-Allow-Origin", allowedOrigin(env));
  resp.headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  resp.headers.set("Access-Control-Allow-Headers", "Authorization, Content-Type");
  resp.headers.set("Vary", "Origin");
  return resp;
}

function json(env, data, status = 200) {
  return withCors(
    new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
    env
  );
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return result === 0;
}

function isAuthorized(request, env) {
  const auth = request.headers.get("Authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  return Boolean(env.AUTH_PASSPHRASE) && timingSafeEqual(token, env.AUTH_PASSPHRASE);
}

async function readSettings(env) {
  const raw = await env.SETTINGS.get(SETTINGS_KEY);
  return raw ? JSON.parse(raw) : { subscription: null, time: null, lastSentDate: null };
}

function isValidTime(t) {
  return typeof t === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(t);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return withCors(new Response(null, { status: 204 }), env);
    }

    if (!isAuthorized(request, env)) {
      return json(env, { error: "unauthorized" }, 401);
    }

    if (url.pathname === "/settings" && request.method === "GET") {
      return json(env, await readSettings(env));
    }

    if (url.pathname === "/subscribe" && request.method === "POST") {
      let body;
      try {
        body = await request.json();
      } catch (e) {
        return json(env, { error: "invalid JSON body" }, 400);
      }
      if (!body || !body.subscription || !isValidTime(body.time)) {
        return json(env, { error: "subscription and time (HH:MM) are required" }, 400);
      }
      const existing = await readSettings(env);
      const next = {
        subscription: body.subscription,
        time: body.time,
        lastSentDate: existing.lastSentDate || null,
      };
      await env.SETTINGS.put(SETTINGS_KEY, JSON.stringify(next));
      return json(env, { ok: true });
    }

    if (url.pathname === "/unsubscribe" && request.method === "POST") {
      await env.SETTINGS.delete(SETTINGS_KEY);
      return json(env, { ok: true });
    }

    if (url.pathname === "/mark-sent" && request.method === "POST") {
      let body;
      try {
        body = await request.json();
      } catch (e) {
        return json(env, { error: "invalid JSON body" }, 400);
      }
      if (!body || typeof body.date !== "string") {
        return json(env, { error: "date is required" }, 400);
      }
      const existing = await readSettings(env);
      existing.lastSentDate = body.date;
      await env.SETTINGS.put(SETTINGS_KEY, JSON.stringify(existing));
      return json(env, { ok: true });
    }

    return json(env, { error: "not found" }, 404);
  },
};
