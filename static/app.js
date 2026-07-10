/* 계약서 검색 UI-1 (read-only). 필터 옵션은 /api/search/facets에서 동적 로드 —
   하드코딩 금지. AI 호출·색인 실행·원본 수정 기능 없음. */
"use strict";

const state = {
  kw: [], type: "", lang: "", expand: "normal",
  excludeDrafts: false, showDuplicates: false,
  limit: 20, offset: 0, total: 0,
};

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value == null ? "" : value)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

/* ---------- init ---------- */
document.addEventListener("DOMContentLoaded", () => {
  loadCorpusStatus();
  loadFacets().then(() => {
    restoreFromUrl();
    if (state.kw.length || state.type || state.lang) runSearch(false);
  });
  bindEvents();
});

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let code = "INTERNAL_ERROR";
    try { code = (await response.json()).error.code; } catch (e) { /* ignore */ }
    throw new Error(code);
  }
  return response;
}

async function loadCorpusStatus() {
  try {
    const status = await (await api("/api/corpus/status")).json();
    const total = Object.entries(status.statuses)
      .filter(([key]) => key !== "missing")
      .reduce((sum, [, count]) => sum + count, 0);
    const banner = $("corpus-banner");
    const scope = status.pilot_corpus ? "파일럿 코퍼스 기준" : "현재 색인 기준";
    banner.textContent = `${scope} · 문서 ${total}건 (검색 가능 ${status.statuses.ok || 0}건, ` +
      `본문 추출 불가 ${status.unsearchable_docs}건) · 마지막 색인 ${status.last_indexed_at || "-"}`;
    banner.classList.toggle("pilot", status.pilot_corpus);
    banner.hidden = false;
  } catch (e) { /* 배너는 보조 정보 — 실패해도 검색은 가능 */ }
}

async function loadFacets() {
  try {
    const facets = await (await api("/api/search/facets")).json();
    fillSelect($("filter-type"), facets.ctype);
    fillSelect($("filter-lang"), facets.lang);
  } catch (e) { announce("필터 옵션을 불러오지 못했습니다"); }
}

function fillSelect(select, items) {
  for (const item of items || []) {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = `${item.value} (${item.count})`;
    select.appendChild(option);
  }
}

/* ---------- events ---------- */
function bindEvents() {
  const input = $("search-input");
  input.addEventListener("keydown", (event) => {
    // 한글 IME 조합 중 Enter는 검색 실행 금지 (isComposing / keyCode 229)
    if (event.key === "Enter") {
      if (event.isComposing || event.keyCode === 229) return;
      event.preventDefault();
      submitSearch();
    }
  });
  $("search-button").addEventListener("click", submitSearch);
  $("toggle-filters").addEventListener("click", () => {
    const panel = $("advanced-filters");
    panel.hidden = !panel.hidden;
    $("toggle-filters").setAttribute("aria-expanded", String(!panel.hidden));
  });
  for (const [id, key] of [["filter-type", "type"], ["filter-lang", "lang"], ["filter-expand", "expand"]]) {
    $(id).addEventListener("change", (event) => { state[key] = event.target.value; submitSearch(); });
  }
  $("filter-drafts").addEventListener("change", (e) => { state.excludeDrafts = e.target.checked; submitSearch(); });
  $("filter-dups").addEventListener("change", (e) => { state.showDuplicates = e.target.checked; submitSearch(); });
  $("more-button").addEventListener("click", () => { state.offset += state.limit; runSearch(true); });
  $("export-md").addEventListener("click", () => exportResults("markdown", "search_export.md"));
  $("export-csv").addEventListener("click", () => exportResults("csv", "search_export.csv"));

  // j/k 결과 카드 이동 — 입력창/셀렉트 포커스 중에는 비활성화
  document.addEventListener("keydown", (event) => {
    const tag = (event.target.tagName || "").toLowerCase();
    if (event.isComposing || ["input", "select", "textarea"].includes(tag)) return;
    if (event.key !== "j" && event.key !== "k") return;
    const cards = Array.from(document.querySelectorAll(".result-card"));
    if (!cards.length) return;
    const current = cards.indexOf(document.activeElement);
    const next = event.key === "j" ? Math.min(current + 1, cards.length - 1) : Math.max(current - 1, 0);
    cards[next].focus();
    event.preventDefault();
  });
  window.addEventListener("popstate", () => { restoreFromUrl(); runSearch(false, true); });
}

function submitSearch() {
  const raw = $("search-input").value;
  state.kw = raw.split(",").map((term) => term.trim()).filter(Boolean);
  state.offset = 0;
  runSearch(false);
}

