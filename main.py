from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
import asyncio
import base64
import os

import requests

app = FastAPI(title="Nyansly Editor")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE_DIR, "static")
SITE = "https://catfood.sldpfy.me"
MAX_BODY = 20 * 1024 * 1024
DROP_HEADERS = {
    "host",
    "content-length",
    "connection",
    "transfer-encoding",
    "origin",
    "referer",
}


def _host_allowed(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    if host in {"git.battlecatsmodding.org", "gitlab.com"}:
        return True
    return host.endswith(".ponosgames.com") or host.endswith(".amazonaws.com")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-cache"})


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n"


@app.get("/sitemap.xml")
def sitemap_xml():
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{SITE}/</loc><changefreq>weekly</changefreq></url>"
        "</urlset>"
    )
    return Response(body, media_type="application/xml")


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
    if parsed.scheme != "https" or not _host_allowed(parsed.hostname or ""):
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
        response = requests.request(
            method,
            url,
            headers=headers,
            data=None if method in {"GET", "HEAD"} else body,
            timeout=90,
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


app.mount("/", StaticFiles(directory=STATIC), name="static")
