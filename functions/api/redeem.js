import { json, redeem } from "./_member.js";

export async function onRequestPost({ request, env }) {
  let body = {};
  try { body = await request.json(); } catch {}
  try {
    const result = await redeem(env, String(body.key || ""), body.device || "");
    return json({ ...result, device_id: body.device || "" }, result.ok ? 200 : 400);
  } catch (err) {
    return json({ ok: false, message: err.message || "등록 실패" }, 502);
  }
}
