"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  summary: null,
  clusters: [],
  nodes: [],
  selected: new Map(),
  status: "pending",
  family: "",
  query: "",
  limit: 50,
  offset: 0,
  activeAction: null,
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || data.error) {
    throw new Error(data.error?.message || `HTTP ${response.status}`);
  }
  return data;
}

function selectedClusters() {
  return [...state.selected.values()];
}

function selectedIds() {
  return selectedClusters().flatMap((cluster) => cluster.candidate_ids);
}

function selectedFamily() {
  const families = new Set(selectedClusters().map((cluster) => cluster.family));
  return families.size === 1 ? [...families][0] : null;
}

function renderSummary() {
  const summary = state.summary;
  $("version-badge").textContent = `taxonomy v${summary.taxonomy_version}`;
  const pending = summary.candidate_status_counts.pending || 0;
  const resolved = ["merged", "approved", "rejected"]
    .reduce((sum, key) => sum + (summary.candidate_status_counts[key] || 0), 0);
  const cards = [
    ["활성 노드", summary.node_count],
    ["검토 대기 후보", pending],
    ["처리 완료", resolved],
    ["최근 작업", summary.recent_actions.length],
  ];
  $("summary-grid").innerHTML = cards.map(([label, value]) =>
    `<article class="summary-card"><span>${esc(label)}</span><strong>${esc(value)}</strong></article>`
  ).join("");
}

function renderCandidates(result) {
  state.clusters = result.clusters;
  $("result-count").textContent =
    `${result.total_clusters}개 묶음 · ${result.total_candidates}개 후보`;
  if (!result.clusters.length) {
    $("candidate-list").innerHTML =
      '<div class="empty-state">조건에 맞는 후보가 없습니다.</div>';
  } else {
    $("candidate-list").innerHTML = result.clusters.map((cluster) => {
      const checked = state.selected.has(cluster.cluster_key);
      const evidence = cluster.evidence.map((row) =>
        `<li><span class="mono">[${esc(row.file_key)}] ¶${row.loc_start}` +
        `${row.loc_end !== row.loc_start ? `–¶${row.loc_end}` : ""}</span> ${esc(row.path)}</li>`
      ).join("");
      const nearest = cluster.nearest_taxonomy_id
        ? `<div class="nearest-node">근접 노드 <strong class="mono">${esc(cluster.nearest_taxonomy_id)}</strong>` +
          ` · ${esc(cluster.nearest_ko || cluster.nearest_en || "")}</div>`
        : "";
      return `<article class="candidate-card ${checked ? "selected" : ""}" data-key="${cluster.cluster_key}">
        <input class="cluster-check" type="checkbox" ${checked ? "checked" : ""}
          aria-label="후보 묶음 선택" data-key="${cluster.cluster_key}">
        <div>
          <div class="candidate-meta">
            <span class="family-badge">${esc(cluster.family)}</span>
            <span class="badge">${cluster.candidate_count}개 후보</span>
            <span class="badge">${cluster.document_count}개 문서</span>
            <span class="mono muted">${esc(cluster.cluster_key)}</span>
          </div>
          <h3>${esc(cluster.verbatim)}</h3>
          <p class="candidate-reason">${esc(cluster.distinction_reason)}</p>
          ${nearest}
          <ul class="evidence-list">${evidence}</ul>
        </div>
      </article>`;
    }).join("");
  }
  document.querySelectorAll(".cluster-check").forEach((input) => {
    input.addEventListener("change", () => toggleCluster(input.dataset.key, input.checked));
  });
  const page = Math.floor(result.offset / result.limit) + 1;
  const pages = Math.max(1, Math.ceil(result.total_clusters / result.limit));
  $("page-status").textContent = `${page} / ${pages}`;
  $("previous-page").disabled = result.offset === 0;
  $("next-page").disabled = result.offset + result.limit >= result.total_clusters;
  $("select-visible").checked = Boolean(result.clusters.length) &&
    result.clusters.every((cluster) => state.selected.has(cluster.cluster_key));
  updateSelection();
}

function toggleCluster(key, checked) {
  const cluster = state.clusters.find((row) => row.cluster_key === key);
  if (!cluster) return;
  if (checked) state.selected.set(key, cluster);
  else state.selected.delete(key);
  const card = document.querySelector(`.candidate-card[data-key="${key}"]`);
  if (card) card.classList.toggle("selected", checked);
  updateSelection();
}

function updateSelection() {
  const clusters = selectedClusters();
  const ids = selectedIds();
  const family = selectedFamily();
  $("selection-summary").textContent = clusters.length
    ? `${clusters.length}개 묶음 · ${ids.length}개 후보 선택` +
      (family ? ` · ${family}` : " · 여러 family")
    : "선택 없음";
  const canAct = ids.length > 0 && Boolean(family) && state.status === "pending";
  ["merge-open", "promote-open", "reject-open"].forEach((id) => {
    $(id).disabled = !canAct;
  });
}

async function loadSummary() {
  state.summary = await api("/api/v4/taxonomy/summary");
  renderSummary();
}

async function loadNodes() {
  const data = await api("/api/v4/taxonomy/nodes");
  state.nodes = data.nodes;
}

async function loadCandidates() {
  const params = new URLSearchParams({
    status: state.status,
    limit: String(state.limit),
    offset: String(state.offset),
  });
  if (state.family) params.set("family", state.family);
  if (state.query) params.set("q", state.query);
  $("candidate-list").innerHTML = '<div class="empty-state">후보를 불러오는 중입니다.</div>';
  const result = await api(`/api/v4/taxonomy/candidates?${params}`);
  renderCandidates(result);
}

async function reloadAll() {
  await Promise.all([loadSummary(), loadNodes(), loadCandidates()]);
}

