from typing import Optional
from fastapi import FastAPI, Request, Form, Header, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import secrets
import time
import asyncio
import os
import random
import json
import re
import hmac
import hashlib
from bcsfe_service import BCSFEService, ensure_game_data
import firebase_admin
from firebase_admin import credentials, db

FIREBASE_DB_URL = "https://battlecatscatfood-default-rtdb.asia-southeast1.firebasedatabase.app"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
candidate_paths = [
    "/etc/secrets/firebase-adminsdk.json",
    os.path.join(BASE_DIR, "firebase-adminsdk.json"),
    "firebase-adminsdk.json"
]

target_file = next((p for p in candidate_paths if os.path.exists(p)), None)

if target_file and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(target_file)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
        print(f"✅ Firebase Realtime Database 연동 완료! (경로: {target_file})")
    except Exception as e:
        print(f"❌ Firebase 초기화 오류: {e}")

SESSIONS = {}
UPLOAD_RESULTS = {}
SESSION_TIMEOUT = 300
RESULT_TTL = 600
MAX_SESSIONS = 24
LOCK_STATE = {"locked": False}
ADMIN_PASSWORD = "110923"
HEAVY = asyncio.Semaphore(3)
GAME_TIMEOUT = 40
DB_TIMEOUT = 8
_KEY_RE = re.compile(r"^[0-9A-F]{6}$")

class CachedStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=86400"
        return response

def _drop_session(token):
    data = SESSIONS.pop(token, None)
    if data is not None:
        data.pop("service", None)

def _store_upload(token, payload):
    if token:
        UPLOAD_RESULTS[token] = (time.time(), payload)

def _stored_upload(token):
    item = UPLOAD_RESULTS.get(token)
    if not item:
        return None
    saved_at, payload = item
    if time.time() - saved_at > RESULT_TTL:
        UPLOAD_RESULTS.pop(token, None)
        return None
    return payload

def _evict_sessions(now=None):
    now = time.time() if now is None else now
    expired = [tok for tok, data in SESSIONS.items() if now - data["last_active"] > SESSION_TIMEOUT]
    for tok in expired:
        _drop_session(tok)
    while len(SESSIONS) > MAX_SESSIONS:
        oldest = min(SESSIONS, key=lambda tok: SESSIONS[tok]["last_active"])
        _drop_session(oldest)
    stale = [tok for tok, (saved_at, _) in UPLOAD_RESULTS.items() if now - saved_at > RESULT_TTL]
    for tok in stale:
        UPLOAD_RESULTS.pop(tok, None)

async def session_cleanup_task():
    while True:
        await asyncio.sleep(30)
        _evict_sessions()

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="work")
    loop.set_default_executor(pool)
    try:
        ensure_game_data()
        print("✅ BCSFE 데이터 사전 로드 완료")
    except Exception as e:
        print(f"⚠️ 데이터 사전 로드 실패: {e}")
    task = asyncio.create_task(session_cleanup_task())
    yield
    task.cancel()
    pool.shutdown(wait=False, cancel_futures=True)

