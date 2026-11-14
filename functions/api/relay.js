const MAX_BODY = 20 * 1024 * 1024;
const DROP = new Set(["host", "content-length", "connection", "transfer-encoding", "origin", "referer"]);

function hostAllowed(host, path) {
  host = (host || "").toLowerCase().replace(/\.$/, "");
  path = (path || "").toLowerCase();
  if (host === "git.battlecatsmodding.org" || host === "gitlab.com") return true;
  if (host.endsWith(".ponosgames.com") || host.endsWith(".amazonaws.com")) return true;
  if (host === "storage.googleapis.com" || host.endsWith(".storage.googleapis.com")) {
    return host.includes("battlecats") || path.includes("battlecats");
  }
  return false;
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

export async function onRequestPost(context) {
  let payload;
  try {
    payload = await context.request.json();
  } catch (e) {
    return Response.json({ error: "요청 형식이 잘못되었습니다." }, { status: 400 });
  }
  const method = String(payload.method || "GET").toUpperCase();
  if (!["GET", "POST", "PUT", "HEAD"].includes(method)) {
    return Response.json({ error: "허용되지 않은 요청입니다." }, { status: 400 });
  }
  let url;
  try {
    url = new URL(payload.url || "");
  } catch (e) {
    return Response.json({ error: "허용되지 않은 주소입니다." }, { status: 400 });
  }
  if (url.protocol !== "https:" || !hostAllowed(url.hostname, url.pathname)) {
    return Response.json({ error: "허용되지 않은 주소입니다." }, { status: 400 });
  }
  const headers = new Headers();
  const raw = payload.headers || {};
  for (const [key, value] of Object.entries(raw)) {
    if (value == null || DROP.has(key.toLowerCase())) continue;
    headers.set(key, String(value));
  }
  let body;
  if (payload.body_b64 && method !== "GET" && method !== "HEAD") {
    const binary = atob(payload.body_b64);
    body = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) body[i] = binary.charCodeAt(i);
    if (body.length > MAX_BODY) {
      return Response.json({ error: "요청이 너무 큽니다." }, { status: 400 });
    }
  }
  let upstream;
  try {
    upstream = await fetch(url, { method, headers, body, redirect: "follow" });
  } catch (e) {
    return Response.json({ error: "게임 서버에 연결하지 못했습니다." }, { status: 502 });
  }
  const content = new Uint8Array(await upstream.arrayBuffer());
  if (content.length > MAX_BODY) {
    return Response.json({ error: "응답이 너무 큽니다." }, { status: 502 });
  }
  const outHeaders = {};
  upstream.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (["content-encoding", "transfer-encoding", "content-length", "connection"].includes(lower)) return;
    outHeaders[key] = value;
  });
  return Response.json({
    status: upstream.status,
    headers: outHeaders,
    body_b64: bytesToB64(content),
  });
}
