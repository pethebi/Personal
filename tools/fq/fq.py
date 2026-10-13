#!/usr/bin/env python3
"""fq: deterministic helpers for the food queue (Mike's Food Tracker). Stdlib only.

The LLM only does what code can't: look at photos and estimate nutrition. Everything else
(file moves, photo decoding, duplicate detection, doc edits, totals, Garmin merging) is here.

  python tools/fq/fq.py stage   [--days DIR]          decode tools/queue/phone/*.json, list captures (+ duplicate candidates)
  python tools/fq/fq.py apply   --day F --meal M [--replace MEAL_ID] [--out F2]   add/replace a meal in a day doc
  python tools/fq/fq.py totals  --day F                totals per meal + day (kcal, protein, carbs, fat, fiber)
  python tools/fq/fq.py done                           mark staged inbox files done, clear tools/queue/phone
  python tools/fq/fq.py garmin  --pull F               merge a garmin-pull.js result, write db kv docs to tools/fq/out/

Day docs are the JSON files ArtifactData writes with out_dir (days/<date>.json). Output files are
UTF-8 without BOM so ArtifactData file_path accepts them. See .claude/skills/process-food-queue/SKILL.md.
"""
import argparse, base64, json, os, re, shutil, sys, time
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PHONE = os.path.join(ROOT, "tools", "queue", "phone")
DATA = os.path.join(ROOT, "tools", "data")
OUT = os.path.join(ROOT, "tools", "fq", "out")
MATCH_MIN = 45  # Mike 10/13: same meal in Food Capture + app within 45 min = one meal
ITEM_KEYS = {"n": str, "k": (int, float), "p": (int, float), "f": (int, float), "c": (int, float), "fi": (int, float), "errPct": (int, float), "basis": str}


def load(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def save(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:  # no BOM
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))


def day_body(doc):
    """ArtifactData out_dir files hold the document body; tolerate a {data: body} wrapper."""
    return doc["data"] if isinstance(doc, dict) and "data" in doc and "meals" not in doc else doc


def mins(t):
    if not t or not re.match(r"^\d{1,2}:\d{2}$", str(t)):
        return None
    h, m = str(t).split(":")
    return int(h) * 60 + int(m)


def r1(x):
    return round(float(x or 0), 1)


# ---------- stage ----------
def cmd_stage(a):
    if not os.path.isdir(PHONE):
        print(json.dumps({"captures": [], "note": "tools/queue/phone is empty"}))
        return
    days = {}
    if a.days:
        for fn in os.listdir(a.days):
            if fn.endswith(".json"):
                b = day_body(load(os.path.join(a.days, fn)))
                days[b.get("date", fn[:-5])] = b
    caps = []
    for fn in sorted(os.listdir(PHONE)):
        if not fn.endswith(".json"):
            continue
        c = load(os.path.join(PHONE, fn))
        base = fn[:-5]
        photos = []
        for i, p in enumerate(c.get("photos") or [], 1):
            data = re.sub(r"^data:[^,]+,", "", p.get("data", ""))
            out = os.path.join(PHONE, f"{base}-{i}.jpg")
            with open(out, "wb") as fh:
                fh.write(base64.b64decode(data))
            photos.append({"step": i, "caption": p.get("caption", ""), "file": out})
        date = c.get("date")
        path = base.replace("_", "/", 1) if "_" in base[:11] else f"{date}/{base}"
        cap = {"inboxPath": path + ".json", "date": date, "time": c.get("time"), "meal": c.get("meal") or "",
               "hunger": c.get("hunger"), "note": c.get("note") or "", "photos": photos,
               "test": bool(re.search(r"\btest\b", c.get("note") or "", re.I))}
        t = mins(c.get("time"))
        cand = []
        for m in (days.get(date) or {}).get("meals", []):
            mt = mins(m.get("time"))
            if t is not None and mt is not None and abs(mt - t) <= MATCH_MIN:
                cand.append({"mealId": m["id"], "name": m.get("name"), "time": m.get("time"), "tags": m.get("tags", []),
                             "items": [i.get("n") for i in m.get("items", [])]})
        cap["duplicateCandidates"] = cand  # LLM confirms "same food" before merging
        caps.append(cap)
    save(os.path.join(PHONE, "_staged.json"), {"staged": [c["inboxPath"] for c in caps]})
    print(json.dumps({"captures": caps}, indent=1, ensure_ascii=False))


# ---------- apply ----------
def check_items(items):
    errs = []
    for n, it in enumerate(items):
        for k, typ in ITEM_KEYS.items():
            if k not in it or not isinstance(it[k], typ):
                errs.append(f"item {n} ({it.get('n', '?')}): missing/invalid '{k}'")
        if it.get("fermented") not in (True, False, "unclear"):
            errs.append(f"item {n}: fermented must be true/false/\"unclear\"")
    return errs


