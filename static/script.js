// script.js - frontend logic (vanilla JavaScript)
// The Python (Flask) server must answer the API calls.
// 1) If this page is served by Flask itself, use relative URLs.
// 2) Otherwise (double-click, VS Code Live Server, ...) look for Flask on common local ports.
let apiBase = null;
async function findBase() {
  if (apiBase !== null) return apiBase;
  const candidates = [""];
  if (location.protocol === "file:" || ["127.0.0.1", "localhost", ""].includes(location.hostname)) {
    for (const p of [5000, 5001, 5002, 8000, 8080]) candidates.push("http://127.0.0.1:" + p);
  }
  for (const base of candidates) {
    // Check 1: the health route (new app.py)
    try {
      const r = await fetch(base + "/api/health", { cache: "no-store" });
      if (r.ok && (await r.json()).status === "ok") return (apiBase = base);
    } catch { /* fall through */ }
    // Check 2: works even with an older app.py that has no /api/health route
    try {
      const r = await fetch(base + "/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      const d = await r.json();
      if (d && typeof d.error === "string") return (apiBase = base);
    } catch { /* try next port */ }
  }
  throw new Error("Python server not detected. In the VS Code terminal run:  python app.py   then open http://127.0.0.1:5000");
}
const $ = (id) => document.getElementById(id);
let currentUrl = "";
let lastData = null;
let history = [];

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function readJson(res) {
  const raw = await res.text();
  if (!raw.trim()) throw new Error("Empty reply (HTTP " + res.status + ") from " + res.url + ". Make sure `python app.py` is running and open http://127.0.0.1:5000 in your browser.");
  try { return JSON.parse(raw); }
  catch { throw new Error("The server sent an invalid reply (HTTP " + res.status + ")."); }
}

async function postJson(path, payload, ms = 70000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const base = await findBase();
    const res = await fetch(base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    return { res, data: await readJson(res) };
  } catch (e) {
    if (e.name === "AbortError") throw new Error("The request took too long. Try again or use another website.");
    if (e instanceof TypeError) { apiBase = null; throw new Error("Cannot reach the Python server. Make sure `python app.py` is running in the terminal."); }
    throw e;
  } finally { clearTimeout(timer); }
}

// ---------- Scrape form ----------
document.querySelectorAll(".ex").forEach((b) => (b.onclick = () => {
  $("urlInput").value = b.dataset.url;
  $("scrapeForm").requestSubmit();
}));

$("scrapeForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("error").hidden = true;
  $("results").hidden = true;
  $("loader").hidden = false;
  $("scrapeBtn").disabled = true;
  const steps = ["Connecting to website...", "Reading pages...", "Extracting services & contacts..."];
  let i = 0;
  $("loaderText").textContent = steps[0];
  const ticker = setInterval(() => ($("loaderText").textContent = steps[Math.min(++i, steps.length - 1)]), 2500);
  try {
    const { res, data } = await postJson("/api/scrape", { url: $("urlInput").value });
    if (!res.ok) throw new Error(data.error || "Something went wrong.");
    currentUrl = data.url;
    lastData = data;
    history = [];
    render(data);
    addMsg("bot", `I've analyzed ${data.site_name}. Ask me anything about it!`);
    $("results").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    $("error").textContent = err.message;
    $("error").hidden = false;
  } finally {
    clearInterval(ticker);
    $("loader").hidden = true;
    $("scrapeBtn").disabled = false;
  }
});

function render(d) {
  $("siteName").textContent = d.site_name;
  $("siteUrl").textContent = d.url;
  $("siteUrl").href = d.url;
  $("purpose").textContent = d.purpose || d.description || "No purpose statement found on this website.";

  $("services").innerHTML = d.services.length
    ? d.services.map((s) => `<li>${esc(s)}</li>`).join("")
    : '<li class="muted">No services detected.</li>';

  const c = d.contact;
  const rows = [];
  if (c.emails.length) rows.push(`<div class="row"><b>Email:</b> ${c.emails.map((m) => `<a href="mailto:${esc(m)}">${esc(m)}</a>`).join(", ")}</div>`);
  if (c.phones.length) rows.push(`<div class="row"><b>Phone:</b> ${c.phones.map(esc).join(", ")}</div>`);
  if (c.address) rows.push(`<div class="row"><b>Address:</b> ${esc(c.address)}</div>`);
  if (c.contact_page) rows.push(`<div class="row"><b>Contact page:</b> <a href="${esc(c.contact_page)}" target="_blank" rel="noopener">${esc(c.contact_page)}</a></div>`);
  $("contact").innerHTML = rows.join("") || '<p class="muted">No contact details found.</p>';

  const soc = Object.entries(d.social_links);
  $("socials").innerHTML = soc.length
    ? soc.map(([n, u]) => `<li><b>${esc(n)}:</b> <a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></li>`).join("")
    : '<li class="muted">No social links found.</li>';

  const pages = Object.entries(d.key_pages);
  $("pages").innerHTML = pages.length
    ? pages.map(([n, u]) => `<li><b>${esc(n)}:</b> <a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></li>`).join("")
    : '<li class="muted">No About / Contact / Services pages found.</li>';
  const heads = [...d.headings.h1, ...d.headings.h2];
  $("headings").innerHTML = heads.map((h) => `<li>• ${esc(h)}</li>`).join("");

  $("statServices").textContent = d.services.length;
  $("statEmails").textContent = c.emails.length;
  $("statPhones").textContent = c.phones.length;
  $("statSocial").textContent = soc.length;
  $("results").hidden = false;
}

$("downloadBtn").onclick = () => {
  if (!lastData) return;
  const blob = new Blob([JSON.stringify(lastData, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (lastData.site_name || "website").replace(/\W+/g, "_") + ".json";
  a.click();
  URL.revokeObjectURL(a.href);
};

// ---------- Chatbot ----------
$("chatToggle").onclick = () => ($("chatBox").hidden = !$("chatBox").hidden);
$("chatClose").onclick = () => ($("chatBox").hidden = true);

function addMsg(role, text) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  $("chatMessages").appendChild(div);
  $("chatMessages").scrollTop = $("chatMessages").scrollHeight;
  return div;
}

async function sendChat(text) {
  if (!text.trim()) return;
  addMsg("user", text);
  if (!currentUrl) return addMsg("bot", "Please analyze a website first.");
  const typing = addMsg("bot", "...");
  try {
    const { data } = await postJson("/api/chat", { message: text, url: currentUrl, history });
    typing.textContent = data.reply || data.error || "Sorry, something went wrong.";
    history.push({ role: "user", content: text }, { role: "assistant", content: typing.textContent });
  } catch (err) {
    typing.textContent = err.message;
  }
}

$("chatForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const t = $("chatInput").value;
  $("chatInput").value = "";
  sendChat(t);
});
document.querySelectorAll(".chips button").forEach((b) => (b.onclick = () => sendChat(b.dataset.q)));

// ---------- Backend status check ----------
(async function checkBackend() {
  try { await findBase(); }
  catch (e) { $("error").textContent = e.message; $("error").hidden = false; }
})();
