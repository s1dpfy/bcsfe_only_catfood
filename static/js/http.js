const SKIP_HEADERS = new Set(["user-agent", "connection", "content-length", "host", "origin", "referer", "accept-encoding", "accept-enconding"]);
const GAME_CACHE = "nyanko-gamedata-v1";
const gameMem = new Map();

function isGameData(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === "git.battlecatsmodding.org"
      || host === "gitlab.com"
      || host === "storage.googleapis.com"
      || host.endsWith(".storage.googleapis.com");
  } catch (err) {
    return false;
  }
}

async function getGameCache(url) {
  if (gameMem.has(url)) return gameMem.get(url);
  try {
    const cache = await caches.open(GAME_CACHE);
    const hit = await cache.match(url);
    if (!hit) return null;
    const text = await hit.text();
    gameMem.set(url, text);
    return text;
  } catch (err) {
    return null;
  }
}

async function putGameCache(url, text) {
  gameMem.set(url, text);
  try {
    const cache = await caches.open(GAME_CACHE);
    await cache.put(url, new Response(text, { headers: { "content-type": "application/json" } }));
  } catch (err) {}
}

function bytesToB64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    const slice = bytes.subarray(i, i + chunk);
    for (let j = 0; j < slice.length; j++) binary += String.fromCharCode(slice[j]);
  }
  return btoa(binary);
}

function bytesFromB64(b64) {
  if (!b64) return new Uint8Array();
  const binary = atob(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

async function readHttpResult(res) {
  const bytes = new Uint8Array(await res.arrayBuffer());
  const headers = {};
  res.headers.forEach((value, key) => { headers[key] = value; });
  return JSON.stringify({ status: res.status, headers, body_b64: bytesToB64(bytes) });
}

function useRelay(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host.endsWith(".ponosgames.com")
      || host.endsWith(".amazonaws.com")
      || host === "storage.googleapis.com"
      || host.endsWith(".storage.googleapis.com")
      || host === "git.battlecatsmodding.org"
      || host === "gitlab.com";
  } catch (err) {
    return false;
  }
}

async function viaRelay(methodU, url, headers, bodyB64) {
  const relay = await fetch("/api/relay", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ method: methodU, url, headers, body_b64: bodyB64 || "" }),
  });
  const text = await relay.text();
  if (!relay.ok) {
    let msg = "게임 서버에 연결하지 못했습니다.";
    try {
      const parsed = JSON.parse(text);
      if (parsed.error) msg = parsed.error;
    } catch (parseErr) {}
    throw new Error(msg);
  }
  return text;
}

window.nyanslyHttpAsync = async (method, url, headersJson, bodyB64) => {
  const methodU = String(method || "GET").toUpperCase();
  const headers = JSON.parse(headersJson || "{}");
  const body = bodyB64 ? bytesFromB64(bodyB64) : null;
  const cacheable = methodU === "GET" && isGameData(url);
  if (cacheable) {
    const hit = await getGameCache(url);
    if (hit) return hit;
  }
  let text;
  if (useRelay(url)) {
    text = await viaRelay(methodU, url, headers, bodyB64);
  } else {
    try {
      const outbound = new Headers();
      for (const [key, value] of Object.entries(headers)) {
        if (value == null || SKIP_HEADERS.has(String(key).toLowerCase())) continue;
        try { outbound.set(key, String(value)); } catch (err) {}
      }
      const res = await fetch(url, {
        method: methodU,
        headers: outbound,
        body: methodU === "GET" || methodU === "HEAD" ? undefined : body,
        cache: cacheable ? "force-cache" : "no-store",
      });
      text = await readHttpResult(res);
    } catch (err) {
      text = await viaRelay(methodU, url, headers, bodyB64);
    }
  }
  if (cacheable && text) await putGameCache(url, text);
  return text;
};
