from fastapi import FastAPI, Request, Form, Header, HTTPException, Response, Cookie
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import uvicorn
import secrets
import time
import asyncio
import os
import random

from bcsfe_service import BCSFEService

# ==========================================
# 🔥 Firebase Admin SDK 초기화
# ==========================================
import firebase_admin
from firebase_admin import credentials, db

import json
from dotenv import load_dotenv

load_dotenv()

FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")

if not FIREBASE_CREDENTIALS_JSON:
    raise RuntimeError("FIREBASE_CREDENTIALS_JSON 환경변수가 없습니다.")

if not FIREBASE_DB_URL:
    raise RuntimeError("FIREBASE_DB_URL 환경변수가 없습니다.")

try:
    if not firebase_admin._apps:
        firebase_config = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(firebase_config)

        firebase_admin.initialize_app(cred, {
            "databaseURL": FIREBASE_DB_URL
        })

        print("✅ Firebase Realtime Database 연동 완료!")

except Exception as e:
    print(f"❌ Firebase 초기화 중 오류 발생: {e}")
    raise
try:
    if not firebase_admin._apps:
        if os.path.exists(FIREBASE_CRED_PATH):
            cred = credentials.Certificate(FIREBASE_CRED_PATH)
            firebase_admin.initialize_app(cred, {
                'databaseURL': FIREBASE_DB_URL
            })
            print("✅ Firebase Realtime Database 연동 완료!")
        else:
            print(f"⚠️ 경고: 키 파일을 찾을 수 없습니다. 경로 확인 -> {FIREBASE_CRED_PATH}")
except Exception as e:
    print(f"❌ Firebase 초기화 중 오류 발생: {e}")

# ==========================================
# ⚙️ 세션 설정
# ==========================================
SESSIONS = {}          
SESSION_TIMEOUT = 300  

LOCK_STATE = {"locked": False}
ADMIN_PASSWORD = "110923"  

async def session_cleanup_task():
    while True:
        await asyncio.sleep(60)
        current_time = time.time()
        expired_tokens = [tok for tok, data in SESSIONS.items() if current_time - data["last_active"] > SESSION_TIMEOUT]
        for tok in expired_tokens:
            del SESSIONS[tok]

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(session_cleanup_task())
    yield
    task.cancel()

