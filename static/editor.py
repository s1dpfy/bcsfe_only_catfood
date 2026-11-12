import builtins
import base64
import json

builtins.input = lambda *args, **kwargs: ""

import requests
from requests import Response
from requests.structures import CaseInsensitiveDict
from pyodide.ffi import run_sync
from js import nyanslyHttpAsync

def _http(method, url, headers, body):
    if isinstance(body, str):
        body = body.encode()
    body = body or b""
    raw = run_sync(nyanslyHttpAsync(method, url, json.dumps(headers), base64.b64encode(body).decode()))
    data = json.loads(raw)
    resp = Response()
    resp.status_code = int(data.get("status") or 0)
    resp.headers = CaseInsensitiveDict(data.get("headers") or {})
    resp._content = base64.b64decode(data.get("body_b64") or "")
    resp.url = url
    resp.reason = "OK" if resp.status_code < 400 else "Error"
    return resp

def _send(self, request, **kwargs):
    return _http(request.method, request.url, dict(request.headers), request.body or b"")

requests.sessions.Session.send = _send

import micropip
await micropip.install("pyjwt")
await micropip.install("bcsfe", deps=False)

from bcsfe import core

core.core_data.init_data()

CAPS = {
    "catfood": 1000000,
    "xp": 100000000,
    "normal": 999,
    "legend": 999,
    "platinum": 999,
    "catfruit": 998,
    "np": 9999,
    "catseyes": 999,
}

class Editor:
    def __init__(self):
        self.handler = None
        self.save = None

    def download(self, transfer_code, confirmation_code):
        handler, _result = core.ServerHandler.from_codes(
            transfer_code.strip(),
            confirmation_code.strip(),
            core.CountryCode("kr"),
            core.GameVersion.from_string("15.6.0"),
            print=False,
            save_backup=False,
        )
        if handler is None or handler.save_file is None:
            return {"success": False, "error": "이어하기 코드 또는 인증 번호가 올바르지 않거나, 게임 버전이 맞지 않습니다."}
        handler.print = False
        self.handler = handler
        save = handler.save_file
        self.save = save
        return {
            "success": True,
            "catfood": int(save.catfood),
            "xp": int(save.xp),
            "normal_tickets": int(save.normal_tickets),
            "legend_tickets": int(save.legend_tickets),
            "platinum_tickets": int(save.platinum_tickets),
            "catfruit": [int(v) for v in list(save.catfruit)],
            "catseyes": [int(v) for v in list(save.catseyes)],
            "np": int(save.np),
        }

    def _clamp_list(self, current, values, limit):
        out = list(current)
        for i, value in enumerate(values or []):
            if i < len(out):
                out[i] = min(max(0, int(value)), limit)
        return out

    def upload(self, payload):
        if self.handler is None or self.save is None:
            return {"success": False, "error": "먼저 세이브를 불러오세요."}
        save = self.save
        if payload.get("catfood") is not None:
            save.catfood = min(max(0, int(payload["catfood"])), CAPS["catfood"])
        if payload.get("xp") is not None:
            save.xp = min(max(0, int(payload["xp"])), CAPS["xp"])
        if payload.get("normal") is not None:
            save.normal_tickets = min(max(0, int(payload["normal"])), CAPS["normal"])
        if payload.get("legend") is not None:
            save.legend_tickets = min(max(0, int(payload["legend"])), CAPS["legend"])
        if payload.get("platinum") is not None:
            save.platinum_tickets = min(max(0, int(payload["platinum"])), CAPS["platinum"])
        if payload.get("np") is not None:
            save.np = min(max(0, int(payload["np"])), CAPS["np"])
        if payload.get("catfruitEach") is not None:
            save.catfruit = self._clamp_list(save.catfruit, payload["catfruitEach"], CAPS["catfruit"])
        if payload.get("catseyesEach") is not None:
            save.catseyes = self._clamp_list(save.catseyes, payload["catseyesEach"], CAPS["catseyes"])
        codes = self.handler.get_codes()
        if not codes or not codes[0] or not codes[1]:
            return {"success": False, "error": "업로드에 실패했습니다."}
        self.handler = None
        self.save = None
        return {"success": True, "transfer_code": str(codes[0]), "confirmation_code": str(codes[1])}

editor = Editor()

def api_download(transfer_code, confirmation_code):
    try:
        return json.dumps(editor.download(transfer_code, confirmation_code), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)

def api_upload(payload_json):
    try:
        payload = json.loads(payload_json)
        return json.dumps(editor.upload(payload), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
