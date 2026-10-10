from typing import Optional
from fastapi import FastAPI, Request, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import secrets
import time
import asyncio
import os
import random
import json
import gc

from bcsfe_service import BCSFEService
import firebase_admin
from firebase_admin import credentials, db

# ==========================================
# 🔥 Firebase Admin SDK 초기화
# ==========================================
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
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
        print(f"✅ Firebase Realtime Database 연동 완료! (경로: {target_file})")
    except Exception as e:
        print(f"❌ Firebase 초기화 오류: {e}")

# ==========================================
# ⚙️ 초경량 세션 설정 (OOM 방지)
# ==========================================
SESSIONS = {}          
SESSION_TIMEOUT = 300  
LOCK_STATE = {"locked": False}
ADMIN_PASSWORD = "110923"  

async def session_cleanup_task():
    while True:
        await asyncio.sleep(30)  
        current_time = time.time()
        expired = [tok for tok, data in SESSIONS.items() if current_time - data["last_active"] > SESSION_TIMEOUT]
        for tok in expired:
            session_data = SESSIONS.pop(tok, None)
            if session_data:
                del session_data["service"]
                del session_data
        if expired:
            gc.collect()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 BCSFE 데이터(캐릭터 이름 등) 미리 로드
    try:
        from bcsfe import core
        core.core_data.init_data()
        print("✅ BCSFE 데이터 사전 로드 완료")
    except Exception as e:
        print(f"⚠️ 데이터 사전 로드 실패: {e}")
    task = asyncio.create_task(session_cleanup_task())
    yield
    task.cancel()

app = FastAPI(title="Simple BCSFE Web", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

def get_user_session(x_session_token: str = Header(None)) -> dict:
    if not x_session_token or x_session_token not in SESSIONS:
        raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다.")
    SESSIONS[x_session_token]["last_active"] = time.time()
    return SESSIONS[x_session_token]

# ==========================================
# 🌐 라우트 및 DB 헬퍼
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")

@app.get("/api/lock_status")
def lock_status(): return {"locked": LOCK_STATE["locked"]}

@app.post("/api/toggle_lock")
def toggle_lock(locked: bool = Form(...)):
    LOCK_STATE["locked"] = locked
    return {"success": True, "locked": LOCK_STATE["locked"]}

def _db_set(path, data): db.reference(path).set(data)
def _db_get(path): return db.reference(path).get()
def _db_delete(path): db.reference(path).delete()

SITE = "https://catfood.sldpfy.me"
CAPS = {
    "guest": {"catfood": 17000, "xp": 20000000, "normal": 15},
    "gold": {"catfood": 100000, "xp": 100000000, "normal": 200, "legend": 5, "platinum": 5, "catfruit": 20, "np": 1500, "catseyes": 20},
    "vip": {"catfood": 1000000, "xp": 100000000, "normal": 999, "legend": 999, "platinum": 999, "catfruit": 998, "np": 9999, "catseyes": 999},
}

def _tier_name(tier: str) -> str:
    return "vip" if tier == "catmaster" else tier

def _over_cap(tier: str, **vals) -> bool:
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

async def _resolve_key(vip_key: str, device_id: str, requested_tier: str):
    if vip_key == ADMIN_PASSWORD:
        tier = requested_tier if requested_tier in ("gold", "vip") else "vip"
        return tier, None
    key_data = await asyncio.to_thread(_db_get, f"keys/{vip_key}")
    if not key_data or key_data.get("is_active") is not True:
        return None, "유효하지 않거나 이미 사용된 키입니다."
    if key_data.get("key_type") != "one_time":
        expires_at = key_data.get("expires_at", 0)
        if expires_at and int(time.time()) > int(expires_at):
            return None, "기간이 만료된 키입니다."
    bound = key_data.get("bound_device_id") or ""
    if not bound:
        await asyncio.to_thread(_db_set, f"keys/{vip_key}/bound_device_id", device_id)
    elif bound != device_id:
        return None, "이 키는 다른 기기에 등록되어 있습니다."
    return _tier_name(key_data.get("tier", "vip")), None

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return f"User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: {SITE}/sitemap.xml\n"

@app.get("/sitemap.xml")
def sitemap_xml():
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'<url><loc>{SITE}/</loc><changefreq>weekly</changefreq></url>'
        "</urlset>"
    )
    return Response(body, media_type="application/xml")

