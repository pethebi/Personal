// Food Capture: offline photo + note log. Meals live in IndexedDB on the phone and upload themselves
// (one JSON file per meal) to a private GitHub repo when online. Claude Code reads that repo on
// "process my food queue". No estimates here; Claude estimates on the PC.
"use strict";
const $ = id => document.getElementById(id);
const KEEP_DAYS = 14;

// ---- IndexedDB ----
let dbp;
const db = () => (dbp ||= new Promise((res, rej) => {
  const r = indexedDB.open("food-capture", 1);
  r.onupgradeneeded = () => r.result.createObjectStore("meals", { keyPath: "id" });
  r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
}));
const tx = async (mode, fn) => { const d = await db(); return new Promise((res, rej) => { const t = d.transaction("meals", mode), q = fn(t.objectStore("meals")); t.oncomplete = () => res(q && q.result); t.onerror = () => rej(t.error); }); };
const all = () => tx("readonly", s => s.getAll());
const put = m => tx("readwrite", s => s.put(m));
const del = id => tx("readwrite", s => s.delete(id));

// ---- settings (localStorage; token never leaves the phone except to api.github.com) ----
const get = k => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };
const set = (k, v) => { try { localStorage.setItem(k, v); } catch {} };
const repo = () => get("fc-repo") || "pethebi/food-inbox";

// ---- helpers ----
const pad = n => String(n).padStart(2, "0");
const localIso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
// Food day: midnight-3:59 am counts toward the previous day (same rule as the tracker).
const foodDay = iso => { const d = new Date(iso); if (d.getHours() < 4) d.setDate(d.getDate() - 1); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const fmt = iso => new Date(iso).toLocaleString("en-US", { weekday: "short", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" });
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const status = t => ($("status").textContent = t);

// Resize a photo to <= 1024 px JPEG so uploads stay small (~100-200 KB).
function shrink(file) {
  return new Promise((res, rej) => {
    const url = URL.createObjectURL(file), img = new Image();
    img.onload = () => { const s = Math.min(1, 1024 / Math.max(img.width, img.height)), c = document.createElement("canvas");
      c.width = Math.round(img.width * s); c.height = Math.round(img.height * s); c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url); res(c.toDataURL("image/jpeg", 0.75)); };
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error("Couldn't read that photo")); };
    img.src = url;
  });
}

// ---- form ----
let draft = null;
function openForm(m) {
  draft = m || { id: uid(), photos: [], note: "", time: localIso(new Date()), meal: "", hunger: null, status: "pending" };
  $("note").value = draft.note; $("when").value = draft.time; $("meal").value = draft.meal || ""; drawHunger(); drawPhotos();
  $("form").classList.remove("hide"); $("newBtn").classList.add("hide");
}
function closeForm() { draft = null; $("form").classList.add("hide"); $("newBtn").classList.remove("hide"); }
function drawHunger() { document.querySelectorAll("#hunger button").forEach(b => b.setAttribute("aria-pressed", String(draft && draft.hunger === +b.dataset.h))); }
function drawPhotos() {
  $("photos").innerHTML = draft.photos.map((p, i) => `<div class="ph"><img src="${p.data}" alt="Photo ${i + 1}"><span class="n">${i + 1}</span><button type="button" class="x" data-x="${i}" aria-label="Remove photo ${i + 1}">✕</button><input data-c="${i}" value="${esc(p.caption)}" placeholder="${i ? "added what?" : "what's this?"}"></div>`).join("");
}
async function addFiles(files) {
  for (const f of files) { try { draft.photos.push({ data: await shrink(f), caption: "", takenAt: localIso(new Date(f.lastModified || Date.now())) }); } catch (e) { status(e.message); } }
  drawPhotos();
}
async function save() {
  draft.note = $("note").value.trim(); draft.time = $("when").value || localIso(new Date()); draft.meal = $("meal").value;
  if (!draft.photos.length && !draft.note) { status("Add a photo or a note first."); return; }
  draft.date = foodDay(draft.time); draft.status = "pending"; draft.savedAt = new Date().toISOString();
  await put(draft); closeForm(); status("Saved."); await render(); sync();
}

