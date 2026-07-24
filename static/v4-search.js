const $ = (selector) => document.querySelector(selector);
let nodes = [];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: {"Content-Type": "application/json"},
    ...options
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error?.message || "요청에 실패했습니다.");
  return payload;
}

function fillNodes() {
  const family = $("#family").value;
  const selected = $("#taxonomy").value;
  const visible = nodes.filter((node) => !family || node.family === family);
  $("#taxonomy").innerHTML = visible.map((node) =>
    `<option value="${escapeHtml(node.taxonomy_id)}">${escapeHtml(node.taxonomy_id)} · ${escapeHtml(node.canonical_ko)}</option>`
  ).join("");
  if (visible.some((node) => node.taxonomy_id === selected)) $("#taxonomy").value = selected;
}

function cardForItem(item) {
  const review = item.freshness !== "current" || item.coverage?.state !== "complete";
  return `<article class="${review ? "review" : ""}">
    <div class="meta">
      <span class="badge">${review ? "재확인 필요" : "현재 원문"}</span>
      <span class="code">[${escapeHtml(item.file_key)}]</span>
      <span>${escapeHtml(item.ctype)} · ${escapeHtml(item.lang)}</span>
      <span class="code">${escapeHtml(item.taxonomy_id)}</span>
      <span>¶${item.loc_start}–${item.loc_end}</span>
      <span>${escapeHtml(item.source_kind)}${item.source_name ? ` · ${escapeHtml(item.source_name)}` : ""}</span>
    </div>
    <div class="proposition">${escapeHtml(item.proposition)}</div>
    <blockquote>${escapeHtml(item.verbatim)}</blockquote>
  </article>`;
}

function cardForCoverage(item) {
  const review = item.state === "needs_review";
  const reasons = item.coverage?.reasons?.join(", ") || "본문·별지 평가 완료";
  return `<article class="${review ? "review" : ""}">
    <div class="meta">
      <span class="badge">${review ? "미평가/확인 필요" : "부재 확인"}</span>
      <span class="code">[${escapeHtml(item.file_key)}]</span>
      <span>${escapeHtml(item.ctype)} · ${escapeHtml(item.lang)}</span>
      <span>${escapeHtml(item.path)}</span>
    </div>
    <div class="proposition">${escapeHtml(item.state)}</div>
    <div>${escapeHtml(reasons)}</div>
  </article>`;
}

async function runSearch(event) {
  event.preventDefault();
  $("#notice").textContent = "검색 중…";
  $("#results").innerHTML = "";
  const mode = $("#mode").value;
  const body = {
    mode,
    taxonomy_id: $("#taxonomy").value,
    polarity: $("#polarity").value || null,
    lang: $("#lang").value || null,
    ctype: $("#ctype").value.trim() || null,
    subject: $("#subject").value.trim() || null,
    effective_time: $("#effective-time").value.trim() || null,
    text: $("#text").value.trim() || null,
    include_descendants: $("#descendants").checked,
    limit: 100
  };
  try {
    const data = await request("/api/v4/items/search", {
      method: "POST", body: JSON.stringify(body)
    });
    if (mode === "present") {
      $("#summary").textContent = `${data.query.taxonomy_id} · ${data.total_documents}개 문서 · ${data.total_items}개 원자 항목`;
      $("#results").innerHTML = data.results.map(cardForItem).join("") || "<article>확인된 항목이 없습니다.</article>";
    } else {
      $("#summary").textContent = `${data.query.taxonomy_id} · 부재 확인 ${data.confirmed_absent_count}개 · 확인 필요 ${data.needs_review_count}개`;
      const all = [...data.confirmed_absent, ...data.needs_review];
      $("#results").innerHTML = all.map(cardForCoverage).join("") || "<article>대상 문서가 없습니다.</article>";
    }
    $("#notice").textContent = "";
  } catch (error) {
    $("#notice").textContent = error.message;
  }
}

async function init() {
  try {
    const data = await request("/api/v4/taxonomy/nodes");
    nodes = data.nodes;
    fillNodes();
  } catch (error) {
    $("#notice").textContent = error.message;
  }
  $("#family").addEventListener("change", fillNodes);
  $("#mode").addEventListener("change", () => {
    document.querySelectorAll(".present-only").forEach((node) => {
      node.hidden = $("#mode").value !== "present";
    });
  });
  $("#search-form").addEventListener("submit", runSearch);
}

init();