app = FastAPI(title="Simple BCSFE Web", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=800)
app.mount("/static", CachedStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.cache_size = 50

def get_user_session(x_session_token: str = Header(None)) -> dict:
    if not x_session_token or x_session_token not in SESSIONS:
        raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다.")
    SESSIONS[x_session_token]["last_active"] = time.time()
    return SESSIONS[x_session_token]

def _page(request: Request, name: str, **ctx):
    response = templates.TemplateResponse(request=request, name=name, context=ctx)
    response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _page(request, "index.html")

@app.get("/goldmember", response_class=HTMLResponse)
async def gold_member(request: Request):
    return _page(request, "goldmember.html")

@app.get("/vipmember", response_class=HTMLResponse)
async def vip_member(request: Request):
    return _page(request, "vipmember.html")

@app.get("/editpage", response_class=HTMLResponse)
async def edit_guest(request: Request):
    return _page(request, "editpage.html", tier="guest")

@app.get("/editpage-gold", response_class=HTMLResponse)
async def edit_gold(request: Request):
    return _page(request, "editpage.html", tier="gold")

@app.get("/editpage-vip", response_class=HTMLResponse)
async def edit_vip(request: Request):
    return _page(request, "editpage.html", tier="vip")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return _page(request, "admin.html")

@app.get("/api/lock_status")
def lock_status():
    return {"locked": LOCK_STATE["locked"]}

@app.post("/api/admin_login")
def admin_login(admin_password: str = Form(...)):
    if not _password_ok(admin_password):
        return {"success": False, "error": "관리자 권한이 없습니다."}
    response = JSONResponse({"success": True})
    response.set_cookie("admin_session", _admin_token(), httponly=True, samesite="lax", max_age=60 * 60 * 12, path="/")
    return response

@app.post("/api/toggle_lock")
def toggle_lock(request: Request, locked: bool = Form(...)):
    if not _admin_ok(request):
        return {"success": False, "error": "권한 없음"}
    LOCK_STATE["locked"] = locked
    return {"success": True, "locked": LOCK_STATE["locked"]}

def _password_ok(given):
    given = given or ""
    if len(given) != len(ADMIN_PASSWORD):
        return False
    return hmac.compare_digest(given, ADMIN_PASSWORD)

def _admin_token():
    return hmac.new(ADMIN_PASSWORD.encode(), b"nyansly-admin", hashlib.sha256).hexdigest()

def _admin_ok(request: Request) -> bool:
    cookie = request.cookies.get("admin_session", "")
    token = _admin_token()
    if len(cookie) != len(token):
        return False
    return hmac.compare_digest(cookie, token)

def _public_error(exc):
    print(f"server error: {exc}")
    return "서버 통신에 실패했습니다."

def _firebase_ready():
    return bool(firebase_admin._apps)

def _db_set(path, data):
    db.reference(path).set(data)

def _db_get(path):
    return db.reference(path).get()

def _db_delete(path):
    db.reference(path).delete()

async def _db_call(fn, *args):
    if not _firebase_ready():
        raise RuntimeError("Firebase가 연결되지 않았습니다.")
    return await asyncio.wait_for(asyncio.to_thread(fn, *args), DB_TIMEOUT)

async def _heavy(fn, *args, timeout=GAME_TIMEOUT):
    try:
        await asyncio.wait_for(HEAVY.acquire(), 5)
    except asyncio.TimeoutError:
        raise TimeoutError("서버가 바쁩니다. 잠시 후 다시 시도하세요.")
    try:
        return await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout)
    except TimeoutError:
        raise TimeoutError("서버 응답이 지연되고 있습니다.")
    finally:
        HEAVY.release()

def _clean_key(vip_key):
    key = (vip_key or "").strip().upper()
    return key if _KEY_RE.fullmatch(key) else ""

def _clip(value, limit=64):
    value = (value or "").strip()
    return value[:limit]

SITE = "https://catfood.sldpfy.me"
ROBOTS_TXT = f"User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: {SITE}/sitemap.xml\n"
SITEMAP_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    f"<url><loc>{SITE}/</loc><changefreq>weekly</changefreq></url>"
    "</urlset>"
)

CAPS = {
    "guest": {"catfood": 25000, "xp": 20000000, "normal": 15},
    "gold": {"catfood": 100000, "xp": 100000000, "normal": 200, "legend": 5, "platinum": 5, "catfruit": 20, "np": 1500, "catseyes": 20},
    "vip": {"catfood": 1000000, "xp": 100000000, "normal": 999, "legend": 999, "platinum": 999, "catfruit": 998, "np": 9999, "catseyes": 999},
}
def _tier_name(tier):
    return "vip" if tier == "catmaster" else tier

def _bad_amount(**vals):
    for value in vals.values():
        if value is None:
            continue
        if isinstance(value, list):
            if any(n < 0 for n in value):
                return True
        elif value < 0:
            return True
    return False

def _over_cap(tier, **vals):
    caps = CAPS.get(_tier_name(tier), CAPS["guest"])
    for key, value in vals.items():
        if value is None:
            continue
        limit = caps.get(key, 0)
        if isinstance(value, list):
            if any(n > limit for n in value):
                return True
        elif value > limit:
            return True
    return False

