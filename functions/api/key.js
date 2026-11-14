import { TYPE_FULL, TYPE_ONCE, adminOk, createKey, json } from "./_member.js";

export async function onRequestPost({ request, env }) {
  let body = {};
  try { body = await request.json(); } catch {}
  if (!adminOk(request, body)) return json({ ok: false, error: "비밀번호가 다릅니다." }, 401);
  const kind = String(body.type || body.kind || "");
  const note = String(body.note || "");
  const count = Math.max(1, Math.min(Number(body.count || 1), 50));
  if (kind !== TYPE_ONCE && kind !== TYPE_FULL) {
    return json({ ok: false, error: "종류가 올바르지 않습니다." }, 400);
  }
  try {
    const keys = [];
    for (let i = 0; i < count; i++) keys.push(await createKey(env, kind, note));
    return json({ ok: true, keys });
  } catch (err) {
    return json({ ok: false, error: err.message || "발급 실패" }, 502);
  }
}
