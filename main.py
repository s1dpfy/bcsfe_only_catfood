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

# 사용자별 세션을 저장하는 딕셔너리 { token: {"service": 객체, "last_active": 시간} }
SESSIONS = {}
SESSION_TIMEOUT = 1800  # 30분 동안 활동이 없으면 세션 자동 삭제

# 백그라운드에서 만료된 세션을 주기적으로 청소하는 태스크
async def session_cleanup_task():
    while True:
        await asyncio.sleep(60)
        current_time = time.time()
        expired_tokens = [
            tok for tok, data in SESSIONS.items() 
            if current_time - data["last_active"] > SESSION_TIMEOUT
        ]
        for tok in expired_tokens:
            del SESSIONS[tok]

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(session_cleanup_task())

# 세션 토큰을 검증하고 서비스를 가져오는 함수
def get_user_service(x_session_token: str = Header(None)) -> BCSFEService:
    if not x_session_token or x_session_token not in SESSIONS:
        raise HTTPException(status_code=401, detail="세션이 만료되었거나 유효하지 않습니다. 다시 세이브를 불러와주세요.")
    # 활동 시간 갱신
    SESSIONS[x_session_token]["last_active"] = time.time()
    return SESSIONS[x_session_token]["service"]

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/load_save")
async def load_save(transfer_code: str = Form(...), confirmation_code: str = Form(...)):
    try:
        service = BCSFEService()
        if service.download(transfer_code.strip(), confirmation_code.strip()):
            # 새로운 고유 세션 토큰 발급
            token = secrets.token_hex(16)
            SESSIONS[token] = {
                "service": service,
                "last_active": time.time()
            }
            
            summary = service.summary()
            current_catfood = summary.get("current", {}).get("catfood", 0)
            current_xp = summary.get("current", {}).get("xp", 0) # XP 추가
            
            return {
                "success": True, 
                "token": token, 
                "catfood": current_catfood,
                "xp": current_xp # 프론트로 XP 전송
            }
        else:
            return {"success": False, "error": "이어하기 코드 또는 인증 번호가 올바르지 않습니다."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/modify_and_upload")
async def modify_and_upload(catfood: int = Form(...), xp: int = Form(...), x_session_token: str = Header(None)):
    try:
        # 본인만의 세션에 해당하는 서비스 객체 가져오기
        service = get_user_service(x_session_token)
        
        # 1. 통조림 및 XP 수정 적용
        service.set_catfood(catfood)
        service.set_xp(xp) # XP 적용 로직 추가
        
        # 2. 서버에 업로드하여 새로운 이어하기 코드 발급
        new_tc, new_cc = service.upload()
        
        return {
            "success": True,
            "transfer_code": new_tc,
            "confirmation_code": new_cc
        }
    except HTTPException as he:
        return {"success": False, "error": he.detail}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)