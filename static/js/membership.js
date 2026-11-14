import { OPENCHAT_URL } from "./config.js";
import { redeemRemote } from "./fbkeys.js";

const SECRET = "BCSFE-KR-MEMBER-0923";
const DEVICE_KEY = "bcsfe_device_id";
const BINDS_KEY = "bcsfe_unlimited_binds";
const USED_KEY = "bcsfe_used_once";
const PREMIUM_KEY = "bcsfe_premium";
const GAME_LIMITS = {
  catfood: 1000000,
  xp: 100000000,
  normal: 999,
  legend: 999,
  platinum: 999,
  catfruit: 998,
  np: 9999,
  catseyes: 999,
};
const FREE_LIMITS = { catfood: 30000, xp: 10000000, normal: 20 };

export { OPENCHAT_URL, GAME_LIMITS };

export function deviceId() {
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    const bytes = crypto.getRandomValues(new Uint8Array(8));
    id = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

function loadBinds() {
  try {
    return JSON.parse(localStorage.getItem(BINDS_KEY) || "{}");
  } catch {
    return {};
  }
}

function loadUsed() {
  try {
    const raw = JSON.parse(localStorage.getItem(USED_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

async function sha256hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sign(kind, raw) {
  const hex = await sha256hex(`${SECRET}|${kind}|${raw}`);
  return hex.slice(0, 8).toUpperCase();
}

function parseKey(text) {
  const key = (text || "").trim().toUpperCase().replace(/\s+/g, "");
  const parts = key.split("-");
  if (parts.length !== 7 || parts[0] !== "BCSK" || !["ONCE", "FULL"].includes(parts[1])) return null;
  return { key, kind: parts[1] === "ONCE" ? "once" : "full", raw: parts.slice(2, 6).join("") };
}

async function validKey(text) {
  const parsed = parseKey(text);
  if (!parsed || parsed.raw.length !== 16) return null;
  const sig = await sign(parsed.kind, parsed.raw);
  if (sig !== parsed.key.split("-")[6]) return null;
  return parsed;
}

export function isPremium() {
  try {
    const prem = JSON.parse(localStorage.getItem(PREMIUM_KEY) || "null");
    if (!prem || !prem.key) return false;
    const me = deviceId();
    if (prem.device && prem.device !== me) return false;
    if (prem.type === "full") {
      const bind = loadBinds()[prem.key];
      if (bind && bind.device && bind.device !== me) return false;
    }
    return prem.type === "once" || prem.type === "full";
  } catch {
    return false;
  }
}

export function label() {
  if (!isPremium()) return "무료회원";
  try {
    const prem = JSON.parse(localStorage.getItem(PREMIUM_KEY) || "{}");
    return prem.type === "full" ? "고급회원 · 무제한" : "고급회원 · 1회권";
  } catch {
    return "고급회원";
  }
}

export function limitFor(attr) {
  if (isPremium()) return null;
  return FREE_LIMITS[attr];
}

export function limits() {
  const out = { ...GAME_LIMITS };
  if (!isPremium()) {
    out.catfood = FREE_LIMITS.catfood;
    out.xp = FREE_LIMITS.xp;
    out.normal = FREE_LIMITS.normal;
  }
  return out;
}

function leaveFootprint(key) {
  const me = deviceId();
  const binds = loadBinds();
  const rec = binds[key];
  if (rec && rec.device && rec.device !== me) {
    return { ok: false, message: "이 무제한 키는 다른 기기에 묶여 있습니다." };
  }
  binds[key] = { device: me, at: new Date().toISOString() };
  localStorage.setItem(BINDS_KEY, JSON.stringify(binds));
  localStorage.setItem(PREMIUM_KEY, JSON.stringify({ key, device: me, type: "full" }));
  return { ok: true };
}

export async function redeemKey(text) {
  const parsed = parseKey(text);
  if (!parsed) return { ok: false, message: "키가 올바르지 않습니다." };
  const me = deviceId();
  try {
    const data = await redeemRemote(parsed.key, me);
    if (!data.ok) return { ok: false, message: data.message || "등록에 실패했습니다." };
    localStorage.setItem(PREMIUM_KEY, JSON.stringify({
      key: parsed.key,
      device: me,
      type: parsed.kind === "full" ? "full" : "once",
    }));
    if (parsed.kind === "full") {
      const binds = loadBinds();
      binds[parsed.key] = { device: me, at: new Date().toISOString() };
      localStorage.setItem(BINDS_KEY, JSON.stringify(binds));
    } else {
      const used = loadUsed();
      if (!used.includes(parsed.key)) {
        used.push(parsed.key);
        localStorage.setItem(USED_KEY, JSON.stringify(used));
      }
    }
    return { ok: true, message: data.message };
  } catch {
    return { ok: false, message: "Firebase에 연결하지 못했습니다. 잠시 후 다시 시도하세요." };
  }
}

export function buyUrl() {
  return OPENCHAT_URL;
}