/* ---------- URL 상태 (query/filters/expand_mode) ---------- */
function updateUrl() {
  const params = new URLSearchParams();
  state.kw.forEach((term) => params.append("kw", term));
  if (state.type) params.set("type", state.type);
  if (state.lang) params.set("lang", state.lang);
  if (state.expand !== "normal") params.set("expand", state.expand);
  if (state.excludeDrafts) params.set("exclude_drafts", "1");
  if (state.showDuplicates) params.set("show_duplicates", "1");
  const search = params.toString();
  history.pushState(null, "", search ? `/?${search}` : "/");
}

function restoreFromUrl() {
  const params = new URLSearchParams(location.search);
  state.kw = params.getAll("kw");
  state.type = params.get("type") || "";
  state.lang = params.get("lang") || "";
  state.expand = ["strict", "normal", "broad"].includes(params.get("expand")) ? params.get("expand") : "normal";
  state.excludeDrafts = params.get("exclude_drafts") === "1";
  state.showDuplicates = params.get("show_duplicates") === "1";
  state.offset = 0;
  $("search-input").value = state.kw.join(", ");
  $("filter-type").value = state.type;
  $("filter-lang").value = state.lang;
  $("filter-expand").value = state.expand;
  $("filter-drafts").checked = state.excludeDrafts;
  $("filter-dups").checked = state.showDuplicates;
}

/* ---------- 검색 ---------- */
function searchBody() {
  return {
    kw: state.kw, type: state.type || null, lang: state.lang || null,
    expand: state.expand, exclude_drafts: state.excludeDrafts,
    show_duplicates: state.showDuplicates, limit: state.limit, offset: state.offset,
  };
}

async function runSearch(append, skipUrl) {
  if (!append && !skipUrl) updateUrl();
  renderChips();
  try {
    const data = await (await api("/api/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(searchBody()),
    })).json();
    state.total = data.total;
    renderSummary(data);
    renderResults(data, append);
    announce(`검색 완료: 대표 ${data.total}건, 전체 파일 ${data.total_files}건`);
  } catch (error) {
    announce("검색 실패: " + error.message);
    $("summary-text").textContent = "검색 중 오류가 발생했습니다 (" + error.message + ")";
    $("summary-row").hidden = false;
  }
}

function renderChips() {
  const chips = [];
  state.kw.forEach((term, index) => chips.push({ label: term, undo: () => state.kw.splice(index, 1) }));
  if (state.type) chips.push({ label: state.type, undo: () => { state.type = ""; $("filter-type").value = ""; } });
  if (state.lang) chips.push({ label: state.lang, undo: () => { state.lang = ""; $("filter-lang").value = ""; } });
  if (state.expand !== "normal") chips.push({
    label: "확장: " + ({ strict: "정확하게", broad: "넓게" }[state.expand]),
    undo: () => { state.expand = "normal"; $("filter-expand").value = "normal"; },
  });
  if (state.excludeDrafts) chips.push({ label: "Draft 제외", undo: () => { state.excludeDrafts = false; $("filter-drafts").checked = false; } });
  if (state.showDuplicates) chips.push({ label: "중복본 펼침", undo: () => { state.showDuplicates = false; $("filter-dups").checked = false; } });

  const box = $("filter-chips");
  box.innerHTML = "";
  for (const chip of chips) {
    const el = document.createElement("span");
    el.className = "chip";
    el.innerHTML = esc(chip.label) + ' <button type="button" aria-label="필터 제거: ' + esc(chip.label) + '">×</button>';
    el.querySelector("button").addEventListener("click", () => {
      chip.undo(); state.offset = 0;
      $("search-input").value = state.kw.join(", ");
      runSearch(false);
    });
    box.appendChild(el);
  }
}

const WARNING_LABELS = {
  short_term_fallback: (value) => `2글자 검색어 폴백: ${value}`,
  unsearchable_docs: (value) => `본문 검색 불가 문서 ${value}건`,
  term_dict_not_found: () => "동의어 사전 미발견",
};

function renderSummary(data) {
  $("summary-row").hidden = false;
  $("summary-text").textContent =
    `결과 ${data.total}건 · 전체 파일 ${data.total_files}건 · ${data.offset + 1}~${data.offset + data.results.length}건 표시`;
  const badges = $("warning-badges");
  badges.innerHTML = "";
  for (const warning of data.warnings || []) {
    const [kind, value] = warning.split(":");
    const label = WARNING_LABELS[kind] ? WARNING_LABELS[kind](value) : warning;
    const badge = document.createElement("span");
    badge.className = "badge-warning";
    badge.textContent = label;
    badges.appendChild(badge);
  }
  $("export-md").disabled = $("export-csv").disabled = data.total === 0;
}

