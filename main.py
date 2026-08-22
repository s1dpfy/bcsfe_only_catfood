from fastapi import FastAPI, Request, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import secrets
import time
import asyncio

from bcsfe_service import BCSFEService

app = FastAPI(title="Simple BCSFE Web with Sessions")
templates = Jinja2Templates(directory="templates")

SESSIONS = {}
# 💡 서버 메모리 최적화를 위해 세션 유지 시간을 30분에서 5분으로 단축
SESSION_TIMEOUT = 300 

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

# 💡 광고 네트워크용 Service Worker 파일 지원
@app.get("/sw.js")
async def serve_sw():
    # sw.js 파일이 main.py와 같은 최상단 폴더에 있어야 합니다.
    return FileResponse("sw.js", media_type="application/javascript")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")

# --- 🛠️ 코어 API (비동기 병목 현상 해결을 위해 async 키워드 제거) ---
@app.post("/api/load_save")
def load_save(transfer_code: str = Form(...), confirmation_code: str = Form(...)):
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
def modify_and_upload(catfood: int = Form(...), xp: int = Form(...), x_session_token: str = Header(None)):
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
    # 💡 CPU 리소스 확보를 위해 개발자 모드(reload) 끄기
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=False)