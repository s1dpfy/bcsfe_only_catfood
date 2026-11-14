import { TYPE_FULL, findRecord, json, parseKey, upsertRecord } from "./_member.js";

export async function onRequestPost({ request, env }) {
  let body = {};
  try { body = await request.json(); } catch {}
  const key = String(body.key || "").trim().toUpperCase();
  const device = String(body.device || "");
  const parsed = parseKey(key);
  if (!parsed || parsed.kind !== TYPE_FULL) {
    return json({ ok: false, error: "무제한 키가 아닙니다." }, 400);
  }
  try {
    const rec = await findRecord(env, key);
    if (!rec) return json({ ok: false, error: "등록되지 않은 키입니다." }, 404);
    if (rec.bound_device && rec.bound_device !== device) {
      return json({ ok: false, error: "이 무제한 키는 다른 기기에 묶여 있습니다." }, 409);
    }
    rec.bound_device = device;
    rec.used = true;
    await upsertRecord(env, rec);
    return json({ ok: true, device_id: device });
  } catch (err) {
    return json({ ok: false, error: err.message || "묶기 실패" }, 502);
  }
}
