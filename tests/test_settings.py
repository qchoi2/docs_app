import io
import json
import os
import stat
import sys

import pytest

from lib import settings_store
from tests.test_webapp import make_app, call, get_json


BUDGET_TEMPLATE = """# 사용자 입력
per_call_limit_usd: null    # 1회 호출 상한
per_run_limit_usd:  null    # 1회 실행 상한
models:
  haiku:
    model_id: "claude-haiku-4-5-20251001"
"""


@pytest.fixture()
def settings_env(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    budget = tmp_path / "api_budget.yaml"
    budget.write_text(BUDGET_TEMPLATE, encoding="utf-8")
    monkeypatch.setenv("CONTRACT_SEARCH_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("CONTRACT_SEARCH_BUDGET_FILE", str(budget))
    return config_dir, budget


def test_api_key_save_masks_and_deletes(settings_env):
    config_dir, _ = settings_env
    saved = settings_store.save_api_key("sk-ant-abcdefghij1234")
    assert saved["api_key_last4"] == "1234"

    status = settings_store.api_key_status()
    assert status["api_key_set"] and status["api_key_last4"] == "1234"
    # 키 전문은 status에 없다
    assert "sk-ant" not in json.dumps(status)
    assert settings_store.load_api_key() == "sk-ant-abcdefghij1234"

    secrets = config_dir / "secrets.json"
    assert secrets.exists()
    if sys.platform != "win32":
        # DPAPI 불가 환경 폴백: 사용자 전용 권한
        mode = stat.S_IMODE(secrets.stat().st_mode)
        assert mode == 0o600

    assert settings_store.delete_api_key() is True
    assert settings_store.api_key_status()["api_key_set"] is False
    assert settings_store.load_api_key() is None


def test_budget_save_preserves_comments_and_gates_ai(settings_env):
    _, budget_path = settings_env
    assert settings_store.ai_status()["disabled_reason"] == "missing_api_key_and_budget"

    settings_store.save_budget(0.2, 2.0)
    text = budget_path.read_text(encoding="utf-8")
    assert "per_call_limit_usd: 0.2" in text
    assert "model_id" in text and "# 사용자 입력" in text  # 다른 내용 보존
    assert settings_store.load_budget() == {"per_call_limit_usd": 0.2, "per_run_limit_usd": 2.0}
    assert settings_store.ai_status()["disabled_reason"] == "missing_api_key"

    settings_store.save_api_key("sk-ant-abcdefghij9999")
    assert settings_store.ai_status() == {
        "enabled": True, "disabled_reason": None,
        "budget": {"per_call_limit_usd": 0.2, "per_run_limit_usd": 2.0}}

    settings_store.save_budget(None, 2.0)
    assert settings_store.ai_status()["disabled_reason"] == "missing_budget"


def test_runtime_api_endpoints(tmp_path, settings_env):
    app = make_app(tmp_path)

    status, data = get_json(app, "GET", "/api/settings/runtime-api")
    assert status == 200
    assert data["anthropic"]["api_key_set"] is False
    assert data["ai"]["disabled_reason"] == "missing_api_key_and_budget"

    # 형식이 틀린 키 거부
    status, data = call_json(app, "POST", "/api/settings/anthropic-key", {"api_key": "hello"})
    assert status == 400 and data["error"]["code"] == "VALIDATION_ERROR"

    status, data = call_json(app, "POST", "/api/settings/anthropic-key",
                             {"api_key": "sk-ant-abcdefghij5678"})
    assert status == 200 and data["api_key_last4"] == "5678"
    assert "sk-ant" not in json.dumps(data)  # 키 전문 비노출

    # mock 연결 테스트 — 실제 호출 없음
    status, data = call_json(app, "POST", "/api/settings/anthropic-key/test", {})
    assert status == 200 and data["mode"] == "format_only" and data["tested"] is True

    status, data = call_json(app, "POST", "/api/settings/budget",
                             {"per_call_limit_usd": 0.2, "per_run_limit_usd": 2.0})
    assert status == 200 and data["ai"]["enabled"] is True

    status, data = get_json(app, "DELETE", "/api/settings/anthropic-key")
    assert status == 200 and data["api_key_set"] is False
    assert data["ai"]["disabled_reason"] == "missing_api_key"


def test_budget_validation(tmp_path, settings_env):
    app = make_app(tmp_path)
    for bad in ({"per_call_limit_usd": "abc"}, {"per_call_limit_usd": -1},
                {"per_run_limit_usd": True}):
        status, data = call_json(app, "POST", "/api/settings/budget", bad)
        assert status == 400 and data["error"]["code"] == "VALIDATION_ERROR"


def test_settings_ui_never_uses_browser_storage_or_openai():
    from pathlib import Path
    static_dir = Path(__file__).resolve().parent.parent / "static"
    for name in ["settings.html", "settings.js", "app.js", "setup.js"]:
        text = (static_dir / name).read_text(encoding="utf-8")
        assert "localStorage" not in text and "sessionStorage" not in text, name
        if name != "settings.html":
            assert "openai" not in text.lower(), name
    # settings.html의 OpenAI 언급은 "받지 않는다" 안내 문구뿐이어야 한다
    html = (static_dir / "settings.html").read_text(encoding="utf-8")
    assert "OpenAI API key는 받지 않습니다" in html
    assert 'name="openai' not in html.lower() and 'id="openai' not in html.lower()


def call_json(app, method, path, body):
    status, headers, payload = call(app, method, path, body=body)
    return status, json.loads(payload.decode("utf-8"))