app = FastAPI(title="Simple BCSFE Web with Sessions", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

def get_user_session(x_session_token: str = Header(None)) -> dict:
    if not x_session_token or x_session_token not in SESSIONS:
        raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다.")
    SESSIONS[x_session_token]["last_active"] = time.time()
    return SESSIONS[x_session_token]

# ==========================================
# 🌐 페이지 라우트
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")

# ==========================================
# 🔒 관리자 잠금 API
# ==========================================
@app.get("/api/lock_status")
def lock_status():
    return {"locked": LOCK_STATE["locked"]}

@app.post("/api/toggle_lock")
def toggle_lock(locked: bool = Form(...)):
    LOCK_STATE["locked"] = locked
    return {"success": True, "locked": LOCK_STATE["locked"]}

# ==========================================
# 🔑 비동기 DB 헬퍼 함수
# ==========================================
def _db_set(path, data): db.reference(path).set(data)
def _db_get(path): return db.reference(path).get()
def _db_delete(path): db.reference(path).delete()

# ==========================================
# 🔑 VIP 키 관리 API
# ==========================================
@app.post("/api/generate_key")
async def generate_key(admin_password: str = Form(...), duration_days: int = Form(...)):
    if admin_password != ADMIN_PASSWORD:
        return {"success": False, "error": "관리자 권한이 없습니다."}
        
    try:
        new_vip_key = ''.join(random.choices("0123456789ABCDEF", k=6))
        current_time = int(time.time())
        expires_at = 0 if duration_days == 999 else current_time + (duration_days * 86400)
        
        data_to_save = {
            'is_active': True,
            'created_at': current_time,
            'expires_at': expires_at,
            'duration_type': duration_days,
            'bound_device_id': "" # 기기 식별자 초기화 (미귀속)
        }
        
        await asyncio.to_thread(_db_set, f'keys/{new_vip_key}', data_to_save)
        return {"success": True, "key": new_vip_key}
    except Exception as e:
        return {"success": False, "error": f"Firebase 연동 실패: {str(e)}"}

@app.post("/api/list_keys")
async def list_keys(admin_password: str = Form(...)):
    if admin_password != ADMIN_PASSWORD: return {"success": False, "error": "관리자 권한이 없습니다."}
    try:
        keys_data = await asyncio.to_thread(_db_get, 'keys')
        return {"success": True, "keys": keys_data or {}}
    except Exception as e: return {"success": False, "error": f"조회 실패: {str(e)}"}

@app.post("/api/delete_key")
async def delete_key(admin_password: str = Form(...), vip_key: str = Form(...)):
    if admin_password != ADMIN_PASSWORD: return {"success": False, "error": "관리자 권한이 없습니다."}
    try:
        await asyncio.to_thread(_db_delete, f'keys/{vip_key}')
        return {"success": True}
    except Exception as e: return {"success": False, "error": f"삭제 실패: {str(e)}"}

@app.post("/api/verify_key")
async def verify_key(vip_key: str = Form(...), device_id: str = Form("")):
    try:
        key_data = await asyncio.to_thread(_db_get, f'keys/{vip_key}')
        if not key_data or key_data.get('is_active') != True:
            return {"success": False, "error": "유효하지 않은 키입니다."}
            
        # 만료 검사
        expires_at = key_data.get('expires_at', 0)
        if expires_at != 0 and int(time.time()) > expires_at:
            return {"success": False, "error": "기간이 만료된 키입니다."}

        # 🛡️ 기기 지문 검증 및 귀속
        bound_device = key_data.get('bound_device_id', '')
        if not bound_device:
            # 첫 기기 등록
            await asyncio.to_thread(_db_set, f'keys/{vip_key}/bound_device_id', device_id)
        elif bound_device != device_id:
            return {"success": False, "error": "이 VIP 키는 이미 다른 기기에 등록되어 있습니다. (기기 공유 불가)"}

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": "인증 서버 통신 실패"}

# ==========================================
# 🐱 세이브 로드/모딩 API
# ==========================================
def _process_download(tc, cc):
    service = BCSFEService()
    if service.download(tc.strip(), cc.strip()):
        return service
    return None

@app.post("/api/load_save")
async def load_save(transfer_code: str = Form(...), confirmation_code: str = Form(...), 
                    membership_type: str = Form("guest"), vip_key: str = Form(None),
                    device_id: str = Form("")):
    
    if LOCK_STATE["locked"]: return {"success": False, "error": "에디터가 잠금 상태입니다."}

    is_vip = False
    if membership_type == "member" and vip_key:
        try:
            key_data = await asyncio.to_thread(_db_get, f'keys/{vip_key}')
            if key_data and key_data.get('is_active') == True:
                expires_at = key_data.get('expires_at', 0)
                if expires_at != 0 and int(time.time()) > expires_at:
                    return {"success": False, "error": "기간이 만료된 키입니다."}
                
                # 기기 지문 2차 검증
                bound_device = key_data.get('bound_device_id', '')
                if not bound_device:
                    await asyncio.to_thread(_db_set, f'keys/{vip_key}/bound_device_id', device_id)
                elif bound_device != device_id:
                    return {"success": False, "error": "등록되지 않은 기기에서의 비정상 접근입니다."}
                    
                is_vip = True
            else:
                return {"success": False, "error": "유효하지 않거나 삭제된 VIP 키입니다."}
        except: return {"success": False, "error": "VIP 인증 서버 통신 중 오류가 발생했습니다."}

    try:
        service = await asyncio.to_thread(_process_download, transfer_code, confirmation_code)
        
        if service:
            token = secrets.token_hex(16)
            SESSIONS[token] = {"service": service, "last_active": time.time(), "is_vip": is_vip}
            summary = await asyncio.to_thread(service.summary) 
            return {
                "success": True,
                "token": token,
                "catfood": summary.get("current", {}).get("catfood", 0),
                "xp": summary.get("current", {}).get("xp", 0)
            }
        else:
            return {"success": False, "error": "이어하기 코드 또는 인증 번호가 올바르지 않습니다."}
    except Exception as e: return {"success": False, "error": str(e)}

def _process_upload(service, catfood, xp, normal, legend, platinum, catfruit, is_vip):
    service.set_catfood(catfood, is_vip)
    service.set_xp(xp, is_vip)
    service.set_normal_tickets(normal, is_vip)
    if is_vip:
        service.set_legend_tickets(legend, is_vip)
        service.set_platinum_tickets(platinum, is_vip)
        service.set_catfruit_all(catfruit, is_vip)
    return service.upload()

@app.post("/api/modify_and_upload")
async def modify_and_upload(catfood: int = Form(...), xp: int = Form(...), normal_tickets: int = Form(0),
                            legend_tickets: int = Form(0), platinum_tickets: int = Form(0), catfruit: int = Form(0),
                            x_session_token: str = Header(None)):
    
    if LOCK_STATE["locked"]: return {"success": False, "error": "에디터가 잠금 상태입니다."}

    try:
        session_data = get_user_session(x_session_token)
        service = session_data["service"]
        is_vip = session_data.get("is_vip", False)
        
        if not is_vip:
            if catfood > 17000 or xp > 20000000 or normal_tickets > 50:
                return {"success": False, "error": "비회원 최대 한도를 초과했습니다."}
        else:
            if catfood > 1000000 or xp > 100000000 or normal_tickets > 999 or legend_tickets > 999 or platinum_tickets > 999 or catfruit > 998:
                return {"success": False, "error": "회원(VIP) 최대 한도를 초과했습니다."}

        new_tc, new_cc = await asyncio.to_thread(_process_upload, service, catfood, xp, normal_tickets, legend_tickets, platinum_tickets, catfruit, is_vip)
        return {"success": True, "transfer_code": new_tc, "confirmation_code": new_cc}
        
    except HTTPException as he: return {"success": False, "error": he.detail}
    except Exception as e: return {"success": False, "error": str(e)}

@app.post("/api/reset_key_device")
async def reset_key_device(admin_password: str = Form(...), vip_key: str = Form(...)):
    if admin_password != ADMIN_PASSWORD: return {"success": False, "error": "관리자 권한이 없습니다."}
    try:
        await asyncio.to_thread(_db_set, f'keys/{vip_key}/bound_device_id', "")
        return {"success": True}
    except Exception as e: return {"success": False, "error": f"초기화 실패: {str(e)}"}