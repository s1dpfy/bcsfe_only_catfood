import { adminOk, findRecord, json, upsertRecord } from "./_member.js";

export async function onRequestPost({ request, env }) {
  let body = {};
  try { body = await request.json(); } catch {}
  if (!adminOk(request, body)) return json({ ok: false, error: "비밀번호가 다릅니다." }, 401);
  try {
    const rec = await findRecord(env, String(body.key || ""));
    if (!rec) return json({ ok: false });
    rec.revoked = true;
    await upsertRecord(env, rec);
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: err.message || "취소 실패" }, 502);
  }
}
