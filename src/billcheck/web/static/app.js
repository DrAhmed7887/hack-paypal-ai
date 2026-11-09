// BillCheck page logic. All server and model text is inserted with textContent (never innerHTML).
const $ = (id) => document.getElementById(id);
const usd = (x) => x == null ? "–" : "$" + Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const LABELS = {
  ABOVE_REFERENCE: "Above negotiation reference", NOT_FLAGGED: "Not flagged",
  PACKAGED: "Included in visit payment", INFO_ONLY: "For information", NOT_AVAILABLE: "Benchmark not available",
};
let auditId = null;
let paypalLoaded = false;

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function showError(id, message) {
  const box = $(id);
  box.textContent = message;
  box.hidden = !message;
}

async function api(path, options = {}) {
  const resp = await fetch(path, options);
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(body.error || "Something went wrong. Please try again.");
  return body;
}

async function loadConfig() {
  const cfg = await api("/api/config");
  const box = $("samples");
  cfg.samples.forEach((s) => {
    const b = el("button", "chip", s.title);
    b.type = "button";
    b.setAttribute("role", "listitem");
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", async () => {
      box.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      $("bill-file").value = "";
      $("file-name").textContent = "";
      $("bill-text").value = (await api(`/api/samples/${encodeURIComponent(s.id)}`)).text;
    });
    box.appendChild(b);
  });
  return cfg;
}

function renderResults(r) {
  const summary = $("summary");
  summary.replaceChildren(el("p", null, r.summary.text),
    el("p", "src", r.summary.source === "ai"
      ? "Plain-language summary written by AI and checked: every dollar figure in it comes from the audit."
      : "Summary from BillCheck's fixed template."));
  $("t-billed").textContent = usd(r.total_billed);
  $("t-suggested").textContent = usd(r.total_suggested);
  $("t-diff").textContent = usd(r.potential_negotiation_difference);
  const mm = $("mismatch");
  mm.hidden = r.totals_match;
  mm.textContent = r.totals_match ? "" : `The lines add up to ${usd(r.line_sum)}, but the bill states ${usd(r.total_billed)}. BillCheck uses the lines.`;
  const list = $("lines");
  list.replaceChildren();
  r.findings.forEach((f) => {
    const li = el("li", "line");
    const head = el("div", "line-head");
    const left = el("div");
    left.append(el("div", "line-name", f.description), el("div", "line-code", f.cpt_code ? `Code ${f.cpt_code}` : "No code"));
    const right = el("div", "amounts");
    if (f.suggested_amount < f.billed_amount) {
      right.append(el("span", "was", usd(f.billed_amount)), el("strong", null, usd(f.suggested_amount)));
    } else {
      right.append(el("strong", null, usd(f.billed_amount)));
    }
    head.append(left, right);
    li.append(head, el("span", `badge ${f.flag_type}`, LABELS[f.flag_type] || f.flag_type), el("p", "why", f.explanation));
    list.appendChild(li);
  });
  $("caveat").textContent = r.caveat;
  $("step-results").hidden = false;
}

function loadPayPal(clientId) {
  return new Promise((resolve, reject) => {
    if (paypalLoaded) return resolve();
    const s = document.createElement("script");
    s.src = `https://www.sandbox.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=USD&intent=capture`;
    s.onload = () => { paypalLoaded = true; resolve(); };
    s.onerror = () => { s.remove(); reject(new Error("PayPal could not be loaded.")); };
    document.head.appendChild(s);
  });
}

