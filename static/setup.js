/* 색인 설정/진행률 화면 (UI-0.2 온보딩 + UI-0.3 진행률).
   - 원본 폴더는 경로 텍스트 입력 + POST /api/settings/root-path/validate로만 확인한다.
     (브라우저 폴더 피커로 절대경로를 얻는 방식 금지)
   - 진행률은 GET /api/jobs/{id}를 1.5초 간격 폴링한다 (SSE/WebSocket은 v2).
   - 서버는 raw traceback을 절대 내려주지 않는다. 화면에는 표준 error_code 기반
     메시지만 표시한다. */
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value == null ? "" : value)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const POLL_MS = 1500;
let currentJobId = null;
let pollTimer = null;
let lastAnnouncedStatus = null;

const ERROR_MESSAGES = {
  ROOT_NOT_FOUND: "원본 폴더를 찾을 수 없습니다. 경로를 다시 확인하세요.",
  VALIDATION_ERROR: "요청 값이 올바르지 않습니다.",
  INDEX_JOB_ALREADY_RUNNING: "이미 실행 중인 색인 작업이 있습니다.",
  SQLITE_BUSY: "데이터베이스가 잠시 사용 중입니다. 잠시 후 다시 시도하세요.",
  interrupted: "앱이 중단되어 작업이 종료되었습니다. 다시 실행하면 이어서 색인됩니다.",
  cancelled: "사용자가 작업을 취소했습니다. 이미 색인된 파일은 유지됩니다.",
  INTERNAL_ERROR: "서버 오류가 발생했습니다. 서버 로그를 확인하세요.",
};
const errMsg = (code) => ERROR_MESSAGES[code] || `오류 (${code})`;

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let code = "INTERNAL_ERROR";
    try { code = (await response.json()).error.code; } catch (e) { /* ignore */ }
    throw new Error(code);
  }
  return response;
}
const postJson = (path, body) => api(path, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
});

function announce(message) { $("live").textContent = message; }

/* ---------- init ---------- */
document.addEventListener("DOMContentLoaded", () => {
  $("validate-button").addEventListener("click", validatePath);
  $("root-path").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      if (event.isComposing || event.keyCode === 229) return;
      event.preventDefault();
      validatePath();
    }
  });
  $("root-path").addEventListener("input", () => { $("start-button").disabled = true; });
  $("start-button").addEventListener("click", startIndexJob);
  $("cancel-button").addEventListener("click", cancelJob);
  $("log-button").addEventListener("click", toggleLog);
  loadJobs();
});