class _KeyRejected(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

def _sync_resolve_key(vip_key, device_id, requested_tier):
    found = {}

    def update(current):
        if not isinstance(current, dict) or current.get("is_active") is not True:
            raise _KeyRejected("유효하지 않거나 이미 사용된 키입니다.")
        if current.get("key_type") != "one_time":
            expires_at = current.get("expires_at") or 0
            if expires_at and int(time.time()) > int(expires_at):
                raise _KeyRejected("기간이 만료된 키입니다.")
        tier = _tier_name(current.get("tier", "vip"))
        if requested_tier in ("gold", "vip") and tier != requested_tier:
            label = "골드" if requested_tier == "gold" else "VIP"
            raise _KeyRejected(f"{label} 키만 입력할 수 있습니다.")
        if not device_id:
            raise _KeyRejected("기기를 확인할 수 없습니다.")
        bound = current.get("bound_device_id") or ""
        if bound and bound != device_id:
            raise _KeyRejected("이 키는 다른 기기에 등록되어 있습니다.")
        found["tier"] = tier
        if bound == device_id:
            return current
        nxt = dict(current)
        nxt["bound_device_id"] = device_id
        return nxt

    try:
        db.reference(f"keys/{vip_key}").transaction(update)
    except _KeyRejected as exc:
        return None, exc.message
    return found.get("tier"), None

def _claim_one_time(vip_key, nonce):
    def update(current):
        if not isinstance(current, dict):
            raise _KeyRejected("missing")
        if current.get("key_type") != "one_time":
            return current
        if current.get("is_active") is not True:
            return current
        nxt = dict(current)
        nxt["is_active"] = False
        nxt["claim_nonce"] = nonce
        return nxt

    try:
        result = db.reference(f"keys/{vip_key}").transaction(update)
    except _KeyRejected:
        return "used"
    if not isinstance(result, dict) or result.get("key_type") != "one_time":
        return "skip"
    if result.get("claim_nonce") == nonce:
        return "claimed"
    return "used"

def _restore_one_time(vip_key, nonce):
    def update(current):
        if not isinstance(current, dict) or current.get("claim_nonce") != nonce:
            return current
        nxt = dict(current)
        nxt["is_active"] = True
        nxt.pop("claim_nonce", None)
        return nxt

    db.reference(f"keys/{vip_key}").transaction(update)

async def _resolve_key(vip_key, device_id, requested_tier):
    vip_key = _clean_key(vip_key)
    device_id = _clip(device_id, 64)
    if not vip_key:
        return None, "유효하지 않거나 이미 사용된 키입니다."
    if vip_key == ADMIN_PASSWORD:
        tier = requested_tier if requested_tier in ("gold", "vip") else "vip"
        return tier, None
    return await _db_call(_sync_resolve_key, vip_key, device_id, requested_tier)

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return ROBOTS_TXT

@app.get("/sitemap.xml")
def sitemap_xml():
    return Response(SITEMAP_XML, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})

@app.post("/api/generate_key")
async def generate_key(request: Request, duration_type: str = Form(...), tier: str = Form(...)):
    if not _admin_ok(request):
        return {"success": False, "error": "권한 없음"}
    if tier not in ("gold", "vip"):
        return {"success": False, "error": "등급이 올바르지 않습니다."}
    try:
        current_time = int(time.time())
        if duration_type == "use_1":
            data = {"is_active": True, "created_at": current_time, "key_type": "one_time", "tier": tier, "bound_device_id": ""}
        else:
            try:
                days = int(duration_type)
            except ValueError:
                return {"success": False, "error": "기간이 올바르지 않습니다."}
            if days < 1:
                return {"success": False, "error": "기간이 올바르지 않습니다."}
            expires_at = 0 if days == 999 else current_time + (days * 86400)
            data = {"is_active": True, "created_at": current_time, "expires_at": expires_at, "key_type": "period", "tier": tier, "bound_device_id": ""}
        new_vip_key = ""
        for _ in range(5):
            candidate = "".join(random.choices("0123456789ABCDEF", k=6))
            if not await _db_call(_db_get, f"keys/{candidate}"):
                new_vip_key = candidate
                break
        if not new_vip_key:
            return {"success": False, "error": "키 발급에 실패했습니다. 다시 시도하세요."}
        await _db_call(_db_set, f"keys/{new_vip_key}", data)
        return {"success": True, "key": new_vip_key}
    except Exception as e:
        return {"success": False, "error": _public_error(e)}

@app.post("/api/list_keys")
async def list_keys(request: Request):
    if not _admin_ok(request):
        return {"success": False, "error": "권한 없음"}
    try:
        keys = await _db_call(_db_get, "keys")
        return {"success": True, "keys": keys or {}}
    except Exception as e:
        return {"success": False, "error": _public_error(e)}

