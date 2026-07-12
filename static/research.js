"use strict";

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value == null ? "" : value)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error("request failed");
  return response.json();
}

document.addEventListener("DOMContentLoaded", () => {
  $("session-form").addEventListener("submit", createSession);
  loadResearch();
});

async function loadResearch() {
  try {
    const [saved, marks, compare, sessions] = await Promise.all([
      api("/api/saved-searches"),
      api("/api/marks"),
      api("/api/compare/default"),
      api("/api/research/sessions"),
    ]);
    renderSaved(saved.items || []);
    renderMarks(marks.items || []);
    renderCompare(compare.items || []);
    renderSessions(sessions.items || []);
    $("live").textContent = "리서치 보드를 불러왔습니다.";
  } catch (error) {
    $("live").textContent = "리서치 보드를 불러오지 못했습니다.";
  }
}

function renderSaved(items) {
  $("saved-searches").innerHTML = items.length ? items.map((item) =>
    `<div class="list-row vertical"><strong>${esc(item.name)}</strong>` +
    `<span class="body-muted">${esc(item.query || "(필터 검색)")}</span>` +
    `<a class="nav-link" href="/?${savedQueryString(item)}">검색 열기</a></div>`
  ).join("") : `<p class="body-muted">저장된 검색이 없습니다. 검색 화면에서 저장할 수 있습니다.</p>`;
}

function savedQueryString(item) {
  const params = new URLSearchParams();
  const filters = item.filters || {};
  const kw = Array.isArray(filters.kw) ? filters.kw : (item.query ? [item.query] : []);
  kw.forEach((term) => params.append("kw", term));
  if (filters.type) params.set("type", filters.type);
  if (filters.lang) params.set("lang", filters.lang);
  if (item.expand_mode && item.expand_mode !== "normal") params.set("expand", item.expand_mode);
  if (filters.exclude_drafts) params.set("exclude_drafts", "1");
  if (filters.show_duplicates) params.set("show_duplicates", "1");
  return params.toString();
}

function renderMarks(items) {
  $("marks").innerHTML = items.length ? items.map((item) =>
    `<div class="list-row vertical"><strong>${esc(item.mark_type)} · ${esc(item.file_key)}` +
    `${item.para ? " ¶" + esc(item.para) : ""}</strong>` +
    `<span class="body-muted">${esc(item.note || "")}</span></div>`
  ).join("") : `<p class="body-muted">북마크나 메모가 없습니다.</p>`;
}

function renderCompare(items) {
  $("compare-items").innerHTML = items.length ? items.map((item) => {
    const file = item.file || {};
    return `<div class="list-row vertical"><strong>${esc(item.file_key)}${item.para ? " ¶" + esc(item.para) : ""}</strong>` +
      `<span>${esc(file.path || "")}</span><span class="body-muted">${esc(item.note || "")}</span></div>`;
  }).join("") : `<p class="body-muted">비교 목록이 비어 있습니다. 검색 결과에서 추가할 수 있습니다.</p>`;
}

function renderSessions(items) {
  $("sessions").innerHTML = items.length ? items.map((item) =>
    `<div class="list-row vertical"><strong>${esc(item.name)}</strong>` +
    `<span class="body-muted">${esc(item.note || "")}</span>` +
    `<span class="mono">${esc(item.updated_at)}</span></div>`
  ).join("") : `<p class="body-muted">리서치 세션이 없습니다.</p>`;
}

async function createSession(event) {
  event.preventDefault();
  const name = $("session-name").value.trim();
  if (!name) return;
  try {
    await api("/api/research/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    $("session-name").value = "";
    loadResearch();
  } catch (error) {
    $("live").textContent = "세션을 만들지 못했습니다.";
  }
}