async function setupPayment(cfg, r) {
  const step = $("step-pay");
  $("receipt").hidden = true;
  showError("pay-error", "");
  $("paypal-buttons").replaceChildren();
  if (!(r.total_suggested > 0) || r.total_suggested >= r.line_sum) { step.hidden = true; return; }  // nothing reduced: no pay step
  $("pay-text").textContent = `Pay ${usd(r.total_suggested)} instead of ${usd(r.line_sum)}. This is PayPal sandbox money: no real payment is made.`;
  step.hidden = false;
  if (!cfg.paypal_client_id) { showError("pay-error", "PayPal is not configured on this server."); return; }
  try {
    await loadPayPal(cfg.paypal_client_id);
    await window.paypal.Buttons({
      style: { layout: "vertical", label: "pay" },
      createOrder: async () => (await api(`/api/audits/${auditId}/order`, { method: "POST" })).order_id,
      onApprove: async () => showReceipt(await api(`/api/audits/${auditId}/capture`, { method: "POST" })),
      onError: (err) => showError("pay-error", (err && err.message) || "The payment did not complete."),
    }).render("#paypal-buttons");
  } catch (err) { showError("pay-error", err.message); }
}

function showReceipt(rec) {
        $("r-amount").textContent = usd(rec.amount);
        $("r-capture").textContent = rec.capture_id || "–";
        const inv = $("r-invoice");
        inv.replaceChildren();
        if (rec.invoice_url) {
          const a = el("a", null, rec.invoice_id);
          a.href = rec.invoice_url; a.target = "_blank"; a.rel = "noopener";
          inv.appendChild(a);
        } else {
          const retry = el("button", "chip", "Payment received. Issue the itemized invoice");
          retry.type = "button";
          retry.addEventListener("click", async () => {
            retry.disabled = true;
            try { showReceipt(await api(`/api/audits/${auditId}/capture`, { method: "POST" })); }
            catch (err) { showError("pay-error", err.message); retry.disabled = false; }
          });
          inv.appendChild(retry);
        }
        $("r-note").textContent = rec.invoice_status === "issued"
          ? "An itemized invoice at the suggested amounts was issued through PayPal from the provider's sandbox account and marked as paid with this payment."
          : "Your payment is complete. The itemized invoice has not been issued yet; use the button above to try again.";
        $("paypal-buttons").replaceChildren();
        $("receipt").hidden = false;
        window.BillCheckHistory?.refresh();
}

async function checkAllSamples(cfg) {
  const btn = $("hist-samples");
  btn.disabled = true;
  try {
    for (let i = 0; i < cfg.samples.length; i += 1) {
      btn.textContent = `Checking ${i + 1} of ${cfg.samples.length}…`;
      const text = (await api(`/api/samples/${encodeURIComponent(cfg.samples[i].id)}`)).text;
      const form = new FormData();
      form.append("text", text);
      window.BillCheckHistory?.add((await api("/api/audit", { method: "POST", body: form })).audit_id);
      await window.BillCheckHistory?.refresh();
    }
  } catch (err) {
    $("hist-stats").textContent = err.message;
  } finally {
    btn.disabled = false; btn.textContent = "Check all 5 sample bills";
  }
}

async function main() {
  let cfg = { samples: [], paypal_client_id: "" };
  try { cfg = await loadConfig(); } catch (err) { showError("bill-error", err.message); }
  try { window.BillCheckHistory?.init(); } catch (err) { $("hist-stats").textContent = "Audit history is unavailable."; }
  $("hist-samples").addEventListener("click", () => checkAllSamples(cfg));
  $("bill-file").addEventListener("change", (e) => {
    $("file-name").textContent = e.target.files[0] ? e.target.files[0].name : "";
  });
  $("check").addEventListener("click", async () => {
    const btn = $("check");
    showError("bill-error", "");
    const form = new FormData();
    const file = $("bill-file").files[0];
    if (file) form.append("file", file); else form.append("text", $("bill-text").value);
    if (!file && !$("bill-text").value.trim()) { showError("bill-error", "Pick a sample, paste a bill or upload a file first."); return; }
    btn.disabled = true; btn.textContent = "Reading your bill…";
    try {
      const r = await api("/api/audit", { method: "POST", body: form });
      auditId = r.audit_id;
      window.BillCheckHistory?.add(auditId);
      renderResults(r);
      await setupPayment(cfg, r);
      window.BillCheckHistory?.refresh();
      $("step-results").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showError("bill-error", err.message);
    } finally {
      btn.disabled = false; btn.textContent = "Check this bill";
    }
  });
}

main();
