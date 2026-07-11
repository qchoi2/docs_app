"""Runtime API Settings 저장소 (BACKEND_REVIEW_PC §2.1, UI_PRODUCT_SPEC §15.1).

원칙:
- ANTHROPIC_API_KEY는 서버 로컬 secret으로만 저장한다. 프론트엔드 저장소
  (localStorage 등), git 저장소, cs_index, 로그에는 절대 남기지 않는다.
- Windows에서는 DPAPI(CryptProtectData, ctypes — 추가 의존성 없음)로 사용자
  계정 단위 암호화 저장을 기본으로 한다. DPAPI를 쓸 수 없는 환경에서는
  파일 권한을 현재 사용자 전용(0600)으로 제한한 평문 저장으로 폴백한다.
- 저장 후 UI에는 마지막 4자리만 표시한다. 키 전문은 다시 내려주지 않는다.
- 예산(per_call/per_run)은 data/api_budget.yaml의 사용자 입력 두 줄만 갱신한다.
  둘 중 하나라도 null이면 AI 기능은 disabled다.
- Codex용 OpenAI API key는 받지 않는다 (입력란 자체를 만들지 않는다).

disabled_reason (소유자 지정 명칭):
  missing_api_key / missing_budget / missing_api_key_and_budget
"""

from __future__ import annotations

import base64
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Dict, Optional

import yaml

SECRETS_FILE = "secrets.json"
_BUDGET_KEYS = ("per_call_limit_usd", "per_run_limit_usd")


# ---------------- 저장 위치 ----------------

def config_dir() -> Path:
    """%APPDATA%/contract-search (Windows) 또는 ~/.config/contract-search.

    테스트/특수 환경은 CONTRACT_SEARCH_CONFIG_DIR로 재지정할 수 있다.
    """
    override = os.environ.get("CONTRACT_SEARCH_CONFIG_DIR")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "contract-search"
    return Path.home() / ".config" / "contract-search"


def _secrets_path() -> Path:
    return config_dir() / SECRETS_FILE


def _restrict_to_user(path: Path) -> None:
    """비 Windows/DPAPI 불가 환경 폴백: 현재 사용자 전용 파일 권한."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass


# ---------------- DPAPI (Windows 전용, ctypes) ----------------

def _dpapi_available() -> bool:
    return sys.platform == "win32"


def _dpapi_protect(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def to_blob(raw: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(raw, len(raw))
        return DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    blob_in = to_blob(data)
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


# ---------------- API key 저장/조회/삭제 ----------------

def save_api_key(api_key: str) -> Dict[str, object]:
    """키를 저장하고 표시용 메타(last4, storage)만 반환한다. 키 전문은 반환하지 않는다."""
    raw = api_key.encode("utf-8")
    if _dpapi_available():
        payload = _dpapi_protect(raw)
        storage = "dpapi"
    else:
        payload = raw
        storage = "plain_acl"
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = _secrets_path()
    record = {
        "anthropic_api_key": {
            "storage": storage,
            "data": base64.b64encode(payload).decode("ascii"),
            "last4": api_key[-4:],
        }
    }
    path.write_text(json.dumps(record), encoding="utf-8")
    _restrict_to_user(path)
    return {"api_key_set": True, "api_key_last4": api_key[-4:], "storage": storage}


def _load_record() -> Optional[Dict[str, object]]:
    path = _secrets_path()
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = record.get("anthropic_api_key")
    return entry if isinstance(entry, dict) else None


def api_key_status() -> Dict[str, object]:
    entry = _load_record()
    if entry is None:
        return {"api_key_set": False, "api_key_last4": None, "storage": None}
    return {"api_key_set": True, "api_key_last4": entry.get("last4"),
            "storage": entry.get("storage")}


def load_api_key() -> Optional[str]:
    """실제 API 호출 직전에만 사용한다. 로그·응답에 절대 싣지 않는다."""
    entry = _load_record()
    if entry is None:
        return None
    try:
        payload = base64.b64decode(entry.get("data") or "")
        if entry.get("storage") == "dpapi":
            payload = _dpapi_unprotect(payload)
        return payload.decode("utf-8")
    except (OSError, ValueError):
        return None


def delete_api_key() -> bool:
    path = _secrets_path()
    if not path.exists():
        return False
    path.unlink()
    return True


# ---------------- 예산 (data/api_budget.yaml) ----------------

def budget_file() -> Path:
    override = os.environ.get("CONTRACT_SEARCH_BUDGET_FILE")
    if override:
        return Path(override)
    for base in (Path.cwd(), Path(__file__).resolve().parent.parent):
        candidate = base / "data" / "api_budget.yaml"
        if candidate.exists():
            return candidate
    return Path.cwd() / "data" / "api_budget.yaml"


def load_budget() -> Dict[str, Optional[float]]:
    path = budget_file()
    if not path.exists():
        return {key: None for key in _BUDGET_KEYS}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {key: None for key in _BUDGET_KEYS}
    result = {}
    for key in _BUDGET_KEYS:
        value = data.get(key)
        result[key] = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    return result


def save_budget(per_call: Optional[float], per_run: Optional[float]) -> Dict[str, Optional[float]]:
    """api_budget.yaml의 사용자 입력 두 줄만 갱신한다 (주석·나머지 설정 보존)."""
    path = budget_file()
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "per_call_limit_usd: null\nper_run_limit_usd: null\n"
    for key, value in (("per_call_limit_usd", per_call), ("per_run_limit_usd", per_run)):
        rendered = "null" if value is None else f"{value:g}"
        text, count = re.subn(
            rf"(?m)^({key}\s*:)\s*[^\s#]+", rf"\g<1> {rendered}", text)
        if count == 0:
            text = text.rstrip("\n") + f"\n{key}: {rendered}\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return load_budget()


# ---------------- AI 기능 상태 ----------------

def ai_status() -> Dict[str, object]:
    key_set = api_key_status()["api_key_set"]
    budget = load_budget()
    budget_set = all(budget[key] is not None for key in _BUDGET_KEYS)
    if not key_set and not budget_set:
        reason = "missing_api_key_and_budget"
    elif not key_set:
        reason = "missing_api_key"
    elif not budget_set:
        reason = "missing_budget"
    else:
        reason = None
    return {"enabled": reason is None, "disabled_reason": reason, "budget": budget}
