// Audit history: every bill this browser checked, one row per line, in AG Grid Community (self-hosted, MIT).
// Only audit ids this browser created are kept (localStorage) and sent to the server in a POST body.
(function () {
  const KEY = "billcheck.audits";
  const MAX_IDS = 50;
  const usd = (x) => x == null ? "–" : "$" + Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const STATUS = {  // short labels for the grid; the full reason is in each line's tooltip
    ABOVE_REFERENCE: "Above reference", NOT_FLAGGED: "Not flagged",
    PACKAGED: "Included in visit", INFO_ONLY: "For information", NOT_AVAILABLE: "No benchmark",
  };
  const PAYMENT = { audited: "Not paid", ordered: "Started", captured: "Paid", invoiced: "Paid, invoiced" };
  let api = null;

  const ID_RE = /^[0-9a-f]{32}$/;
  function readIds() {  // bad or extra stored values would make the server refuse the whole request
    try {
      const v = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(v) ? v.filter((x) => typeof x === "string" && ID_RE.test(x)).slice(-MAX_IDS) : [];
    } catch (e) { return []; }
  }
  function writeIds(ids) {
    try { localStorage.setItem(KEY, JSON.stringify(ids.slice(-MAX_IDS))); } catch (e) { /* private window: history lasts this page only */ }
  }
  let memoryIds = readIds();

  const merge = (...lists) => [...new Set(lists.flat())].slice(-MAX_IDS);  // other tabs may have added ids

  function add(id) {
    if (!ID_RE.test(id)) return;
    memoryIds = merge(readIds(), memoryIds.filter((x) => x !== id), [id]);
    writeIds(memoryIds);
  }

  function badge(params) {
    if (params.node.rowPinned) return null;
    const span = document.createElement("span");
    span.className = `badge ${params.data.flag_type}`;
    span.textContent = params.value;
    return span;
  }

  const money = { type: "rightAligned", filter: "agNumberColumnFilter", valueFormatter: (p) => usd(p.value), width: 128 };
  const columnDefs = [
    { headerName: "Time", field: "time", width: 104, sort: "desc", filter: false,
      comparator: (a, b, nodeA, nodeB) => (nodeA.data ? nodeA.data.created : 0) - (nodeB.data ? nodeB.data.created : 0) },
    { headerName: "Bill", field: "bill", minWidth: 130, flex: 1, filter: "agTextColumnFilter", tooltipField: "bill" },
    { headerName: "Line", field: "description", minWidth: 130, flex: 1, filter: "agTextColumnFilter",
      tooltipValueGetter: (p) => p.data && p.data.explanation },
    { headerName: "Code", field: "code", width: 88, filter: "agTextColumnFilter" },
    { headerName: "Billed", field: "billed", ...money },
    { headerName: "Medicare", field: "medicare", ...money, headerTooltip: "2026 Medicare price" },
    { headerName: "Suggested", field: "suggested", ...money },
    { headerName: "Difference", field: "difference", ...money,
      cellClassRules: { "cell-flag": (p) => p.value > 0 } },
    { headerName: "Status", field: "status", width: 158, filter: "agTextColumnFilter", cellRenderer: badge,
      tooltipValueGetter: (p) => p.data && p.data.explanation },
    { headerName: "Payment", field: "payment", width: 124, filter: "agTextColumnFilter" },
  ];

  function toRows(audits) {
    const rows = [];
    audits.forEach((a) => {
      const t = new Date(a.created);
      const created = isNaN(t) ? 0 : t.getTime();
      const time = isNaN(t) ? "" : t.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
      a.findings.forEach((f) => rows.push({
        audit: a.audit_id, created, time, bill: a.provider_name, description: f.description, code: f.cpt_code || "–",
        billed: f.billed_amount, medicare: f.benchmark_amount, suggested: f.suggested_amount,
        difference: Math.round((f.billed_amount - f.suggested_amount) * 100) / 100,
        status: STATUS[f.flag_type] || f.flag_type, flag_type: f.flag_type,
        payment: PAYMENT[a.state] || a.state, explanation: f.explanation,
      }));
    });
    return rows;
  }

  function updateTotals() {
    let billed = 0, suggested = 0, n = 0;
    const bills = new Set();
    api.forEachNodeAfterFilter((node) => {
      if (!node.data) return;
      billed += node.data.billed; suggested += node.data.suggested; n += 1; bills.add(node.data.audit);
    });
    const r2 = (x) => Math.round(x * 100) / 100;
    api.setGridOption("pinnedBottomRowData", [{
      bill: `Total · ${n} line${n === 1 ? "" : "s"}`, billed: r2(billed), suggested: r2(suggested), difference: r2(billed - suggested),
    }]);
    document.getElementById("hist-stats").textContent =
      `${bills.size} bill${bills.size === 1 ? "" : "s"} shown · billed ${usd(billed)} · suggested ${usd(suggested)} · potential negotiation difference ${usd(billed - suggested)}`;
  }

  let latest = 0;
  async function refresh() {
    const section = document.getElementById("step-history");
    if (!api) return;
    const seq = ++latest;
    const sent = merge(readIds(), memoryIds);
    try {
      const resp = await fetch("/api/history", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audit_ids: sent }) });
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.error || "History could not be loaded.");
      if (seq !== latest) return;  // a newer refresh is on its way: never show older data over it
      const known = new Set(body.audits.map((a) => a.audit_id));
      const expired = new Set(sent.filter((x) => !known.has(x)));  // only ids we asked about can be pruned
      memoryIds = merge(readIds(), memoryIds).filter((x) => !expired.has(x));
      writeIds(memoryIds);
      api.setGridOption("rowData", toRows(body.audits));
      updateTotals();
      document.getElementById("hist-empty").hidden = body.audits.length > 0;
      section.hidden = false;
    } catch (err) {
      document.getElementById("hist-stats").textContent = err.message;
    }
  }

  function init() {
    const box = document.getElementById("history-grid");
    if (!window.agGrid || !box) return;
    const theme = window.agGrid.themeQuartz.withParams({
      accentColor: "#0f6e5c", fontFamily: "inherit", fontSize: 14, headerFontWeight: 700,
      backgroundColor: "#ffffff", headerBackgroundColor: "#f6f7f5", borderColor: "#e2e6e3", foregroundColor: "#1c2321",
    });
    api = window.agGrid.createGrid(box, {
      theme, columnDefs, rowData: [],
      defaultColDef: { sortable: true, resizable: true, filter: true, floatingFilter: false },
      tooltipShowDelay: 300, animateRows: true, enableCellTextSelection: true,
      overlayNoRowsTemplate: "<span>No bills checked in this browser yet.</span>",
      onFilterChanged: updateTotals,
      getRowClass: (p) => (p.node.rowPinned ? "row-total" : ""),
    });
    document.getElementById("hist-filter").addEventListener("input", (e) => api.setGridOption("quickFilterText", e.target.value));
    document.getElementById("hist-csv").addEventListener("click", () =>
      api.exportDataAsCsv({ fileName: "billcheck-audit-history.csv", columnKeys: columnDefs.map((c) => c.field),
        // bill text comes from an upload: stop spreadsheet apps from running a cell as a formula
        processCellCallback: (p) => (typeof p.value === "string" && /^[=+\-@\t\r]/.test(p.value) ? "'" + p.value : p.value) }));
    refresh();
  }

  window.BillCheckHistory = { add, refresh, init };
})();
