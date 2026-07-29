"use strict";

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value == null ? "" : value)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error("request failed");
  return response.json();
}

document.addEventListener("DOMContentLoaded", () => {
  $("refresh").addEventListener("click", loadDashboard);
  loadDashboard();
});

async function loadDashboard() {
  try {
    const data = await api("/api/ops/dashboard");
    renderStatus(data);
    renderBatches(data.batch_labels || []);
    renderFailures(data.failures || []);
    renderFeedback(data);
    renderUnclassified(data.unclassified_folders || []);
    renderJobs(data.jobs || []);
    $("live").textContent = "운영 대시보드를 불러왔습니다.";
  } catch (error) {
    $("live").textContent = "운영 대시보드를 불러오지 못했습니다.";
  }
  await loadBurndown();
}

// 번다운은 V4 색인이 없는 코퍼스에서는 실패할 수 있으므로 별도 요청으로 분리한다
// (운영 대시보드 본체가 함께 죽지 않게).
async function loadBurndown() {
  try {
    const data = await api("/api/ops/burndown");
    $("burndown-error").textContent = "";
    renderBurndown(data);
  } catch (error) {
    $("burndown-error").textContent =
      "번다운 지표를 불러오지 못했습니다 (V4 색인이 없을 수 있습니다).";
  }
}

function pct(value) {
  return value == null ? "-" : `${value}%`;
}

function progressRow(label, block) {
  const width = block.percent == null ? 0 : block.percent;
  return (
    `<div class="burndown-row"><span class="burndown-label">${esc(label)}</span>` +
    `<span class="progress-track burndown-track">` +
    `<span class="progress-fill" style="width:${esc(width)}%"></span></span>` +
    `<strong class="burndown-num">${esc(block.evaluated)}/${esc(block.total)}` +
    ` · ${esc(pct(block.percent))}</strong></div>`
  );
}

function renderBurndown(data) {
  const index = data.index || {};
  $("burndown-meta").textContent =
    `${data.generated_at} · taxonomy v${index.taxonomy_version}` +
    ` · schema v${index.schema_version} rev ${index.schema_revision}`;

  const progress = data.type_progress || {};
  const rows = [
    progressRow("전체", progress.overall),
    progressRow("core 4유형", progress.core_planned),
    progressRow("CB/BW/EB", progress.scope_added),
  ];
  (progress.by_type || []).forEach((row) => rows.push(progressRow(row.ctype, row)));
  $("burndown-types").innerHTML = rows.join("");

  const families = (data.family_coverage || {}).families || {};
  const names = Object.keys(families);
  const head =
    "<tr><th>family</th><th>body<br>complete</th><th>body<br>partial</th>" +
    "<th>body<br>미평가</th><th>annex<br>complete</th><th>annex<br>별지없음</th>" +
    "<th>annex<br>partial</th><th>annex<br>미평가</th><th>coverage<br>행 없음</th></tr>";
  const body = names.map((name) => {
    const scope = families[name].target_scope || {};
    const b = scope.body || {};
    const a = scope.annex || {};
    const cells = [
      b.complete || 0, b.partial || 0, b.not_evaluated || 0,
      a.complete || 0, a.no_annex || 0, a.partial || 0, a.not_evaluated || 0,
      scope.no_coverage_row_not_evaluated || 0,
    ];
    return `<tr><th scope="row">${esc(name)}</th>` +
      cells.map((value) => `<td>${esc(value)}</td>`).join("") + "</tr>";
  }).join("");
  $("burndown-families").innerHTML = head + body;

  const absence = data.absence_eligibility || {};
  $("burndown-absence-summary").textContent =
    `(문서 × family) ${absence.pairs_total}쌍 중 부재 질의 가능 ${absence.absence_eligible}` +
    ` · 차단 ${absence.absence_blocked}` +
    ` · family 게이트: ${(absence.family_gated_families || []).join(", ") || "없음"}`;
  const reasons = absence.blocking_reasons || {};
  $("burndown-reasons").innerHTML = Object.keys(reasons).length
    ? Object.keys(reasons).map((key) =>
        `<div class="list-row"><span class="mono">${esc(key)}</span>` +
        `<strong>${esc(reasons[key])}</strong></div>`).join("")
    : `<p class="body-muted">차단 사유가 없습니다.</p>`;

  const backlog = data.taxonomy_backlog || {};
  const rw = data.rw_reextraction || {};
  const statusCounts = backlog.status_counts || {};
  const lines = Object.keys(statusCounts).map((key) =>
    [`후보 ${key}`, statusCounts[key]]);
  lines.push(["pending 중 부재 차단(blocking)", backlog.pending_blocking]);
  lines.push(["pending 중 비차단(one-off)", backlog.pending_non_blocking]);
  lines.push(["pending이 막는 문서 수", backlog.documents_blocked_by_pending]);
  lines.push([
    "RW 재추출 stored",
    rw.target_documents == null
      ? `미산출 — ${rw.target_documents_unavailable_reason || ""}`
      : `${rw.stored_documents}/${rw.target_documents} · ${pct(rw.percent)} (잔여 ${rw.remaining_audit_pending})`,
  ]);
  lines.push([
    "RW 재추출 결과 파일",
    rw.result_files == null
      ? `미산출 — ${rw.result_files_unavailable_reason || ""}`
      : rw.result_files,
  ]);
  $("burndown-backlog").innerHTML = lines.map(([label, value]) =>
    `<div class="list-row"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`
  ).join("");
}

