from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import requests
from requests.adapters import HTTPAdapter

ADMIN_PASSWORD = "0923"
SECRET = "BCSFE-KR-MEMBER-0923"
PRICE_ONCE = 3000
PRICE_FULL = 10000
TYPE_ONCE = "once"
TYPE_FULL = "full"

FIREBASE_DB = os.environ.get(
    "FIREBASE_DB_URL",
    "https://battlecatscatfood-default-rtdb.asia-southeast1.firebasedatabase.app",
).rstrip("/")
FIREBASE_SECRET = os.environ.get(
    "FIREBASE_DB_SECRET",
    "pf6BWIT74lJUp2MXkt1ieSKmzMJundrcfda85JjZ",
)
KEYS_NODE = "keys"

_session = requests.Session()
_session.mount("https://", HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=1))
_session.headers.update({"Accept": "application/json"})


def device_id() -> str:
    parts = [
        os.environ.get("COMPUTERNAME", ""),
        os.environ.get("USERNAME", ""),
        os.environ.get("USERPROFILE", ""),
        os.environ.get("PROCESSOR_IDENTIFIER", ""),
    ]
    if os.name == "nt":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            parts.append(str(guid))
        except Exception:
            pass
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]


def _sign(kind: str, raw: str) -> str:
    return hashlib.sha256(f"{SECRET}|{kind}|{raw}".encode()).hexdigest()[:8].upper()


def make_key(kind: str) -> str:
    raw = secrets.token_hex(8).upper()
    prefix = "ONCE" if kind == TYPE_ONCE else "FULL"
    grouped = "-".join(raw[i : i + 4] for i in range(0, 16, 4))
    return f"BCSK-{prefix}-{grouped}-{_sign(kind, raw)}"


def parse_key(key: str) -> tuple[str, str] | None:
    text = (key or "").strip().upper().replace(" ", "")
    parts = text.split("-")
    if len(parts) != 7 or parts[0] != "BCSK" or parts[1] not in ("ONCE", "FULL"):
        return None
    kind = TYPE_ONCE if parts[1] == "ONCE" else TYPE_FULL
    raw = "".join(parts[2:6])
    if len(raw) != 16 or any(c not in "0123456789ABCDEF" for c in raw):
        return None
    if parts[6] != _sign(kind, raw):
        return None
    return kind, raw


def _key_id(key: str) -> str:
    return (key or "").strip().upper().replace(".", "_")


def _fb(method: str, path: str, payload: Any = None, extra: dict[str, str] | None = None) -> Any:
    url = f"{FIREBASE_DB}/{path.strip('/')}.json"
    params = {"auth": FIREBASE_SECRET}
    if extra:
        params.update(extra)
    try:
        response = _session.request(
            method,
            url,
            params=params,
            json=payload,
            timeout=12,
        )
    except Exception as err:
        raise RuntimeError("Firebase에 연결하지 못했습니다.") from err
    if response.status_code >= 400:
        raise RuntimeError("Firebase 저장에 실패했습니다.")
    if not response.content:
        return None
    try:
        return response.json()
    except Exception:
        return None


def _ours(kid: str, item: dict[str, Any] | None) -> bool:
    if str(kid).startswith("BCSK-"):
        return True
    if not isinstance(item, dict):
        return False
    if str(item.get("key") or "").startswith("BCSK-"):
        return True
    return item.get("source") == "nyanko-editor"


def load_catalog() -> dict[str, Any]:
    data = _fb("GET", KEYS_NODE, extra={"shallow": "true"})
    ids: list[str] = []
    if isinstance(data, dict):
        ids = [str(kid) for kid in data if _ours(str(kid), {"key": kid})]
    items: list[dict[str, Any]] = []
    if ids:
        with ThreadPoolExecutor(max_workers=min(8, len(ids))) as pool:
            for rec in pool.map(find_record, ids):
                if isinstance(rec, dict):
                    items.append(rec)
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"keys": items}


def save_catalog(data: dict[str, Any]) -> None:
    for item in data.get("keys") or []:
        if not isinstance(item, dict):
            continue
        key = _key_id(str(item.get("key") or ""))
        if key and _ours(key, item):
            upsert_record(item)


def find_record(key: str) -> dict[str, Any] | None:
    want = _key_id(key)
    if not want:
        return None
    data = _fb("GET", f"{KEYS_NODE}/{want}")
    if not isinstance(data, dict):
        return None
    data.setdefault("key", want)
    return data


def upsert_record(record: dict[str, Any]) -> None:
    key = _key_id(str(record.get("key") or ""))
    if not key:
        raise ValueError("invalid key")
    _fb("PUT", f"{KEYS_NODE}/{key}", record)


def create_key(kind: str, note: str = "") -> dict[str, Any]:
    if kind not in (TYPE_ONCE, TYPE_FULL):
        raise ValueError("invalid kind")
    record = {
        "id": str(uuid.uuid4()),
        "key": make_key(kind),
        "type": kind,
        "price": PRICE_ONCE if kind == TYPE_ONCE else PRICE_FULL,
        "note": note,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "used": False,
        "revoked": False,
        "bound_device": None,
        "bound_at": None,
        "source": "nyanko-editor",
    }
    upsert_record(record)
    return record


def revoke(key: str) -> bool:
    rec = find_record(key)
    if rec is None:
        return False
    rec["revoked"] = True
    upsert_record(rec)
    return True


def redeem(key: str, device: str | None = None) -> tuple[bool, str]:
    parsed = parse_key(key)
    if parsed is None:
        return False, "키가 올바르지 않습니다. 관리자가 발급한 키인지 확인하세요."
    kind, _raw = parsed
    text = key.strip().upper().replace(" ", "")
    me = (device or device_id()).strip()
    rec = find_record(text)
    if rec is None:
        return False, "등록되지 않은 키입니다. 관리자에게 발급받은 키인지 확인하세요."
    if rec.get("revoked"):
        return False, "취소된 키입니다."
    now = datetime.now().isoformat(timespec="seconds")
    if kind == TYPE_ONCE:
        if rec.get("used"):
            bound = rec.get("bound_device")
            if bound and bound == me:
                return True, "이미 이 기기에 등록된 키입니다."
            return False, "이미 사용된 1회권입니다."
        rec["used"] = True
        rec["bound_device"] = me
        rec["bound_at"] = now
    else:
        bound = rec.get("bound_device")
        if bound and bound != me:
            return False, "이 무제한 키는 다른 기기에 묶여 있습니다."
        rec["bound_device"] = me
        rec["bound_at"] = now
        rec["used"] = True
    upsert_record(rec)
    if kind == TYPE_FULL:
        return True, "고급회원(무제한)으로 등록했습니다. 이 기기에 발자국을 남겼습니다."
    return True, "고급회원 1회권이 이 기기에 등록되었습니다."
