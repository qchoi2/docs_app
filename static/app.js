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

/* 매칭어 하이라이트 — 검색은 normalize() 텍스트 기준이고 화면은 원문 표면형이라
   표면형 매칭이 실패할 수 있다. 실패는 오류가 아니며, 하이라이트 없이 원문을
   그대로 표시한다(하이라이트를 위해 원문을 변형하지 않는다). */
const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function highlightHtml(text, terms) {
  const raw = String(text == null ? "" : text);
  const list = [...new Set((terms || []).filter((t) => t && t.length >= 2))]
    .sort((a, b) => b.length - a.length);
  if (!list.length || !raw) return esc(raw);
  let re;
  try { re = new RegExp(list.map(escRe).join("|"), "gi"); } catch (e) { return esc(raw); }
  let out = "", last = 0, m;
  while ((m = re.exec(raw)) !== null) {
    if (!m[0]) { re.lastIndex += 1; continue; }
    out += esc(raw.slice(last, m.index)) + "<mark>" + esc(m[0]) + "</mark>";
    last = m.index + m[0].length;
  }
  return out + esc(raw.slice(last));
}

function itemTerms(item) {
  return (item.matched_terms || []).map((t) => t.term).concat(state.kw);
}

/* 표준 오류 코드(BACKEND_REVIEW §2.9) → 사용자 메시지. raw 코드/트레이스 비노출. */
const ERROR_MESSAGES = {
  VALIDATION_ERROR: "요청 값이 올바르지 않습니다",
  FILE_NOT_FOUND_IN_CATALOG: "카탈로그에서 문서를 찾지 못했습니다",
  SQLITE_BUSY: "데이터베이스가 잠시 사용 중입니다 — 다시 시도하세요",
  INTERNAL_ERROR: "서버 오류가 발생했습니다",
  NOT_FOUND: "요청한 경로가 없습니다",
};
const errMsg = (code) => ERROR_MESSAGES[code] || `오류 (${code})`;

/* ---------- init ---------- */
document.addEventListener("DOMContentLoaded", () => {
  loadCorpusStatus();
  loadRecentSearches();
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
    if (total === 0) {
      banner.innerHTML = '색인된 문서가 없습니다 — <a class="nav-link" href="/setup">색인/설정</a>에서 최초 색인을 실행하세요.';
    }
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
    if (!append) loadRecentSearches();
  } catch (error) {
    announce("검색 실패: " + errMsg(error.message));
    $("summary-text").textContent = "검색 실패: " + errMsg(error.message);
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
    (item.snippet ? `<div class="snippet">${highlightHtml(item.snippet, itemTerms(item))}</div>` : "") +
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
  await renderContext(item, panel, 3);
}

async function renderContext(item, panel, context) {
  const para = (item.snippet_paras || [])[0];
  if (para == null) { announce("표시할 매칭 문단이 없습니다"); return; }
  try {
    const data = await (await api(
      `/api/files/${item.file_key}/context?para=${para}&context=${context}`)).json();
    const terms = itemTerms(item);
    panel.innerHTML = data.paragraphs.map((paragraph) =>
      `<div class="snippet${paragraph.para === para ? " current" : ""}">[¶${paragraph.para}] ${highlightHtml(paragraph.text, terms)}</div>`
    ).join("") +
      `<div class="card-actions">` +
      (context < 10 ? `<button type="button" class="button-ghost-sm act-wider">앞뒤 더 보기</button>` : "") +
      `<button type="button" class="button-ghost-sm act-copy-para">¶번호 복사</button>` +
      `<button type="button" class="button-ghost-sm act-copy-path">원본 경로 복사</button></div>`;
    const wider = panel.querySelector(".act-wider");
    if (wider) wider.addEventListener("click", () => renderContext(item, panel, Math.min(context + 3, 10)));
    panel.querySelector(".act-copy-para").addEventListener("click",
      () => copyText(`[${item.file_key}] ¶${para}`));
    panel.querySelector(".act-copy-path").addEventListener("click",
      () => copyText(item.path));
    panel.dataset.mode = "context";
    panel.hidden = false;
  } catch (error) { announce("문단을 불러오지 못했습니다: " + errMsg(error.message)); }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    announce("복사됨: " + text);
  } catch (e) { announce("복사하지 못했습니다 — 브라우저 권한을 확인하세요"); }
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
  } catch (error) { announce("중복본을 불러오지 못했습니다: " + errMsg(error.message)); }
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
  } catch (error) { announce("내보내기 실패: " + errMsg(error.message)); }
}

/* ---------- 최근 검색 (ui_state.sqlite 영속 — query_log와 별개) ---------- */
async function loadRecentSearches() {
  try {
    const data = await (await api("/api/history/recent?limit=10")).json();
    renderRecentSearches(data.items || []);
  } catch (error) { /* 최근 검색은 보조 기능 — 실패해도 검색은 가능 */ }
}

function renderRecentSearches(items) {
  const box = $("recent-searches");
  const list = $("recent-list");
  list.innerHTML = "";
  box.hidden = items.length === 0;
  for (const item of items) {
    const label = describeHistoryItem(item);
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.innerHTML = esc(label) +
      (item.result_count != null ? ` <span class="count">${item.result_count}건</span>` : "");
    chip.title = new Date(item.ts).toLocaleString();
    chip.addEventListener("click", () => applyHistoryItem(item));
    list.appendChild(chip);
  }
}

function describeHistoryItem(item) {
  const filters = item.filters || {};
  const parts = [];
  if (item.query) parts.push(item.query);
  if (filters.type) parts.push(filters.type);
  if (filters.lang) parts.push(filters.lang);
  if (item.expand_mode && item.expand_mode !== "normal")
    parts.push({ strict: "정확하게", broad: "넓게" }[item.expand_mode] || item.expand_mode);
  if (filters.exclude_drafts) parts.push("Draft 제외");
  return parts.join(" · ") || "(빈 검색)";
}

function applyHistoryItem(item) {
  const filters = item.filters || {};
  state.kw = Array.isArray(filters.kw) ? filters.kw.slice() : [];
  state.type = filters.type || "";
  state.lang = filters.lang || "";
  state.expand = ["strict", "normal", "broad"].includes(item.expand_mode) ? item.expand_mode : "normal";
  state.excludeDrafts = Boolean(filters.exclude_drafts);
  state.showDuplicates = Boolean(filters.show_duplicates);
  state.offset = 0;
  $("search-input").value = state.kw.join(", ");
  $("filter-type").value = state.type;
  $("filter-lang").value = state.lang;
  $("filter-expand").value = state.expand;
  $("filter-drafts").checked = state.excludeDrafts;
  $("filter-dups").checked = state.showDuplicates;
  runSearch(false);   // updateUrl()이 URL도 복원한다
}

function announce(message) { $("live").textContent = message; }
