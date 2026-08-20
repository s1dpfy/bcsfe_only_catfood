from fastapi import FastAPI, Request, Form, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import secrets
import time
import asyncio

from bcsfe_service import BCSFEService

app = FastAPI(title="Simple BCSFE Web with Sessions")
templates = Jinja2Templates(directory="templates")

SESSIONS = {}
SESSION_TIMEOUT = 1800 

# ==========================================
# 💰 추가된 모금함(서버 유지비) 전역 상태 변수
# ==========================================
FUND_CURRENT = 0
FUND_TARGET = 50000
ADMIN_PASSWORD = "boji"

def is_site_unlocked():
    return FUND_CURRENT >= FUND_TARGET

# ==========================================

async def session_cleanup_task():
    while True:
        await asyncio.sleep(60)
        current_time = time.time()
        expired_tokens = [tok for tok, data in SESSIONS.items() if current_time - data["last_active"] > SESSION_TIMEOUT]
        for tok in expired_tokens:
            del SESSIONS[tok]

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(session_cleanup_task())

def get_user_service(x_session_token: str = Header(None)) -> BCSFEService:
    if not x_session_token or x_session_token not in SESSIONS:
        raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다.")
    SESSIONS[x_session_token]["last_active"] = time.time()
    return SESSIONS[x_session_token]["service"]

# --- 🌐 페이지 라우터 ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

# 관리자 페이지 추가
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")

# --- 📊 모금 관련 API ---
@app.get("/api/fund_status")
async def fund_status():
    return {
        "current": FUND_CURRENT,
        "target": FUND_TARGET,
        "unlocked": is_site_unlocked()
    }

@app.post("/api/admin/update")
async def admin_update(
    password: str = Form(...),
    target: int = Form(None),
    add_amount: int = Form(None)
):
    global FUND_CURRENT, FUND_TARGET
    
    # 🔒 보안: 비밀번호 체크
    if password != ADMIN_PASSWORD:
        return {"success": False, "error": "비밀번호가 올바르지 않습니다."}
    
    if target is not None:
        FUND_TARGET = target
    if add_amount is not None:
        FUND_CURRENT += add_amount
        
    return {
        "success": True, 
        "current": FUND_CURRENT, 
        "target": FUND_TARGET, 
        "unlocked": is_site_unlocked()
    }

# --- 🛠️ 기존 기능 (보안 락 추가됨) ---
@app.post("/api/load_save")
async def load_save(transfer_code: str = Form(...), confirmation_code: str = Form(...)):
    if not is_site_unlocked():
        return {"success": False, "error": "🚨 모금 목표액이 달성되지 않아 서버가 잠겨있습니다."}

    try:
        service = BCSFEService()
        if service.download(transfer_code.strip(), confirmation_code.strip()):
            token = secrets.token_hex(16)
            SESSIONS[token] = {"service": service, "last_active": time.time()}
            summary = service.summary()
            return {
                "success": True, 
                "token": token, 
                "catfood": summary.get("current", {}).get("catfood", 0),
                "xp": summary.get("current", {}).get("xp", 0)
            }
        else:
            return {"success": False, "error": "이어하기 코드 또는 인증 번호가 올바르지 않습니다."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/modify_and_upload")
async def modify_and_upload(catfood: int = Form(...), xp: int = Form(...), x_session_token: str = Header(None)):
    if not is_site_unlocked():
        return {"success": False, "error": "🚨 모금 목표액이 달성되지 않아 서버가 잠겨있습니다."}

    try:
        service = get_user_service(x_session_token)
        service.set_catfood(catfood)
        service.set_xp(xp)
        new_tc, new_cc = service.upload()
        
        return {"success": True, "transfer_code": new_tc, "confirmation_code": new_cc}
    except HTTPException as he:
        return {"success": False, "error": he.detail}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)