def cmd_apply(a):
    day = day_body(load(a.day))
    meal = load(a.meal)
    meal.setdefault("id", "m" + str(int(time.time() * 1000)))
    meal.setdefault("tags", [])
    meal.setdefault("items", [])
    if meal.get("time") is not None and mins(meal["time"]) is None:
        sys.exit("meal.time must be HH:MM or null (untimed = missing data; never guess from the name)")
    errs = check_items(meal["items"])
    if errs:
        sys.exit("Invalid items:\n  " + "\n  ".join(errs))
    meals = day.setdefault("meals", [])
    if a.replace:
        idx = next((i for i, m in enumerate(meals) if m["id"] == a.replace), None)
        if idx is None:
            sys.exit(f"meal {a.replace} not in {day.get('date')}")
        old = meals[idx]
        for keep in ("photoAssets", "hunger"):  # keep app-side fields unless the new meal sets them
            if keep in old and keep not in meal:
                meal[keep] = old[keep]
        meal["id"] = old["id"]
        meals[idx] = meal
    else:
        meals.append(meal)
    out = a.out or a.day + ".new"
    save(out, day)
    print(f"wrote {out}  ({len(meals)} meals)")
    print_totals(day)


# ---------- totals ----------
def print_totals(day):
    tot = {"k": 0, "p": 0, "c": 0, "f": 0, "fi": 0}
    for m in day.get("meals", []):
        mt = {k: sum(float(i.get(k) or 0) for i in m.get("items", [])) for k in tot}
        for k in tot:
            tot[k] += mt[k]
        print(f"  {m.get('time') or '--:--'} {m.get('name', '')[:28]:28} {mt['k']:6.0f} kcal {mt['p']:5.1f} P {mt['c']:5.1f} C {mt['f']:5.1f} F {mt['fi']:4.1f} fib")
    print(f"  DAY {day.get('date')}: {tot['k']:.0f} kcal, {r1(tot['p'])} g protein, {r1(tot['c'])} g carbs, {r1(tot['f'])} g fat, {r1(tot['fi'])} g fiber")


def cmd_totals(a):
    print_totals(day_body(load(a.day)))


# ---------- done ----------
def cmd_done(a):
    st = os.path.join(PHONE, "_staged.json")
    staged = load(st)["staged"] if os.path.exists(st) else []
    p = os.path.join(DATA, "inbox-done.json")
    d = load(p)
    d["done"] = d["done"] + [x for x in staged if x not in d["done"]]
    save(p, d)
    shutil.rmtree(PHONE, ignore_errors=True)
    print(f"marked {len(staged)} done; cleared tools/queue/phone")


# ---------- garmin ----------
COLS = ["date", "steps", "restingHr", "minHr", "maxHr", "modMin", "vigMin", "hrZ2Min", "hrAboveMin", "wornMin"]


def cmd_garmin(a):
    pull = load(a.pull)  # {daily: {date: [steps,...]}, acts: [[startLocal, name, typeKey, min, avgHr, maxHr, meters]]}
    gd_p = os.path.join(DATA, "garmin-daily.json")
    gd = load(gd_p)
    rows = {(r["value"][0] if isinstance(r, dict) else r[0]): (r["value"] if isinstance(r, dict) else r) for r in gd["days"]}
    for date, vals in pull.get("daily", {}).items():
        if isinstance(vals, list) and len(vals) == len(COLS) - 1:
            rows[date] = [date] + vals
    gd["days"] = sorted(rows.values(), key=lambda r: r[0], reverse=True)
    gd["updated"] = datetime.now().strftime("%Y-%m-%d")
    save(gd_p, gd)
    ga_p = os.path.join(DATA, "garmin.json")
    ga = load(ga_p)
    have = {x.get("start") for x in ga["activities"]}
    added = 0
    for s, name, typ, mnt, avg, mx, meters in pull.get("acts", []):
        start = s[:16].replace(" ", "T")
        if start in have:
            continue
        act = {"start": start, "date": start[:10], "time": start[11:16], "type": (typ or "").replace("_", " ").title(),
               "title": name, "minutes": mnt, "avgHr": avg, "maxHr": mx}
        if meters:
            act["distanceMi"] = round(meters / 1609.34, 2)
        ga["activities"].append(act)
        added += 1
    ga["activities"].sort(key=lambda x: x.get("start", ""))
    save(ga_p, ga)
    daily_objs = [dict(zip(COLS, r)) for r in gd["days"]]
    save(os.path.join(OUT, "kv_garminDaily.json"), {"key": "garminDaily", "value": daily_objs})
    save(os.path.join(OUT, "kv_garmin.json"), {"key": "garmin", "value": ga["activities"]})
    print(f"garmin-daily: {len(pull.get('daily', {}))} day(s) merged; activities added: {added}")
    print("db docs ready: tools/fq/out/kv_garminDaily.json, tools/fq/out/kv_garmin.json (ArtifactData set kv/garminDaily, kv/garmin with if_version)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("stage"); s.add_argument("--days"); s.set_defaults(fn=cmd_stage)
    s = sp.add_parser("apply"); s.add_argument("--day", required=True); s.add_argument("--meal", required=True)
    s.add_argument("--replace"); s.add_argument("--out"); s.set_defaults(fn=cmd_apply)
    s = sp.add_parser("totals"); s.add_argument("--day", required=True); s.set_defaults(fn=cmd_totals)
    s = sp.add_parser("done"); s.set_defaults(fn=cmd_done)
    s = sp.add_parser("garmin"); s.add_argument("--pull", required=True); s.set_defaults(fn=cmd_garmin)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
