const state = {
  data: null,
  filter: "",
  sort: {
    buy: { key: "strength", dir: "desc", type: "number" },
    sell: { key: "dayChangePct", dir: "asc", type: "number" }
  }
};

const SORT_LABELS = {
  name: "名称",
  price: "最新价",
  dayChangePct: "当日涨跌",
  tempChange: "温度变化",
  phase: "节气",
  strength: "相对强度",
  strengthChange: "强度变化"
};

const elements = {
  heroDate: document.getElementById("heroDate"),
  heroStatus: document.getElementById("heroStatus"),
  statDate: document.getElementById("statDate"),
  statTime: document.getElementById("statTime"),
  buyCount: document.getElementById("buyCount"),
  sellCount: document.getElementById("sellCount"),
  buyVisible: document.getElementById("buyVisible"),
  sellVisible: document.getElementById("sellVisible"),
  buyBody: document.getElementById("buyBody"),
  sellBody: document.getElementById("sellBody"),
  buyEmpty: document.getElementById("buyEmpty"),
  sellEmpty: document.getElementById("sellEmpty"),
  buySortHint: document.getElementById("buySortHint"),
  sellSortHint: document.getElementById("sellSortHint"),
  staleBanner: document.getElementById("staleBanner"),
  filterInput: document.getElementById("filterInput"),
  clearFilter: document.getElementById("clearFilter"),
  refreshButton: document.getElementById("refreshButton"),
  metaSource: document.getElementById("metaSource"),
  metaCost: document.getElementById("metaCost"),
  metaCoverage: document.getElementById("metaCoverage"),
  metaGenerated: document.getElementById("metaGenerated"),
  footerDate: document.getElementById("footerDate")
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function isNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function formatPrice(value) {
  return isNumber(value) ? value.toFixed(2) : "—";
}

function formatPct(value) {
  if (!isNumber(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatStrength(value) {
  return isNumber(value) ? value.toFixed(1) : "—";
}

function formatDateTime(value) {
  if (!value) return "—";
  return String(value).replace("T", " ").slice(0, 16);
}

function formatCost(value) {
  if (!isNumber(value)) return "—";
  return `¥${value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "")}（估算）`;
}

function changeClass(value) {
  if (!isNumber(value) || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

function tempClass(temperature) {
  if (temperature === "热" || temperature === "沸") return "temp-hot";
  if (temperature === "温") return "temp-warm";
  if (["平", "凉", "寒", "冻"].includes(temperature)) return "temp-flat";
  return "temp-none";
}

function renderTempBadge(member) {
  if (!member.tempPrev && !member.tempCurr) {
    return '<span class="missing">—</span>';
  }
  const className = tempClass(member.tempCurr || member.tempPrev);
  const arrow = member.tempPrev && member.tempCurr ? '<span class="arrow">→</span>' : "";
  const text = `${member.tempPrev ? escapeHtml(member.tempPrev) : ""}${arrow}${
    member.tempCurr ? escapeHtml(member.tempCurr) : ""
  }`;
  return `<span class="temp ${className}">${text}</span>`;
}

function renderStrength(member) {
  if (!isNumber(member.strength)) {
    return '<span class="missing">—</span>';
  }
  const width = Math.max(0, Math.min(100, member.strength));
  return `<div class="strength">
    <span class="strength-bar" aria-hidden="true"><i style="width:${width}%"></i></span>
    <b>${formatStrength(member.strength)}</b>
  </div>`;
}

function renderStrengthChange(value) {
  if (!value) return '<span class="strength-change muted">—</span>';
  const down = value.includes("↓") ? " down" : "";
  return `<span class="strength-change${down}" title="相对上周强度变化">${escapeHtml(value)}</span>`;
}

function renderStatus(value) {
  if (value === true) {
    return '<span class="status-pill status-on">右侧</span>';
  }
  if (value === false) {
    return '<span class="status-pill status-off">左侧</span>';
  }
  return '<span class="missing">—</span>';
}

function renderRow(member, rank) {
  const phase = member.phase
    ? `<span class="phase">${escapeHtml(member.phase)}</span>`
    : '<span class="missing">—</span>';
  return `<tr>
    <td class="col-rank"><span class="rank">${String(rank).padStart(2, "0")}</span></td>
    <td class="cell-name">
      <div class="name-cell">
        <strong>${escapeHtml(member.name || "—")}</strong>
        <span>${escapeHtml(member.symbol || "—")}</span>
      </div>
    </td>
    <td class="num" data-label="最新价"><span class="price">${formatPrice(member.price)}</span></td>
    <td class="num" data-label="当日涨跌">
      <span class="change ${changeClass(member.dayChangePct)}">${formatPct(member.dayChangePct)}</span>
    </td>
    <td data-label="温度变化">${renderTempBadge(member)}</td>
    <td data-label="节气">${phase}</td>
    <td class="cell-strength" data-label="相对强度">${renderStrength(member)}</td>
    <td data-label="强度变化" class="cell-strength-change">${renderStrengthChange(member.strengthChange)}</td>
    <td class="cell-status" data-label="状态">${renderStatus(member.isRightSide)}</td>
  </tr>`;
}

function compareMembers(a, b, key, type, dir) {
  const valueA = a[key];
  const valueB = b[key];
  const emptyA = valueA === null || valueA === undefined || valueA === "";
  const emptyB = valueB === null || valueB === undefined || valueB === "";
  if (emptyA && emptyB) return 0;
  if (emptyA) return 1;
  if (emptyB) return -1;

  let result;
  if (type === "number") {
    result = valueA - valueB;
  } else {
    result = String(valueA).localeCompare(String(valueB), "zh-CN");
  }
  return dir === "asc" ? result : -result;
}

function sortMembers(members, sort) {
  return [...members].sort((a, b) => {
    const result = compareMembers(a, b, sort.key, sort.type, sort.dir);
    if (result !== 0) return result;
    return compareMembers(a, b, "strength", "number", "desc");
  });
}

function currentFilter() {
  return state.filter.trim().toLowerCase();
}

function filterMembers(members) {
  const query = currentFilter();
  if (!query) return members;
  return members.filter((member) => {
    const name = String(member.name || "").toLowerCase();
    const symbol = String(member.symbol || "").toLowerCase();
    return name.includes(query) || symbol.includes(query);
  });
}

function updateVisibleCount(element, visible, total) {
  element.textContent = currentFilter() ? `${visible} / ${total}` : String(total);
}

function sortHint(table) {
  const sort = state.sort[table];
  if (table === "sell" && sort.key === "dayChangePct" && sort.dir === "asc") {
    return "跌幅优先，点击表头可换排序";
  }
  const direction = sort.dir === "asc" ? "升序" : "降序";
  return `${SORT_LABELS[sort.key] || sort.key}${direction}，点击表头可换排序`;
}

function renderTable(table) {
  const body = table === "buy" ? elements.buyBody : elements.sellBody;
  const empty = table === "buy" ? elements.buyEmpty : elements.sellEmpty;
  const visibleLabel = table === "buy" ? elements.buyVisible : elements.sellVisible;
  const hintLabel = table === "buy" ? elements.buySortHint : elements.sellSortHint;
  const list = state.data.lists[table];
  const members = list.members || [];
  const filtered = filterMembers(members);
  const sorted = sortMembers(filtered, state.sort[table]);

  body.innerHTML = sorted.map((member, index) => renderRow(member, index + 1)).join("");
  empty.hidden = sorted.length > 0;
  updateVisibleCount(visibleLabel, sorted.length, members.length);
  hintLabel.textContent = sortHint(table);

  document.querySelectorAll(`.sort-button[data-table="${table}"]`).forEach((button) => {
    const active = button.dataset.key === state.sort[table].key;
    button.dataset.active = active ? "true" : "false";
    button.dataset.dir = state.sort[table].dir;
    const header = button.closest("th");
    if (header) {
      header.setAttribute(
        "aria-sort",
        active ? (state.sort[table].dir === "asc" ? "ascending" : "descending") : "none"
      );
    }
  });
}

function renderSummary() {
  const { buy, sell } = state.data.lists;
  elements.buyCount.textContent = buy.count;
  elements.sellCount.textContent = sell.count;
  elements.heroDate.textContent = state.data.asOfDate || "—";
  elements.statDate.textContent = state.data.asOfDate || "—";
  elements.statTime.textContent = state.data.updateDt
    ? `更新时间 ${formatDateTime(state.data.updateDt)}`
    : "—";
  elements.heroStatus.textContent = state.data.stale
    ? "数据待更新，展示最近有效快照"
    : `已更新 · 买入 ${buy.count} / 卖出 ${sell.count}`;

  elements.staleBanner.hidden = !state.data.stale;
  if (state.data.stale) {
    elements.staleBanner.textContent = `数据尚未更新：当前数据日期 ${state.data.asOfDate || "—"}，预期交易日 ${
      state.data.expectedAsOfDate || "—"
    }。页面展示最近一次有效数据，未生成新信号。`;
  }

  const missing = state.data.meta?.missingSnapshotIds?.length || 0;
  elements.metaSource.textContent = state.data.source?.name || "趋势动物 API";
  elements.metaCost.textContent = formatCost(state.data.meta?.estimatedCost?.total);
  elements.metaCost.title = state.data.meta?.estimatedCost?.note || "";
  elements.metaCoverage.textContent = `买入 ${buy.count} + 卖出 ${sell.count}，快照缺失 ${missing}`;
  elements.metaGenerated.textContent = formatDateTime(state.data.generatedAt);
  elements.footerDate.textContent = `数据日期 ${state.data.asOfDate || "—"}`;

  document.title = `${state.data.asOfDate || "每日"} · 趋势动物 A股趋势信号`;
}

function renderAll() {
  renderSummary();
  renderTable("buy");
  renderTable("sell");
}

function renderError(message) {
  elements.heroStatus.textContent = "数据载入失败";
  elements.staleBanner.hidden = false;
  elements.staleBanner.textContent = `${message} 请稍后点击“刷新数据”重试。`;
  elements.buyEmpty.hidden = false;
  elements.buyEmpty.textContent = "数据载入失败。";
  elements.sellEmpty.hidden = false;
  elements.sellEmpty.textContent = "数据载入失败。";
}

async function loadData() {
  elements.refreshButton.setAttribute("aria-busy", "true");
  elements.refreshButton.textContent = "载入中…";
  try {
    const response = await fetch(`./data.json?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    if (!data.lists?.buy || !data.lists?.sell) {
      throw new Error("数据结构不完整");
    }
    state.data = data;
    renderAll();
  } catch (error) {
    renderError(`无法读取 data.json（${error.message}）。`);
  } finally {
    elements.refreshButton.removeAttribute("aria-busy");
    elements.refreshButton.textContent = "刷新数据";
  }
}

function applyFilter() {
  state.filter = elements.filterInput.value;
  elements.clearFilter.hidden = !state.filter;
  if (state.data) {
    renderTable("buy");
    renderTable("sell");
  }
}

document.querySelectorAll(".sort-button").forEach((button) => {
  button.addEventListener("click", () => {
    const table = button.dataset.table;
    const key = button.dataset.key;
    const type = button.dataset.type;
    const current = state.sort[table];
    if (current.key === key) {
      current.dir = current.dir === "asc" ? "desc" : "asc";
    } else {
      state.sort[table] = {
        key,
        type,
        dir: type === "number" ? "desc" : "asc"
      };
    }
    if (state.data) renderTable(table);
  });
});

elements.filterInput.addEventListener("input", applyFilter);

elements.clearFilter.addEventListener("click", () => {
  elements.filterInput.value = "";
  applyFilter();
  elements.filterInput.focus();
});

elements.refreshButton.addEventListener("click", loadData);

loadData();
