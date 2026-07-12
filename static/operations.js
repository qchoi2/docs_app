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
