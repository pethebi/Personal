// STEP 2 — run on https://github.com/pethebi/food-inbox (Mike is logged in; read-only, no token on the PC).
// Lists the last 4 days' folders, fetches every capture not in the done list, stores them in window.name.
// Then navigate the SAME tab back to http://localhost:8765/queue.html and run step 3.
const { done } = JSON.parse(window.name || '{"done":[]}');
const days = [...Array(4)].map((_, i) => new Date(Date.now() - i * 864e5).toLocaleDateString("en-CA"));
const out = [];
for (const d of days) {
  const r = await fetch("/pethebi/food-inbox/tree/main/" + d, { cache: "no-store" });
  if (!r.ok) continue;
  const names = [...new Set([...(await r.text()).matchAll(new RegExp(d + "/([\w-]+)\.json", "g"))].map(m => m[1]))];
  for (const n of names) {
    const path = d + "/" + n + ".json";
    if (done.includes(path)) continue;
    out.push({ id: d + "_" + n, body: await (await fetch("/pethebi/food-inbox/raw/main/" + path)).text() });
  }
}
window.name = JSON.stringify(out);
out.length ? "new captures: " + out.map(o => o.id).join(" ") : "no new captures"