@app.post("/api/delete_key")
async def delete_key(request: Request, vip_key: str = Form(...)):
    if not _admin_ok(request):
        return {"success": False, "error": "권한 없음"}
    try:
        vip_key = _clean_key(vip_key)
        if not vip_key or vip_key == ADMIN_PASSWORD:
            return {"success": False, "error": "키가 올바르지 않습니다."}
        await _db_call(_db_delete, f"keys/{vip_key}")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": _public_error(e)}

@app.post("/api/reset_key_device")
async def reset_key_device(request: Request, vip_key: str = Form(...)):
    if not _admin_ok(request):
        return {"success": False, "error": "권한 없음"}
    try:
        vip_key = _clean_key(vip_key)
        if not vip_key or vip_key == ADMIN_PASSWORD:
            return {"success": False, "error": "키가 올바르지 않습니다."}
        await _db_call(_db_set, f"keys/{vip_key}/bound_device_id", "")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": _public_error(e)}

@app.post("/api/verify_key")
async def verify_key(vip_key: str = Form(...), device_id: str = Form(""), requested_tier: str = Form("vip")):
    try:
        tier, err = await _resolve_key(vip_key, device_id, requested_tier)
        return {"success": False, "error": err} if err else {"success": True, "tier": tier}
    except Exception:
        return {"success": False, "error": "인증 서버 통신 실패"}

def _load_editor(tc, cc):
    service = BCSFEService()
    if not service.download(tc, cc):
        return None
    return service, service.editor_view()

@app.post("/api/load_save")
async def load_save(transfer_code: str = Form(...), confirmation_code: str = Form(...),
                    membership_type: str = Form("guest"), vip_key: str = Form(None),
                    device_id: str = Form(""), requested_tier: str = Form("vip")):
    if LOCK_STATE["locked"]:
        return {"success": False, "error": "에디터가 잠금 상태입니다."}
    transfer_code = _clip(transfer_code, 32)
    confirmation_code = _clip(confirmation_code, 12)
    if not transfer_code or not confirmation_code:
        return {"success": False, "error": "이어하기 코드와 인증 번호를 입력하세요."}
    tier = "guest"
    stored_key = None
    if membership_type != "guest" and vip_key:
        stored_key = _clean_key(vip_key)
        try:
            tier, err = await _resolve_key(stored_key, device_id, requested_tier)
        except Exception as exc:
            return {"success": False, "error": _public_error(exc)}
        if err:
            return {"success": False, "error": err}
    try:
        loaded = await _heavy(_load_editor, transfer_code, confirmation_code)
    except TimeoutError as e:
        return {"success": False, "error": str(e)}
    except Exception:
        return {"success": False, "error": "서버 처리 오류"}
    if not loaded:
        return {"success": False, "error": "이어하기 코드 또는 인증 번호가 올바르지 않거나, 게임 버전이 맞지 않습니다."}
    service, current_data = loaded
    _evict_sessions()
    if len(SESSIONS) >= MAX_SESSIONS:
        _drop_session(min(SESSIONS, key=lambda tok: SESSIONS[tok]["last_active"]))
    token = secrets.token_hex(16)
    SESSIONS[token] = {"service": service, "last_active": time.time(), "tier": tier, "vip_key": stored_key, "busy": False}
    return {
        "success": True,
        "token": token,
        "catfood": current_data.get("catfood", 0),
        "xp": current_data.get("xp", 0),
        "normal_tickets": current_data.get("normal_tickets", 0),
        "legend_tickets": current_data.get("legend_tickets", 0),
        "platinum_tickets": current_data.get("platinum_tickets", 0),
        "catfruit": current_data.get("catfruit") or [],
        "catseyes": current_data.get("catseyes") or [],
        "np": current_data.get("np", 0),
    }

def _as_int_list(raw):
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) > 40:
        raise ValueError("bad list")
    return [int(v) for v in data]

