---
name: food-app-dev
description: Build, fix, test and ship Mike's Food Tracker (claude.ai artifact app) and the Food Capture offline uploader. Use for any code change, new feature, bug, deploy, data repair or "continue the app work" request in this project.
---

# Food Tracker development

Written so a new session (or a different LLM) can pick the work up cold. Read in this order:
CLAUDE.md (rules, targets, data model) → README.md "How the pieces fit" → this file.

## System map
| Part | Code | Runs at | Data |
|---|---|---|---|
| Food Tracker (main, online) | `app/` (plain ES modules, no build) | claude.ai artifact <APP_URL: the owner's private claude.ai artifact>; dev at http://localhost:8765 | artifact db: `days/<date>`, `foods/<id>`, `kv/<key>` (profile, plan, calc, garmin, garminDaily), `queue/<id>` (owner only); photos in artifact assets |
| Food Capture (offline) | `food-capture/` | GitHub Pages, repo `pethebi/Personal` (root) | phone storage → private repo `pethebi/food-inbox` |
| Queue + Garmin tooling | `tools/fq/fq.py`, `tools/fq/js/*.js` | PC (Python 3 stdlib, Mike's Chrome) | see process-food-queue skill |

Key modules: `app/js/store.js` (IndexedDB locally; on claude.ai `detectShare` → `connectCloud`: owner = `EDIT`,
writes mirrored to the db, `SAMPLE` = Claude, `ASSETS` = photo storage), `app/js/app.js` (UI), `app/js/llm.js`
(estimates via `sample`, photo-pending fallback), `app/js/core/calc.js` (all math; totals are always computed,
never stored), `app/js/trends.js`, `app/js/core/parser.js` (typed food → library items).

## Hard rules (Mike's)
- Never store or type passwords/tokens on the PC; GitHub token lives only on the phone. Never sign in to claude.ai/Garmin.
- Ask before commits, repo creation or settings changes. Personal data never goes into `pethebi/Personal` (code only;
  `app/js/data/legacy-data.js` stays out of every repo).
- Accessibility: every color cue needs a word/shape/label. No red/green-only signals, no colored emoji in replies.
- No sodium in UI or replies. No Garmin calories. Accuracy as %, never letter grades.
- Large readable text; no horizontal scroll at 375 px; light + dark.
- Owner sees everything; shared viewers (commenters) get `html.share` read-only: hide new owner-only UI with `.share` CSS.
- Keep replies short. Check weekly usage (`get_usage`) before big builds; above ~80% projected, log only.

## Change → ship loop
1. Edit files under `app/` (or `food-capture/`). Match the surrounding style (dense, short comments with dates).
2. Bump `VERSION` in `app/sw.js` (`ft-vNN`) or `food-capture/sw.js` (`fc-vN`).
3. Test locally: built-in browser `preview_start {name:"food-app"}`; unregister service workers + clear caches, reload;
   check `document.documentElement.dataset.ready === "1"`, no `<pre>` error, no console errors;
   `/test.html` must say "all passed" (add a parser case to `app/js/tests.js` for new phrase patterns);
   at 375 px `document.documentElement.scrollWidth <= 375`, light + dark. The cloud parts (db/sample/assets)
   only run on claude.ai: ask Mike to test those on his phone and report what he sees.
4. Publish the artifact: Artifact tool, `url` = the app URL, `file_path` = absolute `app/index.html`,
   `root` = project folder, `files` = `{"js/app.js":"app/js/app.js", ...}` listing every changed file
   (published paths are relative to app/). Omit `capabilities` to keep them. If refused as "not read",
   `action:"read"` those paths first, confirm they match your pre-edit copy, then publish again.
   Current capabilities: `{db:{rules:[{path:"",read:"view",write:"owner"},{path:"queue",read:"owner",write:"owner"}]}, user:{}, sample:{}, assets:{}}`, contract 0.2.76.
5. Food Capture: upload changed files to `pethebi/Personal` via Mike's Chrome (github.com/pethebi/Personal/upload/main,
   file_upload on the file input, commit message) — only after Mike OKs the commit.
6. Update README.md / CLAUDE.md when behavior changes. Tell Mike to reload (or tap ↻ Update).

## Data repair (db)
ArtifactData: `list`/`get` with `out_dir` to files; edit with `tools/fq/fq.py apply` or a short script;
write back with `set`/`batch` using `file_path` and `if_version` (writes fail if the doc changed: re-read, redo).
Files must be UTF-8 **without BOM** (PowerShell 5 `Set-Content -Encoding utf8` adds one; use Python or `[IO.File]::WriteAllText`).
Never run fresh-install seeding on claude.ai (`seedIfEmpty` returns early in SHARE mode; the 10/13 bug overwrote profile/foods).

## Known limits / decisions (10/13)
- claude.ai iPhone app: a page can't send photos to Claude (`sample.limits().images` absent). The app estimates from the
  note, tags the meal "photo pending", stores photos as assets; Claude Code corrects later. The Log food tab's gray
  line says whether the current view can send photos.
- Artifact pages can't reach outside sites (no GitHub from the page). Offline capture = Food Capture only.
- Duplicate rule: inbox capture within 45 min of an app meal with the same food → merge, never add.
- Backlog: text labels on Trends chart colors, Week 2 features (recent-notes picks, "same as yesterday"),
  summary for the dietitian.