function renderStatus(data) {
  const statuses = data.statuses || {};
  const total = Object.entries(statuses)
    .filter(([key]) => key !== "missing")
    .reduce((sum, [, count]) => sum + count, 0);
  const metrics = [
    ["전체", total],
    ["검색 가능", statuses.ok || 0],
    ["본문 없음", statuses.empty || 0],
    ["오류", statuses.error || 0],
    ["미지원", statuses.unsupported || 0],
  ];
  $("status-grid").innerHTML = metrics.map(([label, value]) =>
    `<div class="metric"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`
  ).join("");
  $("last-indexed").textContent = "마지막 색인: " + (data.last_indexed_at || "-");
}

function renderBatches(items) {
  $("batch-list").innerHTML = items.length ? items.map((item) =>
    `<div class="list-row"><span>${esc(item.batch_label)}</span><strong>${esc(item.count)}</strong></div>`
  ).join("") : `<p class="body-muted">batch 정보가 없습니다.</p>`;
}

function renderFailures(items) {
  $("failure-list").innerHTML = items.length ? items.map((item) =>
    `<div class="list-row vertical"><strong>${esc(item.status)} · ${esc(item.error_reason || "-")}</strong>` +
    `<span class="body-muted">${esc(item.path)}</span></div>`
  ).join("") : `<p class="body-muted">실패 문서가 없습니다.</p>`;
}

function renderFeedback(data) {
  const feedback = data.feedback || {};
  const parts = Object.keys(feedback).sort().map((key) =>
    `<div class="list-row"><span>${esc(key)}</span><strong>${esc(feedback[key])}</strong></div>`
  );
  parts.unshift(`<div class="list-row"><span>저장 검색</span><strong>${esc(data.saved_search_count || 0)}</strong></div>`);
  $("feedback-box").innerHTML = parts.join("");
}

function renderUnclassified(items) {
  $("unclassified-list").innerHTML = items.length ? items.map((item) =>
    `<div class="list-row"><span>${esc(item.folder)}</span><strong>${esc(item.count)}</strong></div>`
  ).join("") : `<p class="body-muted">미분류 폴더가 없습니다.</p>`;
}

function renderJobs(items) {
  $("job-list").innerHTML = items.length ? items.map((job) =>
    `<div class="list-row vertical"><strong>${esc(job.status)} · ${esc(job.kind)}</strong>` +
    `<span class="mono">${esc(job.id)}</span><span class="body-muted">${esc(job.message || "")}</span></div>`
  ).join("") : `<p class="body-muted">최근 작업이 없습니다.</p>`;
}
