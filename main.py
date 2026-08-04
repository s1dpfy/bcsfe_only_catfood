from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import os

from bcsfe_service import BCSFEService

app = FastAPI(title="Simple BCSFE Web")
templates = Jinja2Templates(directory="templates")

# 메모리에 현재 세션 유지 (단순화 버전)
current_service = None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/load_save")
async def load_save(transfer_code: str = Form(...), confirmation_code: str = Form(...)):
    global current_service
    try:
        service = BCSFEService()
        if service.download(transfer_code.strip(), confirmation_code.strip()):
            current_service = service
            # 현재 통조림 개수 요약해서 전달
            summary = service.summary()
            current_catfood = summary.get("current", {}).get("catfood", 0)
            return {"success": True, "catfood": current_catfood}
        else:
            return {"success": False, "error": "이어하기 코드 또는 인증 번호가 올바르지 않습니다."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/modify_and_upload")
async def modify_and_upload(catfood: int = Form(...)):
    global current_service
    if not current_service:
        return {"success": False, "error": "먼저 세이브를 불러와주세요."}
    
    try:
        # 1. 통조림 수정 적용
        current_service.set_catfood(catfood)
        
        # 2. 서버에 업로드하여 새로운 이어하기 코드(Transfer Code) 발급
        new_tc, new_cc = current_service.upload()
        
        return {
            "success": True,
            "transfer_code": new_tc,
            "confirmation_code": new_cc
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)