# ==========================================
# 🔑 키 생성 API
# ==========================================
@app.post("/api/generate_key")
async def generate_key(admin_password: str = Form(...), duration_type: str = Form(...), tier: str = Form(...)):
    if admin_password != ADMIN_PASSWORD:
        return {"success": False, "error": "관리자 권한이 없습니다."}
    try:
        new_vip_key = ''.join(random.choices("0123456789ABCDEF", k=6))
        current_time = int(time.time())
        
        if duration_type == "use_1":
            data = {
                'is_active': True,
                'created_at': current_time,
                'key_type': 'one_time',
                'tier': tier,
                'bound_device_id': ""
            }
        else:
            days = int(duration_type)
            expires_at = 0 if days == 999 else current_time + (days * 86400)
            data = {
                'is_active': True,
                'created_at': current_time,
                'expires_at': expires_at,
                'key_type': 'period',
                'tier': tier,
                'bound_device_id': ""
            }
            
        await asyncio.to_thread(_db_set, f'keys/{new_vip_key}', data)
        return {"success": True, "key": new_vip_key}
    except Exception as e:
        return {"success": False, "error": f"Firebase 연동 실패: {str(e)}"}

@app.post("/api/list_keys")
async def list_keys(admin_password: str = Form(...)):
    if admin_password != ADMIN_PASSWORD: return {"success": False, "error": "권한 없음"}
    try:
        keys = await asyncio.to_thread(_db_get, 'keys')
        return {"success": True, "keys": keys or {}}
    except Exception as e: return {"success": False, "error": str(e)}

@app.post("/api/delete_key")
async def delete_key(admin_password: str = Form(...), vip_key: str = Form(...)):
    if admin_password != ADMIN_PASSWORD: return {"success": False, "error": "권한 없음"}
    try:
        await asyncio.to_thread(_db_delete, f'keys/{vip_key}')
        return {"success": True}
    except Exception as e: return {"success": False, "error": str(e)}

@app.post("/api/reset_key_device")
async def reset_key_device(admin_password: str = Form(...), vip_key: str = Form(...)):
    if admin_password != ADMIN_PASSWORD: return {"success": False, "error": "권한 없음"}
    try:
        await asyncio.to_thread(_db_set, f'keys/{vip_key}/bound_device_id', "")
        return {"success": True}
    except Exception as e: return {"success": False, "error": str(e)}

@app.post("/api/verify_key")
async def verify_key(vip_key: str = Form(...), device_id: str = Form(""), requested_tier: str = Form("vip")):
    try:
        tier, err = await _resolve_key(vip_key, device_id, requested_tier)
        return {"success": False, "error": err} if err else {"success": True, "tier": tier}
    except Exception:
        return {"success": False, "error": "인증 서버 통신 실패"}

# ==========================================
# 🐱 세이브 로드/모딩 API
# ==========================================
def _process_download(tc: str, cc: str):
    service = BCSFEService()
    return service if service.download(tc.strip(), cc.strip()) else None

