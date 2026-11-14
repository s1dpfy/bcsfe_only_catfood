export const FB_URL = "https://battlecatscatfood-default-rtdb.asia-southeast1.firebasedatabase.app";
const AUTH = "pf6BWIT74lJUp2MXkt1ieSKmzMJundrcfda85JjZ";

function fbUrl(path, query) {
  const clean = String(path || "").replace(/^\/+|\/+$/g, "");
  const params = new URLSearchParams({ auth: AUTH, ...(query || {}) });
  return `${FB_URL}/${clean}.json?${params}`;
}

export function isEditorKey(id, rec) {
  const key = String(id || "");
  const recKey = String((rec && rec.key) || "");
  return key.startsWith("BCSK-") || recKey.startsWith("BCSK-") || !!(rec && rec.source === "nyanko-editor");
}

export function recordId(rec) {
  return String((rec && (rec.key || rec.id)) || "").trim().toUpperCase();
}

export async function fbGet(path, query) {
  const res = await fetch(fbUrl(path, query));
  if (!res.ok) throw new Error("Firebase 읽기 실패");
  return res.json();
}

export async function fbPut(path, data) {
  const res = await fetch(fbUrl(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Firebase 저장 실패");
  return res.json();
}

export async function listEditorKeys() {
  const shallow = await fbGet("keys", { shallow: "true" });
  if (!shallow || typeof shallow !== "object") return [];
  const ids = Object.keys(shallow).filter((id) => isEditorKey(id, { key: id }));
  const recs = await Promise.all(ids.map((id) => getRecord(id)));
  const items = [];
  for (let i = 0; i < ids.length; i++) {
    const rec = recs[i];
    if (rec && typeof rec === "object") items.push({ ...rec, key: rec.key || ids[i] });
  }
  items.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  return items;
}

export async function getRecord(key) {
  const id = String(key || "").trim().toUpperCase();
  if (!id) return null;
  const rec = await fbGet(`keys/${id}`);
  return rec && typeof rec === "object" ? rec : null;
}

export async function saveRecord(rec) {
  const id = recordId(rec);
  if (!id) throw new Error("invalid key");
  const payload = { ...rec, key: id, source: "nyanko-editor" };
  await fbPut(`keys/${id}`, payload);
  return payload;
}

export async function redeemRemote(key, device) {
  const id = String(key || "").trim().toUpperCase();
  const rec = await getRecord(id);
  if (!rec) return { ok: false, message: "등록되지 않은 키입니다. 관리자에게 발급받은 키인지 확인하세요." };
  if (rec.revoked) return { ok: false, message: "취소된 키입니다." };
  const kind = rec.type === "full" || String(rec.key || id).includes("-FULL-") ? "full" : "once";
  const me = String(device || "").trim();
  const now = new Date().toISOString().slice(0, 19);
  if (kind === "once") {
    if (rec.used) {
      if (rec.bound_device && rec.bound_device === me) {
        return { ok: true, message: "이미 이 기기에 등록된 키입니다.", type: "once", record: rec };
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
  rec.key = rec.key || id;
  rec.type = kind;
  await saveRecord(rec);
  return {
    ok: true,
    type: kind,
    record: rec,
    message: kind === "full"
      ? "고급회원(무제한)으로 등록했습니다. 이 기기에 발자국을 남겼습니다."
      : "고급회원 1회권이 이 기기에 등록되었습니다.",
  };
}
