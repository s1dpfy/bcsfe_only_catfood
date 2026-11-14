import { adminOk, catalogFrom, fb, isOurs, json, KEYS_NODE, keyId, upsertRecord } from "./_member.js";

export async function onRequestGet({ request, env }) {
  if (!adminOk(request)) return json({ ok: false, error: "비밀번호가 다릅니다." }, 401);
  try {
    const shallow = await fb(env, "GET", KEYS_NODE, undefined, { shallow: "true" });
    const ids = Object.keys(shallow || {}).filter((id) => isOurs(id, { key: id }));
    const records = await Promise.all(ids.map((id) => fb(env, "GET", `${KEYS_NODE}/${id}`)));
    return json({ keys: catalogFrom(Object.fromEntries(ids.map((id, i) => [id, records[i]]))) });
  } catch (err) {
    return json({ ok: false, error: err.message || "불러오기 실패" }, 502);
  }
}

export async function onRequestPost({ request, env }) {
  let body = {};
  try { body = await request.json(); } catch {}
  if (!adminOk(request, body)) return json({ ok: false, error: "비밀번호가 다릅니다." }, 401);
  if (!Array.isArray(body.keys)) return json({ ok: false, error: "키 목록이 없습니다." }, 400);
  try {
    for (const item of body.keys) {
      const id = keyId(item && item.key);
      if (!id || !isOurs(id, item)) continue;
      await upsertRecord(env, { ...item, key: id, source: "nyanko-editor" });
    }
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: err.message || "저장 실패" }, 502);
  }
}