/* ---------- 1단계: 경로 검증 ---------- */
async function validatePath() {
  const path = $("root-path").value.trim();
  const box = $("validate-result");
  if (!path) { announce("경로를 입력하세요"); return; }
  box.hidden = false;
  box.textContent = "확인 중…";
  try {
    const info = await (await postJson("/api/settings/root-path/validate", { path })).json();
    const ok = info.exists && info.is_dir && info.readable;
    const rows = [
      ["경로", info.path],
      ["상태", info.message],
      ["예상 파일 수", `${info.file_count}건 (색인 대상 .docx/.pdf ${info.supported_file_count}건` +
        (info.scan_truncated ? ", 상한 도달 — 실제는 더 많을 수 있음" : "") + ")"],
      ["인덱스 저장 위치", info.index_dir],
    ];
    box.innerHTML =
      `<div class="validate-head ${ok ? "ok" : "bad"}">${ok ? "사용 가능한 경로입니다" : esc(info.message)}</div>` +
      rows.map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span>${esc(v)}</span></div>`).join("") +
      (info.network_drive ? `<div class="badge-warning">네트워크 드라이브로 보입니다 — 원본은 가능하지만 색인 산출물은 로컬 디스크에 두세요.</div>` : "") +
      `<div class="body-muted">${esc(info.read_only_notice || "")}</div>`;
    $("index-dir").textContent = info.index_dir || "cs_index";
    $("start-button").disabled = !ok;
    announce(ok ? "경로 확인 완료 — 색인을 시작할 수 있습니다" : "경로를 사용할 수 없습니다: " + info.message);
  } catch (error) {
    box.textContent = errMsg(error.message);
    $("start-button").disabled = true;
    announce("경로 확인 실패: " + errMsg(error.message));
  }
}

/* ---------- 2단계: 색인 시작 ---------- */
async function startIndexJob() {
  const root = $("root-path").value.trim();
  const batch = $("batch-label").value.trim();
  const body = { root };
  if (batch) body.batch_label = batch;
  $("start-button").disabled = true;
  try {
    const data = await (await postJson("/api/jobs/index", body)).json();
    announce("색인 작업이 시작되었습니다");
    watchJob(data.job_id);
  } catch (error) {
    $("start-button").disabled = false;
    announce("색인 시작 실패: " + errMsg(error.message));
  }
}

/* ---------- 3단계: 진행률 폴링 (1.5초) ---------- */
function watchJob(jobId) {
  currentJobId = jobId;
  lastAnnouncedStatus = null;
  $("job-section").hidden = false;
  $("job-log").hidden = true;
  if (pollTimer) clearTimeout(pollTimer);
  pollJob();
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const job = await (await api(`/api/jobs/${currentJobId}`)).json();
    renderJob(job);
    if (!["completed", "failed", "cancelled"].includes(job.status)) {
      pollTimer = setTimeout(pollJob, POLL_MS);
    } else {
      loadJobs();
    }
  } catch (error) {
    $("job-status").textContent = errMsg(error.message);
    pollTimer = setTimeout(pollJob, POLL_MS * 2);
  }
}

const STATUS_LABELS = { queued: "대기 중", running: "실행 중", completed: "완료",
                        failed: "실패", cancelled: "취소됨" };

function renderJob(job) {
  const label = STATUS_LABELS[job.status] || job.status;
  const done = job.progress_done || 0;
  const total = job.progress_total || 0;
  let text = `상태: ${label}`;
  if (total) text += ` · ${done.toLocaleString()} / ${total.toLocaleString()} files`;
  if (job.status === "failed" && job.error_code) text += ` · ${errMsg(job.error_code)}`;
  if (job.status === "cancelled") text += ` · ${errMsg("cancelled")}`;
  $("job-status").textContent = text;
  $("job-current").textContent = job.current_item ? `현재 파일: ${job.current_item}` : "";
  $("progress-fill").style.width = total ? `${Math.round((done / total) * 100)}%` : "0%";
  $("cancel-button").hidden = !["queued", "running"].includes(job.status);
  $("log-button").hidden = false;
  // aria-live는 상태 전이 시에만 알린다 (매 폴링마다 읽어주지 않음)
  if (job.status !== lastAnnouncedStatus) {
    lastAnnouncedStatus = job.status;
    announce(`색인 작업 ${label}` + (total && job.status === "running" ? ` — 총 ${total.toLocaleString()}개 파일` : ""));
  }
}

async function cancelJob() {
  if (!currentJobId) return;
  try {
    await postJson(`/api/jobs/${currentJobId}/cancel`);
    announce("취소를 요청했습니다 — 현재 파일까지 처리 후 중단됩니다");
  } catch (error) { announce("취소 실패: " + errMsg(error.message)); }
}

async function toggleLog() {
  const box = $("job-log");
  if (!box.hidden) { box.hidden = true; return; }
  if (!currentJobId) return;
  try {
    const data = await (await api(`/api/jobs/${currentJobId}/log`)).json();
    box.textContent = (data.entries || []).map((e) => `${e.ts}  ${e.line}`).join("\n") || "(로그 없음)";
    box.hidden = false;
  } catch (error) { announce("로그를 불러오지 못했습니다: " + errMsg(error.message)); }
}

/* ---------- 최근 작업 목록 ---------- */
async function loadJobs() {
  try {
    const data = await (await api("/api/jobs?limit=10")).json();
    const jobs = data.jobs || [];
    const box = $("jobs-list");
    if (!jobs.length) { box.textContent = "아직 실행한 작업이 없습니다."; return; }
    box.innerHTML = jobs.map((job) => {
      const label = STATUS_LABELS[job.status] || job.status;
      const when = (job.created_at || "").replace("T", " ").slice(0, 19);
      const prog = job.progress_total ? ` · ${job.progress_done}/${job.progress_total}` : "";
      const err = job.status === "failed" && job.error_code ? ` · ${esc(errMsg(job.error_code))}` : "";
      return `<div class="job-row"><span class="badge ${job.status === "completed" ? "exact" : job.status === "failed" ? "draft" : ""}">${esc(label)}</span> ` +
        `<span class="mono">${esc(job.type)}</span> ${esc(when)}${prog}${err} ` +
        `<button type="button" class="button-ghost-sm" data-job="${esc(job.id)}">보기</button></div>`;
    }).join("");
    box.querySelectorAll("button[data-job]").forEach((button) =>
      button.addEventListener("click", () => watchJob(button.dataset.job)));
  } catch (error) { $("jobs-list").textContent = "작업 목록을 불러오지 못했습니다."; }
}