// ---- list ----
async function render() {
  const ms = (await all()).sort((a, b) => (a.time < b.time ? 1 : -1));
  $("list").innerHTML = ms.length ? ms.map(m => `<div class="card meal">${m.photos[0] ? `<img src="${m.photos[0].data}" alt="">` : ""}<div style="flex:1;min-width:0">
    <div class="t">${esc(m.meal || "Meal")} · ${fmt(m.time)}</div><div class="d">${esc(m.note) || "<i>no note</i>"}${m.photos.length > 1 ? ` · ${m.photos.length} photos` : ""}</div>
    <div class="row" style="margin-top:6px;align-items:center"><span class="st ${m.status === "sent" ? "sent" : m.error ? "err" : "wait"}">${m.status === "sent" ? "✓ sent" : m.error ? "⚠ " + esc(m.error) : "⏳ waiting to send"}</span>
    ${m.status === "sent" ? `<button type="button" data-del="${m.id}" style="min-height:36px;flex:0 0 auto">Remove</button>` : `<button type="button" data-edit="${m.id}" style="min-height:36px;flex:0 0 auto">Edit</button><button type="button" data-del="${m.id}" style="min-height:36px;flex:0 0 auto">Delete</button>`}</div></div></div>`).join("") : `<p class="sub">No meals yet.</p>`;
}

// ---- upload to GitHub (Contents API), one file per meal ----
let syncing = false;
const b64 = s => { const u = new TextEncoder().encode(s); let out = ""; for (let i = 0; i < u.length; i += 0x8000) out += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(out); };
async function sync() {
  if (syncing) return; const token = get("fc-token");
  const pending = (await all()).filter(m => m.status !== "sent");
  if (!pending.length) { await cleanup(); return; }
  if (!navigator.onLine) { status(`Offline: ${pending.length} meal${pending.length > 1 ? "s" : ""} will send when you're online.`); return; }
  if (!token) { status("Add your GitHub token in Settings to send meals."); return; }
  syncing = true; let ok = 0;
  for (const m of pending) {
    const path = `${m.date}/${m.time.slice(11, 16).replace(":", "")}-${m.id}.json`;
    const body = { id: m.id, date: m.date, time: m.time.slice(11, 16), datetime: m.time, meal: m.meal, note: m.note, hunger: m.hunger,
      photos: m.photos.map((p, i) => ({ step: i + 1, caption: p.caption, data: p.data })), savedAt: m.savedAt, app: "food-capture v1" };
    try {
      const r = await fetch(`https://api.github.com/repos/${repo()}/contents/${path}`, { method: "PUT",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "Content-Type": "application/json" },
        body: JSON.stringify({ message: `meal ${m.date} ${m.time.slice(11, 16)}`, content: b64(JSON.stringify(body)) }) });
      if (r.status === 201 || r.status === 200 || r.status === 422) { m.status = "sent"; m.sentAt = new Date().toISOString(); delete m.error; ok++; } // 422 = already there
      else m.error = r.status === 401 ? "token rejected" : r.status === 404 ? "repo not found / no access" : "send failed (" + r.status + ")";
    } catch { m.error = "send failed (network)"; }
    await put(m);
  }
  syncing = false; status(ok ? `Sent ${ok} meal${ok > 1 ? "s" : ""}.` : ""); await cleanup(); await render();
}
async function cleanup() {
  const cut = Date.now() - KEEP_DAYS * 864e5;
  for (const m of await all()) if (m.status === "sent" && Date.parse(m.sentAt || 0) < cut) await del(m.id);
}

// ---- wiring ----
$("newBtn").onclick = () => openForm();
$("cancelBtn").onclick = closeForm;
$("saveBtn").onclick = save;
$("camBtn").onclick = () => $("cam").click();
$("libBtn").onclick = () => $("lib").click();
$("cam").onchange = e => { addFiles([...e.target.files]); e.target.value = ""; };
$("lib").onchange = e => { addFiles([...e.target.files]); e.target.value = ""; };
$("photos").onclick = e => { const x = e.target.dataset.x; if (x != null) { draft.photos.splice(+x, 1); drawPhotos(); } };
$("photos").oninput = e => { const c = e.target.dataset.c; if (c != null) draft.photos[+c].caption = e.target.value; };
$("hunger").onclick = e => { const h = +e.target.dataset.h; if (h) { draft.hunger = draft.hunger === h ? null : h; drawHunger(); } };
$("list").onclick = async e => {
  const ed = e.target.dataset.edit, dl = e.target.dataset.del;
  if (ed) openForm((await all()).find(m => m.id === ed));
  if (dl && confirm("Remove this meal from the phone?")) { await del(dl); render(); }
};
$("syncBtn").onclick = sync;
$("token").value = get("fc-token"); $("repo").value = repo();
$("saveSet").onclick = () => { set("fc-token", $("token").value.trim()); set("fc-repo", $("repo").value.trim() || "pethebi/food-inbox"); status("Settings saved."); sync(); };
window.addEventListener("online", sync);
document.addEventListener("visibilitychange", () => { if (!document.hidden) sync(); });
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
render().then(sync);
