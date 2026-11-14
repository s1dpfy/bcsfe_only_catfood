from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
import asyncio
import base64
import os

import requests
from requests.adapters import HTTPAdapter

import membership as member

app = FastAPI(title="Nyansly Editor", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=400)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE_DIR, "static")
SITE = "https://catfood.sldpfy.me"
MAX_BODY = 20 * 1024 * 1024
CACHE_HTML = "no-cache"
CACHE_ASSET = "public, max-age=604800, stale-while-revalidate=86400"
NO_STORE = {"Cache-Control": "no-store"}
DROP_HEADERS = {
    "host",
    "content-length",
    "connection",
    "transfer-encoding",
    "origin",
    "referer",
}

_relay = requests.Session()
_relay.mount("https://", HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=1))


def _host_allowed(host: str, path: str = "") -> bool:
    host = (host or "").lower().rstrip(".")
    path = (path or "").lower()
    if host in {"git.battlecatsmodding.org", "gitlab.com"}:
        return True
    if host.endswith(".ponosgames.com") or host.endswith(".amazonaws.com"):
        return True
    if host == "storage.googleapis.com" or host.endswith(".storage.googleapis.com"):
        return "battlecats" in host or "battlecats" in path
    return False


@app.get("/")
def index():
    return FileResponse(
        os.path.join(STATIC, "index.html"),
        headers={"Cache-Control": CACHE_HTML, "X-Content-Type-Options": "nosniff"},
    )


@app.get("/admin")
@app.get("/admin/")
def admin_redirect():
    return RedirectResponse("/admin.html", status_code=302)


@app.get("/admin.html")
@app.get("/ADMIN.HTML")
@app.get("/ADMIN.html")
def admin_page():
    return FileResponse(
        os.path.join(STATIC, "admin.html"),
        headers={"Cache-Control": CACHE_HTML, "X-Content-Type-Options": "nosniff"},
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /admin.html\n"
        f"Sitemap: {SITE}/sitemap.xml\n"
    )


@app.get("/sitemap.xml")
def sitemap_xml():
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{SITE}/</loc><changefreq>weekly</changefreq></url>"
        "</urlset>"
    )
    return Response(body, media_type="application/xml")


def _admin_ok(request: Request, body: dict | None = None) -> bool:
    password = request.headers.get("X-Admin-Password", "")
    if password == member.ADMIN_PASSWORD:
        return True
    return str((body or {}).get("password", "")) == member.ADMIN_PASSWORD


@app.get("/api/ping")
def api_ping():
    return {"ok": True}


@app.get("/api/device")
def api_device():
    return {"device_id": member.device_id()}


def _store_error(err: Exception):
    return JSONResponse({"ok": False, "error": str(err) or "Firebase 오류"}, status_code=502)


@app.get("/api/keys")
async def api_keys(request: Request):
    if not _admin_ok(request):
        return JSONResponse({"ok": False, "error": "비밀번호가 다릅니다."}, status_code=401)
    try:
        return await asyncio.to_thread(member.load_catalog)
    except Exception as err:
        return _store_error(err)


@app.post("/api/keys")
async def api_keys_save(request: Request):
    body = await request.json()
    if not _admin_ok(request, body if isinstance(body, dict) else {}):
        return JSONResponse({"ok": False, "error": "비밀번호가 다릅니다."}, status_code=401)
    incoming = body.get("keys") if isinstance(body, dict) else None
    if not isinstance(incoming, list):
        return JSONResponse({"ok": False, "error": "키 목록이 없습니다."}, status_code=400)
    try:
        await asyncio.to_thread(member.save_catalog, {"keys": incoming})
        return {"ok": True}
    except Exception as err:
        return _store_error(err)