function nodeOptions(family, includeLeavesOnly = false, needle = "") {
  const query = needle.trim().toLowerCase();
  return state.nodes.filter((node) =>
    node.family === family &&
    (!includeLeavesOnly || node.is_leaf) &&
    (!query || `${node.taxonomy_id} ${node.canonical_ko} ${node.canonical_en}`.toLowerCase().includes(query))
  );
}

function fillNodeSelect(select, nodes) {
  select.innerHTML = nodes.map((node) =>
    `<option value="${esc(node.taxonomy_id)}">${esc(node.taxonomy_id)} · ${esc(node.canonical_ko)}</option>`
  ).join("");
}

function openAction(action) {
  const clusters = selectedClusters();
  const family = selectedFamily();
  if (!clusters.length || !family) return;
  state.activeAction = action;
  $("action-panel").hidden = false;
  $("merge-form").hidden = action !== "merge";
  $("promote-form").hidden = action !== "promote";
  $("reject-form").hidden = action !== "reject";
  $("action-message").textContent = "";
  $("action-message").className = "form-message";
  $("action-title").textContent = {
    merge: "기존 노드 귀속", promote: "신규 노드 승격", reject: "후보 기각",
  }[action];
  $("action-context").textContent =
    `${family} · ${clusters.length}개 묶음 · ${selectedIds().length}개 후보를 처리합니다.`;
  if (action === "merge") {
    fillNodeSelect($("merge-node"), nodeOptions(family, true));
  }
  if (action === "promote") {
    fillNodeSelect(
      $("promote-parent"),
      state.nodes.filter((node) => node.family === family && !node.is_leaf),
    );
    const first = clusters[0];
    $("promote-id").value = `${family}.`;
    $("promote-ko").value =
      first.proposed_ko?.replace(/^(?:검토후보|정의용어 후보):\s*/, "") || "";
    $("promote-en").value = first.proposed_en || "";
    $("promote-definition").value = "";
    $("promote-aliases").value = clusters
      .map((row) => row.verbatim)
      .filter((value) => value.length <= 200)
      .join("\n");
  }
}

function closeAction() {
  $("action-panel").hidden = true;
  state.activeAction = null;
}

async function resolve(payload, confirmText) {
  if (!window.confirm(confirmText)) return;
  const message = $("action-message");
  message.textContent = "저장 중…";
  message.className = "form-message";
  try {
    const result = await api("/api/v4/taxonomy/candidates/resolve", {
      method: "POST",
      body: JSON.stringify({ ...payload, candidate_ids: selectedIds() }),
    });
    message.textContent = `${result.resolved_count}개 후보를 처리했습니다.`;
    state.selected.clear();
    closeAction();
    await reloadAll();
  } catch (error) {
    message.textContent = error.message;
    message.className = "form-message error";
  }
}

function bind() {
  $("refresh-button").addEventListener("click", reloadAll);
  $("apply-filter").addEventListener("click", () => {
    state.status = $("status-filter").value;
    state.family = $("family-filter").value;
    state.query = $("query-filter").value.trim();
    state.offset = 0;
    state.selected.clear();
    closeAction();
    loadCandidates();
  });
  $("query-filter").addEventListener("keydown", (event) => {
    if (event.key === "Enter") $("apply-filter").click();
  });
  $("select-visible").addEventListener("change", (event) => {
    state.clusters.forEach((cluster) => {
      if (event.target.checked) state.selected.set(cluster.cluster_key, cluster);
      else state.selected.delete(cluster.cluster_key);
    });
    renderCandidates({
      clusters: state.clusters,
      total_clusters: state.clusters.length,
      total_candidates: state.clusters.reduce((sum, row) => sum + row.candidate_count, 0),
      limit: state.limit, offset: state.offset,
    });
  });
  $("previous-page").addEventListener("click", () => {
    state.offset = Math.max(0, state.offset - state.limit);
    loadCandidates();
  });
  $("next-page").addEventListener("click", () => {
    state.offset += state.limit;
    loadCandidates();
  });
  $("merge-open").addEventListener("click", () => openAction("merge"));
  $("promote-open").addEventListener("click", () => openAction("promote"));
  $("reject-open").addEventListener("click", () => openAction("reject"));
  $("action-close").addEventListener("click", closeAction);
  $("merge-node-search").addEventListener("input", (event) => {
    fillNodeSelect($("merge-node"), nodeOptions(selectedFamily(), true, event.target.value));
  });
  $("merge-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const taxonomyId = $("merge-node").value;
    if (!taxonomyId) return;
    resolve({
      action: "merge",
      taxonomy_id: taxonomyId,
      reason: $("merge-reason").value.trim(),
    }, `${selectedIds().length}개 후보를 ${taxonomyId}에 귀속할까요?`);
  });
  $("promote-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const taxonomyId = $("promote-id").value.trim().toUpperCase();
    resolve({
      action: "promote",
      taxonomy_id: taxonomyId,
      parent_id: $("promote-parent").value,
      canonical_ko: $("promote-ko").value.trim(),
      canonical_en: $("promote-en").value.trim(),
      definition: $("promote-definition").value.trim(),
      aliases: $("promote-aliases").value.split("\n").map((value) => value.trim()).filter(Boolean),
      reason: $("promote-reason").value.trim(),
    }, `${taxonomyId} 신규 노드를 만들고 ${selectedIds().length}개 후보를 승격할까요?`);
  });
  $("reject-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const reason = $("reject-reason").value.trim();
    if (!reason) return;
    resolve({ action: "reject", reason },
      `${selectedIds().length}개 후보를 기각할까요? 원문 증거와 작업 로그는 보존됩니다.`);
  });
}

bind();
reloadAll().catch((error) => {
  $("candidate-list").innerHTML = `<div class="empty-state">${esc(error.message)}</div>`;
});
