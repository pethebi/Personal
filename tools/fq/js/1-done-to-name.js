// STEP 1 — run on http://localhost:8765/queue.html (Mike's Chrome). Loads the done list into window.name
// (window.name survives navigation in the same tab). Then navigate the SAME tab to https://github.com/pethebi/food-inbox
const d = await (await fetch("/__file?name=data/inbox-done.json", { cache: "no-store" })).json();
window.name = JSON.stringify({ done: d.done });
"done list loaded: " + d.done.length + " paths"