function renderResults(data, append) {
  const box = $("results");
  if (!append) box.innerHTML = "";
  for (const item of data.results) box.appendChild(resultCard(item));
  $("empty-state").hidden = data.total !== 0;
  $("more-button").hidden = data.offset + data.results.length >= data.total;
}

function resultCard(item) {
  const card = document.createElement("article");
  card.className = "result-card";
  card.tabIndex = -1;

  const badges = [];
  const score = item.score_breakdown || {};
  if (score.exact_rank != null) badges.push('<span class="badge exact">정확 매칭</span>');
  if (score.expanded_rank != null)
    badges.push(`<span class="badge ${state.expand === "broad" ? "broad" : ""}">` +
      (state.expand === "broad" ? "넓은 확장 매칭" : "동의어 매칭") + "</span>");
  if (item.is_draft === 1) badges.push('<span class="badge draft">Draft</span>');
  if (item.is_draft == null) badges.push('<span class="badge draft">Draft 판별불가</span>');
  if (item.dup_count > 1) badges.push(`<span class="badge">중복 ${item.dup_count}건 중 대표본</span>`);

  const whyItems = (item.why || []).map((reason) => `<li>${esc(reason)}</li>`).join("");
  const scoreText = `exact_rank=${score.exact_rank ?? "—"} · expanded_rank=${score.expanded_rank ?? "—"}` +
    ` · rrf=${score.rrf_score ?? "—"}`;
  const paras = (item.snippet_paras || []).map((p) => "¶" + p).join(" ");

  card.innerHTML =
    `<h3>[${esc(item.ctype)}] ${esc(item.path)}</h3>` +
    `<div class="result-key">${esc(item.file_key)} · ${esc(item.lang)}` +
    (item.version_hint ? ` · ${esc(item.version_hint)}` : "") + `</div>` +
    `<div class="result-meta">${badges.join(" ")}</div>` +
    (whyItems ? `<div class="body-muted">왜 검색됐나</div><ul class="why">${whyItems}</ul>` : "") +
    `<div class="score">${esc(scoreText)} · 매칭 문단: ${esc(paras) || "—"}</div>` +
    (item.snippet ? `<div class="snippet">${esc(item.snippet)}</div>` : "") +
    `<div class="card-actions">` +
    `<button type="button" class="button-ghost-sm act-context">문단 주변 보기</button>` +
    (item.dup_count > 1 ? `<button type="button" class="button-ghost-sm act-dups">중복본 보기</button>` : "") +
    `</div><div class="detail-panel" hidden></div>`;

  const panel = card.querySelector(".detail-panel");
  card.querySelector(".act-context").addEventListener("click",
    () => toggleContext(item, panel));
  const dupButton = card.querySelector(".act-dups");
  if (dupButton) dupButton.addEventListener("click", () => toggleDuplicates(item, panel));
  return card;
}

async function toggleContext(item, panel) {
  if (!panel.hidden && panel.dataset.mode === "context") { panel.hidden = true; return; }
  const para = (item.snippet_paras || [])[0];
  if (para == null) { announce("표시할 매칭 문단이 없습니다"); return; }
  try {
    const data = await (await api(
      `/api/files/${item.file_key}/context?para=${para}&context=3`)).json();
    panel.innerHTML = data.paragraphs.map((paragraph) =>
      `<div class="snippet${paragraph.para === para ? " current" : ""}">[¶${paragraph.para}] ${esc(paragraph.text)}</div>`
    ).join("");
    panel.dataset.mode = "context";
    panel.hidden = false;
  } catch (error) { announce("문단을 불러오지 못했습니다: " + error.message); }
}

async function toggleDuplicates(item, panel) {
  if (!panel.hidden && panel.dataset.mode === "dups") { panel.hidden = true; return; }
  try {
    const data = await (await api(`/api/files/${item.file_key}/duplicates`)).json();
    panel.innerHTML = `<div class="body-muted">같은 내용의 문서 ${data.count}건</div>` +
      data.members.map((member) =>
        `<div class="dup-row"><span class="mono">${esc(member.file_key)}</span> ${esc(member.path)}` +
        (member.is_draft === 1 ? ' <span class="badge draft">Draft</span>' : "") +
        (member.version_hint ? ` <span class="badge">${esc(member.version_hint)}</span>` : "") +
        `</div>`).join("");
    panel.dataset.mode = "dups";
    panel.hidden = false;
  } catch (error) { announce("중복본을 불러오지 못했습니다: " + error.message); }
}

/* ---------- export ---------- */
async function exportResults(kind, filename) {
  try {
    const body = Object.assign(searchBody(), { offset: 0, limit: 100 });
    const response = await api(`/api/export/${kind}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
    announce("내보내기 완료: " + filename);
  } catch (error) { announce("내보내기 실패: " + error.message); }
}

function announce(message) { $("live").textContent = message; }
