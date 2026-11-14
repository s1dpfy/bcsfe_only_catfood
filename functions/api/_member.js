export const ADMIN_PASSWORD = "0923";
export const HMAC_SECRET = "BCSFE-KR-MEMBER-0923";
export const PRICE_ONCE = 3000;
export const PRICE_FULL = 10000;
export const TYPE_ONCE = "once";
export const TYPE_FULL = "full";
export const KEYS_NODE = "keys";
const DEFAULT_DB = "https://battlecatscatfood-default-rtdb.asia-southeast1.firebasedatabase.app";
const DEFAULT_SECRET = "pf6BWIT74lJUp2MXkt1ieSKmzMJundrcfda85JjZ";

export function json(data, status = 200) {
  return Response.json(data, { status });
}

export function adminOk(request, body) {
  const password = request.headers.get("X-Admin-Password") || (body && body.password) || "";
  return password === ADMIN_PASSWORD;
}

function dbUrl(env) {
  return String((env && env.FIREBASE_DB_URL) || DEFAULT_DB).replace(/\/$/, "");
}

function dbSecret(env) {
  return String((env && env.FIREBASE_DB_SECRET) || DEFAULT_SECRET);
}

export function keyId(key) {
  return String(key || "").trim().toUpperCase().replace(/\./g, "_");
}

export async function fb(env, method, path, payload, query) {
  const params = new URLSearchParams({ auth: dbSecret(env), ...(query || {}) });
  const url = `${dbUrl(env)}/${String(path).replace(/^\/|\/$/g, "")}.json?${params}`;
  const res = await fetch(url, {
    method,
    headers: payload === undefined ? undefined : { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!res.ok) throw new Error("Firebase 저장에 실패했습니다.");
  return data;
}

export function isOurs(id, rec) {
  const key = String(id || "");
  const recKey = String((rec && rec.key) || "");
  return key.startsWith("BCSK-") || recKey.startsWith("BCSK-") || !!(rec && rec.source === "nyanko-editor");
}

export function catalogFrom(data) {
  if (!data) return [];
  const items = [];
  if (Array.isArray(data)) {
    for (const item of data) {
      if (item && typeof item === "object" && isOurs(item.key, item)) items.push(item);
    }
    return items;
  }
  for (const [id, item] of Object.entries(data)) {
    if (item && typeof item === "object" && isOurs(id, item)) {
      items.push({ ...item, key: item.key || id });
    }
  }
  return items;
}

async function sha256hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sign(kind, raw) {
  const hex = await sha256hex(`${HMAC_SECRET}|${kind}|${raw}`);
  return hex.slice(0, 8).toUpperCase();
}

export async function makeKey(kind) {
  const bytes = crypto.getRandomValues(new Uint8Array(8));
  const raw = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("").toUpperCase();
  const prefix = kind === TYPE_ONCE ? "ONCE" : "FULL";
  const grouped = raw.match(/.{4}/g).join("-");
  return `BCSK-${prefix}-${grouped}-${await sign(kind, raw)}`;
}

export function parseKey(text) {
  const key = String(text || "").trim().toUpperCase().replace(/\s+/g, "");
  const parts = key.split("-");
  if (parts.length !== 7 || parts[0] !== "BCSK" || !["ONCE", "FULL"].includes(parts[1])) return null;
  return { key, kind: parts[1] === "ONCE" ? TYPE_ONCE : TYPE_FULL, raw: parts.slice(2, 6).join("") };
}

export async function validKey(text) {
  const parsed = parseKey(text);
  if (!parsed || parsed.raw.length !== 16) return null;
  if ((await sign(parsed.kind, parsed.raw)) !== parsed.key.split("-")[6]) return null;
  return parsed;
}

export async function findRecord(env, key) {
  const id = keyId(key);
  if (!id) return null;
  const data = await fb(env, "GET", `${KEYS_NODE}/${id}`);
  return data && typeof data === "object" ? data : null;
}

export async function upsertRecord(env, record) {
  const id = keyId(record.key);
  if (!id) throw new Error("invalid key");
  await fb(env, "PUT", `${KEYS_NODE}/${id}`, record);
  return record;
}

export async function createKey(env, kind, note = "") {
  const record = {
    id: crypto.randomUUID(),
    key: await makeKey(kind),
    type: kind,
    price: kind === TYPE_FULL ? PRICE_FULL : PRICE_ONCE,
    note,
    created_at: new Date().toISOString().slice(0, 19),
    used: false,
    revoked: false,
    bound_device: null,
    bound_at: null,
    source: "nyanko-editor",
  };
  await upsertRecord(env, record);
  return record;
}

export async function redeem(env, key, device) {
  const parsed = await validKey(key);
  if (!parsed) return { ok: false, message: "키가 올바르지 않습니다. 관리자가 발급한 키인지 확인하세요." };
  const me = String(device || "").trim();
  const rec = await findRecord(env, parsed.key);
  if (!rec) return { ok: false, message: "등록되지 않은 키입니다. 관리자에게 발급받은 키인지 확인하세요." };
  if (rec.revoked) return { ok: false, message: "취소된 키입니다." };
  const now = new Date().toISOString().slice(0, 19);
  if (parsed.kind === TYPE_ONCE) {
    if (rec.used) {
      if (rec.bound_device && rec.bound_device === me) {
        return { ok: true, message: "이미 이 기기에 등록된 키입니다." };
      }
      return { ok: false, message: "이미 사용된 1회권입니다." };
    }
    rec.used = true;
    rec.bound_device = me;
    rec.bound_at = now;
  } else {
    if (rec.bound_device && rec.bound_device !== me) {
      return { ok: false, message: "이 무제한 키는 다른 기기에 묶여 있습니다." };
    }
    rec.bound_device = me;
    rec.bound_at = now;
    rec.used = true;
  }
  await upsertRecord(env, rec);
  return {
    ok: true,
    message: parsed.kind === TYPE_FULL
      ? "고급회원(무제한)으로 등록했습니다. 이 기기에 발자국을 남겼습니다."
      : "고급회원 1회권이 이 기기에 등록되었습니다.",
  };
}