@app.post("/api/key")
async def api_key_create(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        body = {}
    if not _admin_ok(request, body):
        return JSONResponse({"ok": False, "error": "비밀번호가 다릅니다."}, status_code=401)
    kind = str(body.get("type") or body.get("kind") or "")
    note = str(body.get("note") or "")
    count = max(1, min(int(body.get("count") or 1), 50))
    if kind not in (member.TYPE_ONCE, member.TYPE_FULL):
        return JSONResponse({"ok": False, "error": "종류가 올바르지 않습니다."}, status_code=400)
    try:
        created = await asyncio.to_thread(
            lambda: [member.create_key(kind, note) for _ in range(count)]
        )
        return {"ok": True, "keys": created}
    except Exception as err:
        return _store_error(err)


@app.post("/api/revoke")
async def api_revoke(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        body = {}
    if not _admin_ok(request, body):
        return JSONResponse({"ok": False, "error": "비밀번호가 다릅니다."}, status_code=401)
    try:
        ok = await asyncio.to_thread(member.revoke, str(body.get("key", "")))
        return {"ok": ok}
    except Exception as err:
        return _store_error(err)


@app.post("/api/redeem")
async def api_redeem(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        body = {}
    try:
        ok, msg = await asyncio.to_thread(
            member.redeem, str(body.get("key", "")), body.get("device") or None
        )
    except Exception as err:
        return JSONResponse({"ok": False, "message": str(err) or "등록 실패"}, status_code=502, headers=NO_STORE)
    payload = {"ok": ok, "message": msg, "device_id": member.device_id()}
    return JSONResponse(payload, status_code=200 if ok else 400, headers=NO_STORE)


@app.post("/api/bind")
async def api_bind(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        body = {}
    key = str(body.get("key", "")).strip().upper()
    device = str(body.get("device") or member.device_id())
    parsed = member.parse_key(key)
    if parsed is None or parsed[0] != member.TYPE_FULL:
        return JSONResponse({"ok": False, "error": "무제한 키가 아닙니다."}, status_code=400)
    try:
        rec = await asyncio.to_thread(member.find_record, key)
    except Exception as err:
        return _store_error(err)
    if rec is None:
        return JSONResponse({"ok": False, "error": "등록되지 않은 키입니다."}, status_code=404)
    bound = rec.get("bound_device")
    if bound and bound != device:
        return JSONResponse(
            {"ok": False, "error": "이 무제한 키는 다른 기기에 묶여 있습니다."},
            status_code=409,
        )
    rec["bound_device"] = device
    rec["used"] = True
    try:
        await asyncio.to_thread(member.upsert_record, rec)
    except Exception as err:
        return _store_error(err)
    return {"ok": True, "device_id": device}


@app.post("/api/relay")
async def relay(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "요청 형식이 잘못되었습니다."}, status_code=400)
    url = str(payload.get("url") or "")
    method = str(payload.get("method") or "GET").upper()
    if method not in {"GET", "POST", "PUT", "HEAD"}:
        return JSONResponse({"error": "허용되지 않은 요청입니다."}, status_code=400)
    parsed = requests.utils.urlparse(url)
    if parsed.scheme != "https" or not _host_allowed(parsed.hostname or "", parsed.path or ""):
        return JSONResponse({"error": "허용되지 않은 주소입니다."}, status_code=400)
    raw_headers = payload.get("headers") or {}
    headers = {}
    if isinstance(raw_headers, dict):
        for key, value in raw_headers.items():
            if value is None or str(key).lower() in DROP_HEADERS:
                continue
            headers[str(key)] = str(value)
    body = b""
    body_b64 = payload.get("body_b64") or ""
    if body_b64:
        try:
            body = base64.b64decode(body_b64)
        except Exception:
            return JSONResponse({"error": "본문을 읽지 못했습니다."}, status_code=400)
        if len(body) > MAX_BODY:
            return JSONResponse({"error": "요청이 너무 큽니다."}, status_code=400)

    def do():
        response = _relay.request(
            method,
            url,
            headers=headers,
            data=None if method in {"GET", "HEAD"} else body,
            timeout=45,
        )
        kept = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in {"content-encoding", "transfer-encoding", "content-length", "connection"}
        }
        return response.status_code, kept, response.content

    try:
        status, resp_headers, content = await asyncio.to_thread(do)
    except Exception:
        return JSONResponse({"error": "게임 서버에 연결하지 못했습니다."}, status_code=502)
    if len(content) > MAX_BODY:
        return JSONResponse({"error": "응답이 너무 큽니다."}, status_code=502)
    return {
        "status": status,
        "headers": resp_headers,
        "body_b64": base64.b64encode(content).decode(),
    }


class SmartStatic(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if getattr(response, "status_code", 0) != 200:
            return response
        lower = str(path).lower()
        if lower.endswith(".html"):
            response.headers["Cache-Control"] = CACHE_HTML
        elif lower.endswith((".js", ".css", ".woff", ".woff2", ".py")):
            response.headers["Cache-Control"] = CACHE_ASSET
        else:
            response.headers["Cache-Control"] = "public, max-age=3600"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


app.mount("/", SmartStatic(directory=STATIC), name="static")
