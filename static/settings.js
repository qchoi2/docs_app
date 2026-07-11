/* Runtime API Settings (UI_PRODUCT_SPEC §15.1).
   - 키는 서버 측 secret으로만 저장. 프론트엔드(브라우저) 저장소 사용 금지.
   - 저장 후에는 마지막 4자리만 표시하고 키 전문은 다시 표시하지 않는다.
   - 연결 테스트는 mock(형식 확인)만 — 실제 API 호출 없음.
   - disabled_reason: missing_api_key / missing_budget / missing_api_key_and_budget */
"use strict";

const $ = (id) => document.getElementById(id);

const REASON_LABELS = {
  missing_api_key: "Anthropic API key 필요",
  missing_budget: "예산 상한 필요 (per_call/per_run)",
  missing_api_key_and_budget: "API key와 예산 상한 모두 필요",
};

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = "INTERNAL_ERROR";
    try {
      const err = (await response.json()).error;
      message = err.message || err.code;
    } catch (e) { /* ignore */ }
    throw new Error(message);
  }
  return response;
}
const postJson = (path, body) => api(path, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
});

function announce(message) { $("live").textContent = message; }

document.addEventListener("DOMContentLoaded", () => {
  $("save-key").addEventListener("click", saveKey);
  $("test-key").addEventListener("click", testKey);
  $("delete-key").addEventListener("click", deleteKey);
  $("save-budget").addEventListener("click", saveBudget);
  refresh();
});

async function refresh() {
  try {
    const data = await (await api("/api/settings/runtime-api")).json();
    renderState(data.anthropic, data.budget, data.ai);
  } catch (error) {
    $("key-status").textContent = "설정을 불러오지 못했습니다";
    announce("설정 조회 실패: " + error.message);
  }
}

function renderState(anthropic, budget, ai) {
  if (anthropic.api_key_set) {
    const storage = anthropic.storage === "dpapi" ? "DPAPI 암호화" : "사용자 전용 파일 권한";
    $("key-status").textContent = `설정됨 — ****${anthropic.api_key_last4} (${storage} 저장)`;
  } else {
    $("key-status").textContent = "미설정";
  }
  $("test-key").disabled = $("delete-key").disabled = !anthropic.api_key_set;
  if (budget) {
    $("per-call").value = budget.per_call_limit_usd ?? "";
    $("per-run").value = budget.per_run_limit_usd ?? "";
  }
  const box = $("ai-status");
  if (ai.enabled) {
    box.innerHTML = '<span class="badge exact">사용 가능</span> key·예산이 설정되었습니다.';
  } else {
    const label = REASON_LABELS[ai.disabled_reason] || ai.disabled_reason;
    box.innerHTML = `<span class="badge draft">비활성</span> <span class="badge-warning">${label}</span>`;
  }
}

async function saveKey() {
  const value = $("api-key").value.trim();
  if (!value) { announce("API key를 입력하세요"); return; }
  try {
    const data = await (await postJson("/api/settings/anthropic-key", { api_key: value })).json();
    $("api-key").value = "";   // 입력창에 키를 남겨두지 않는다
    renderState({ api_key_set: true, api_key_last4: data.api_key_last4, storage: data.storage },
                null, data.ai);
    announce("API key 저장 완료 — 마지막 4자리 " + data.api_key_last4);
  } catch (error) { announce("저장 실패: " + error.message); }
}

async function testKey() {
  try {
    const data = await (await postJson("/api/settings/anthropic-key/test")).json();
    announce(data.message);
  } catch (error) { announce("연결 테스트 실패: " + error.message); }
}

async function deleteKey() {
  try {
    const data = await (await api("/api/settings/anthropic-key", { method: "DELETE" })).json();
    renderState({ api_key_set: false }, null, data.ai);
    announce("API key를 삭제했습니다. 새 키를 입력해 교체할 수 있습니다.");
  } catch (error) { announce("삭제 실패: " + error.message); }
}

function numOrNull(id) {
  const raw = $(id).value.trim();
  if (raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

async function saveBudget() {
  try {
    const data = await (await postJson("/api/settings/budget", {
      per_call_limit_usd: numOrNull("per-call"),
      per_run_limit_usd: numOrNull("per-run"),
    })).json();
    renderState({ api_key_set: !$("test-key").disabled }, data.budget, data.ai);
    announce(data.ai.enabled ? "예산 저장 완료 — AI 기능 사용 가능"
                             : "예산 저장 완료 — " + (REASON_LABELS[data.ai.disabled_reason] || ""));
  } catch (error) { announce("예산 저장 실패: " + error.message); }
}