@app.post("/api/load_save")
async def load_save(transfer_code: str = Form(...), confirmation_code: str = Form(...), 
                    membership_type: str = Form("guest"), vip_key: str = Form(None),
                    device_id: str = Form(""), requested_tier: str = Form("vip")):
    
    if LOCK_STATE["locked"]: return {"success": False, "error": "에디터가 잠금 상태입니다."}

    tier = "guest"
    if membership_type != "guest" and vip_key:
        try:
            tier, err = await _resolve_key(vip_key, device_id, requested_tier)
            if err:
                return {"success": False, "error": err}
        except Exception:
            return {"success": False, "error": "키 인증 서버 오류"}

    try:
        service = await asyncio.to_thread(_process_download, transfer_code, confirmation_code)
        if not service:
            return {"success": False, "error": "이어하기 코드 또는 인증 번호가 올바르지 않거나, 게임 버전이 맞지 않습니다."}

        token = secrets.token_hex(16)
        SESSIONS[token] = {"service": service, "last_active": time.time(), "tier": tier, "vip_key": vip_key}
        
        summary = await asyncio.to_thread(service.summary)
        current_data = summary.get("current", {})
        
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
    except Exception as e:
        return {"success": False, "error": f"서버 처리 오류: {str(e)}"}

def _as_int_list(raw):
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, list):
        return None
    return [int(v) for v in data]

def _process_upload(service, catfood, xp, normal, legend, platinum, catfruit, catfruit_each, np, catseyes, catseyes_each, tier: str):
    is_premium = tier in ["gold", "vip", "catmaster"]
    if catfood is not None: service.set_catfood(catfood, is_premium)
    if xp is not None: service.set_xp(xp, is_premium)
    if normal is not None: service.set_normal_tickets(normal, is_premium)
    if is_premium:
        if legend is not None: service.set_legend_tickets(legend, is_premium)
        if platinum is not None: service.set_platinum_tickets(platinum, is_premium)
        if catfruit_each is not None: service.set_catfruit_values(catfruit_each, tier)
        elif catfruit is not None: service.set_catfruit_values(None, tier, fill=catfruit)
        if np is not None: service.set_np(np, is_premium, "vip" if tier == "catmaster" else tier)
        if catseyes_each is not None: service.set_catseye_values(catseyes_each, tier)
        elif catseyes is not None: service.set_catseye_values(None, tier, fill=catseyes)
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
    x_session_token: str = Header(None)
):
    if LOCK_STATE["locked"]: return {"success": False, "error": "에디터가 잠금 상태입니다."}

    session_data = get_user_session(x_session_token)
    service = session_data["service"]
    tier = session_data.get("tier", "guest")
    vip_key = session_data.get("vip_key")
    try:
        fruit_list = _as_int_list(catfruit_each) if catfruit_each else None
        eye_list = _as_int_list(catseyes_each) if catseyes_each else None
    except Exception:
        return {"success": False, "error": "수량 형식이 잘못되었습니다."}
    if _over_cap(tier, catfood=catfood, xp=xp, normal=normal_tickets, legend=legend_tickets,
                 platinum=platinum_tickets, catfruit=fruit_list if fruit_list is not None else catfruit,
                 np=np, catseyes=eye_list if eye_list is not None else catseyes):
        return {"success": False, "error": "등급 최대 한도를 넘었습니다."}

    try:
        new_tc, new_cc = await asyncio.to_thread(
            _process_upload, service, catfood, xp, normal_tickets, legend_tickets,
            platinum_tickets, catfruit, fruit_list, np, catseyes, eye_list, tier
        )
        
        key_burned = False
        # 어드민 키는 소멸(Burn) 대상에서 제외[cite: 2]
        if tier in ["gold", "vip", "catmaster"] and vip_key and vip_key != ADMIN_PASSWORD:
            key_data = await asyncio.to_thread(_db_get, f'keys/{vip_key}')
            if key_data and key_data.get('key_type') == 'one_time':
                await asyncio.to_thread(_db_set, f'keys/{vip_key}/is_active', False)
                key_burned = True

        SESSIONS.pop(x_session_token, None)
        return {"success": True, "transfer_code": new_tc, "confirmation_code": new_cc, "key_burned": key_burned}
    except HTTPException as he: 
        return {"success": False, "error": he.detail}
    except Exception as e: 
        return {"success": False, "error": str(e)}