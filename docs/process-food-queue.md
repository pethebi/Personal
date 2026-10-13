---
name: process-food-queue
description: Process Mike's food queue - estimate nutrition for photos and unknown foods waiting in the Food Tracker app, then send the estimates back to the app for his review. Use when he says "process my food queue", "process my queue", "check my food queue" or similar.
---

# Process the food queue

Works from any fresh session (or another LLM with the same tools). **Code does every step except
looking at photos and estimating nutrition.** Read CLAUDE.md first for the owner's rules (no sodium talk,
accessibility: words, never color-only cues, never guess meal times, accuracy as %, every item has basis + errPct).

Constants
- APP = <APP_URL: the owner's private claude.ai artifact> (artifact db = source of truth)
- INBOX = private GitHub repo pethebi/food-inbox (Food Capture offline uploads)
- Tools needed: ArtifactData + Artifact (read assets), Claude in Chrome (Mike's logged-in Chrome), a shell with Python 3.
- Local server must be running for the inbox bridge: built-in browser `preview_start {name:"food-app"}` (port 8765).
- SCR = a scratch folder (session scratchpad). Never write personal data into a public repo.

## 0. Usage (Claude Code only)
`get_usage` → append {date, weeklyPct, resetsAt} to tools/data/usage-log.json; one line in the reply. Over 70% weekly: log only.

## 1. Pull current state from the app (deterministic)
ArtifactData `list` collection `queue` (out_dir SCR/db) and `get` days/<today> and days/<yesterday> (out_dir SCR/db).

## 2. Food Capture inbox → tools/queue/phone (deterministic snippets, same Chrome tab)
1. Navigate to http://localhost:8765/queue.html, run `tools/fq/js/1-done-to-name.js` (javascript_tool, paste the file text).
2. Navigate the same tab to https://github.com/pethebi/food-inbox, run `tools/fq/js/2-inbox-fetch.js`.
3. Navigate back to http://localhost:8765/queue.html, run `tools/fq/js/3-inbox-post.js`. Close the tab.
4. `python tools/fq/fq.py stage --days SCR/db/days` → JSON list of captures with photo files and
   `duplicateCandidates` (app meals within 45 min). Captures whose note says "test" → skip (still marked done).

## 3. App queue photos (waiting, with assetIds) and "photo pending" meals
For each assetId: Artifact `read` with `url: APP, path: <assetId>` (one call per asset) → Read the saved jpg.

## 4. Estimate (the only probabilistic step)
Read every photo. Multi-photo rule: photo 1 = base, each later photo = only what was added since the
previous one; captions/notes win. Label photos: use printed values (errPct ~10). Item fields:
`{n, k, p, f, c, fi, fermented: true|false|"unclear", errPct, basis}` (na optional; never mention sodium).
Library foods/rulings: CLAUDE.md + food-tracker-state.md (salmon, cheese wedge 13 g, shake, butter rule).
Write each meal as SCR/meal-<n>.json: `{name, time:"HH:MM"|null, hunger, tags:["phone"], items:[...]}`.

## 5. Merge or add (deterministic doc edit)
- Capture with a duplicateCandidate showing the SAME food → `fq.py apply --day SCR/db/days/<date>.json --meal SCR/meal-n.json --replace <mealId>` (keeps photoAssets/hunger; drop the "photo pending" tag in the meal JSON). Tell Mike "matched your app entry at HH:MM".
- No match → `fq.py apply --day ... --meal ...` (adds). Apply several meals by chaining `--day <previous .new output>`.
- App queue entries (photos only) → instead of a day edit, ArtifactData `update` queue/<id> with
  `{status:"review", error:null, result:{items:[{name, food_id:"", servings, serving_desc, source, per_serving:{k,p,f,c,fi,na}, fermented:"yes|no|unclear", err_pct, basis, save_as_food, aliases}], questions:[], viaClaudeCode:true}, keep:[{servings, save}]}` (pin if_version). Mike taps Accept & log.
- Write each changed day: ArtifactData `set` days/<date> `file_path: <...>.new`, `if_version` = version from step 1.
  Version conflict → re-get, re-apply, never overwrite blindly.

## 6. Finish (deterministic)
`python tools/fq/fq.py done` (marks staged inbox paths in tools/data/inbox-done.json, clears tools/queue/phone).
Reply in a few lines: each meal (time, items with kcal/protein, assumptions, questions), then
`fq.py totals --day <final .new>` numbers for the day. Tell Mike to tap ↻ Update in the app.

## Garmin (when asked, or when the PC session starts the day)
Chrome tab on https://connect.garmin.com/modern/ → run `tools/fq/js/garmin-pull.js` → Write the returned text to
tools/fq/out/garmin-pull.json → `python tools/fq/fq.py garmin --pull tools/fq/out/garmin-pull.json` → ArtifactData
`get` kv/garmin + kv/garminDaily (versions) → `set` them from tools/fq/out/kv_*.json with if_version.
Never use Garmin calories. 

## Legacy (only if the localhost app has queued entries)
http://localhost:8765/queue.html?export=1 → tools/queue/queue.json → estimate → tools/queue/results.json → ?import=1.