def _process_upload(service, catfood, xp, normal, legend, platinum, catfruit, catfruit_each, np, catseyes, catseyes_each, tier):
    is_premium = tier in ("gold", "vip", "catmaster")
    if catfood is not None:
        service.set_catfood(catfood, is_premium)
    if xp is not None:
        service.set_xp(xp, is_premium)
    if normal is not None:
        service.set_normal_tickets(normal, is_premium)
    if is_premium:
        if legend is not None:
            service.set_legend_tickets(legend, is_premium)
        if platinum is not None:
            service.set_platinum_tickets(platinum, is_premium)
        if catfruit_each is not None:
            service.set_catfruit_values(catfruit_each, tier)
        elif catfruit is not None:
            service.set_catfruit_values(None, tier, fill=catfruit)
        if np is not None:
            service.set_np(np, is_premium, "vip" if tier == "catmaster" else tier)
        if catseyes_each is not None:
            service.set_catseye_values(catseyes_each, tier)
        elif catseyes is not None:
            service.set_catseye_values(None, tier, fill=catseyes)
    return service.upload()

@app.post("/api/modify_and_upload")
async def modify_and_upload(
    catfood: Optional[int] = Form(None),
    xp: Optional[int] = Form(None),
    normal_tickets: Optional[int] = Form(None),
    legend_tickets: Optional[int] = Form(None),
    platinum_tickets: Optional[int] = Form(None),
    catfruit: Optional[int] = Form(None),
    catfruit_each: Optional[str] = Form(None),
    np: Optional[int] = Form(None),
    catseyes: Optional[int] = Form(None),
    catseyes_each: Optional[str] = Form(None),
    x_session_token: str = Header(None),
):
    if LOCK_STATE["locked"]:
        return {"success": False, "error": "에디터가 잠금 상태입니다."}
    cached = _stored_upload(x_session_token)
    if cached:
        return cached
    session_data = get_user_session(x_session_token)
    if session_data.get("busy"):
        return {"success": False, "error": "이미 업로드 중입니다."}
    session_data["busy"] = True
    service = session_data["service"]
    tier = session_data.get("tier", "guest")
    vip_key = session_data.get("vip_key")
    try:
        fruit_list = _as_int_list(catfruit_each) if catfruit_each else None
        eye_list = _as_int_list(catseyes_each) if catseyes_each else None
    except Exception:
        session_data["busy"] = False
        return {"success": False, "error": "수량 형식이 잘못되었습니다."}
    amounts = dict(catfood=catfood, xp=xp, normal=normal_tickets, legend=legend_tickets, platinum=platinum_tickets, catfruit=fruit_list if fruit_list is not None else catfruit, np=np, catseyes=eye_list if eye_list is not None else catseyes)
    if _bad_amount(**amounts):
        session_data["busy"] = False
        return {"success": False, "error": "수량이 올바르지 않습니다."}
    if _over_cap(tier, **amounts):
        session_data["busy"] = False
        return {"success": False, "error": "등급 최대 한도를 넘었습니다."}
    nonce = None
    if tier in ("gold", "vip", "catmaster") and vip_key and vip_key != ADMIN_PASSWORD:
        nonce = secrets.token_hex(8)
        try:
            claim = await _db_call(_claim_one_time, vip_key, nonce)
        except Exception as exc:
            session_data["busy"] = False
            return {"success": False, "error": _public_error(exc)}
        if claim == "used":
            session_data["busy"] = False
            return {"success": False, "error": "이미 사용된 키입니다."}
        if claim != "claimed":
            nonce = None
    try:
        new_tc, new_cc = await _heavy(
            _process_upload, service, catfood, xp, normal_tickets, legend_tickets, platinum_tickets,
            catfruit, fruit_list, np, catseyes, eye_list, tier,
        )
        if not new_tc or not new_cc:
            raise RuntimeError("empty transfer codes")
    except Exception as exc:
        if nonce:
            try:
                await _db_call(_restore_one_time, vip_key, nonce)
            except Exception as restore_exc:
                print(f"key restore failed: {restore_exc}")
        if x_session_token in SESSIONS:
            SESSIONS[x_session_token]["busy"] = False
        if isinstance(exc, TimeoutError):
            _drop_session(x_session_token)
            return {"success": False, "error": "처리 시간이 초과되었습니다. 세이브를 다시 불러오세요."}
        return {"success": False, "error": "업로드에 실패했습니다. 다시 시도하세요."}
    payload = {"success": True, "transfer_code": new_tc, "confirmation_code": new_cc, "key_burned": nonce is not None}
    _store_upload(x_session_token, payload)
    _drop_session(x_session_token)
    return payload
