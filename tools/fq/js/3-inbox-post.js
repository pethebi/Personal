// STEP 3 — run on http://localhost:8765/queue.html. Writes each capture to tools/queue/phone/<date>_<id>.json.
// Next: python tools/fq/fq.py stage --days <ArtifactData out_dir>/days
const arr = window.name ? JSON.parse(window.name) : [];
const res = [];
for (const a of Array.isArray(arr) ? arr : []) {
  const r = await fetch("/__file?name=queue/phone/" + a.id + ".json", { method: "POST", body: a.body });
  res.push(a.id + ":" + r.status);
}
window.name = "";
res.join(" ") || "nothing to write"
