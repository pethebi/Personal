"""Garmin pull through Garmin's Personal API (Mike 11/8; replaces the Chrome garmin-pull.js when the key works).

Key: Windows user env var GARMIN_API_KEY (Mike set it himself; read from the process env or HKCU\\Environment).
NEVER print, log or write the key or the access token.

Writes tools/fq/out/garmin-pull.json in the same shape garmin-pull.js returns, then:
  python tools/fq/fq.py garmin --pull tools/fq/out/garmin-pull.json
Usage: python tools/fq/garmin_api.py [--days 3] [--acts 8] [--probe] [--merge-kv DIR]
  --merge-kv DIR (cloud / no PC files, 11/8): DIR holds kv/garmin.json + kv/garminDaily.json as ArtifactData `get`
  out_dir wrote them; writes DIR/kv_garmin.json + DIR/kv_garminDaily.json ready for ArtifactData set (pin if_version).
  --probe: only check the key works and list the field names of one daily summary + one activity (no values).
No calorie fields are used (Mike's rule).
"""
import argparse, datetime as dt, json, os, sys, urllib.request, urllib.error
from pathlib import Path

HOST = "https://personal.connectapi.garmin.com"
OUT = Path(__file__).resolve().parent / "out" / "garmin-pull.json"


def api_key():
    k = os.environ.get("GARMIN_API_KEY")
    if not k and sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
            i = 0
            while True:
                try:
                    name, val, _ = winreg.EnumValue(h, i)
                except OSError:
                    break
                if name.upper() == "GARMIN_API_KEY":
                    k = val
                    break
                i += 1
    if not k:
        sys.exit("GARMIN_API_KEY is not set (Windows: Edit environment variables for your account).")
    return k.strip()


def call(path, auth, method="GET"):
    req = urllib.request.Request(HOST + path, method=method, headers={"Authorization": auth, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            if not body:
                return None
            try:
                return json.loads(body)
            except ValueError:
                return body.decode("utf-8", "replace").strip()  # token endpoint replies with plain text
    except urllib.error.HTTPError as e:
        if e.code in (204, 404):
            return None
        sys.exit(f"Garmin API {method} {path.split('?')[0]} -> HTTP {e.code}")


def token():
    t = call("/personalapitoken-service/personal-api/personal-api-key/token", "ApiKey " + api_key(), "POST")
    if isinstance(t, dict):
        for k in ("access_token", "accessToken", "token"):
            if t.get(k):
                return "Bearer " + t[k]
        sys.exit("Token reply had no token field; fields: " + ", ".join(sorted(t)))
    if isinstance(t, str) and t:
        return "Bearer " + t
    sys.exit("Token reply was empty.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--acts", type=int, default=8)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--merge-kv")
    a = ap.parse_args()
    auth = token()
    today = dt.date.today()
    if a.probe:
        s = call(f"/usersummary-service/usersummary/daily?calendarDate={today}", auth)
        acts = call(f"/activitylist-service/activities/search/activities?limit=1", auth) or []
        print("token ok")
        print("daily fields:", ", ".join(sorted(s)) if isinstance(s, dict) else type(s).__name__)
        print("activity fields:", ", ".join(sorted(acts[0])) if acts else "none")
        return
    daily = {}
    for i in range(a.days):
        d = (today - dt.timedelta(days=i)).isoformat()
        s = call(f"/usersummary-service/usersummary/daily?calendarDate={d}", auth)
        hr = call(f"/wellness-service/wellness/dailyHeartRate?date={d}", auth)
        if not isinstance(s, dict):
            continue
        z2 = ab = w = 0.0
        v = (hr or {}).get("heartRateValues") or []
        for j, (t0, x) in enumerate(v):
            if x is None:
                continue
            step = (v[j + 1][0] - t0) / 60000 if j + 1 < len(v) else 2
            w += step
            if 110 <= x <= 130:
                z2 += step
            elif x > 130:
                ab += step
        daily[d] = [s.get("totalSteps"), s.get("restingHeartRate"), s.get("minHeartRate"), s.get("maxHeartRate"),
                    s.get("moderateIntensityMinutes"), s.get("vigorousIntensityMinutes"), round(z2), round(ab), round(w)]
    acts = call(f"/activitylist-service/activities/search/activities?limit={a.acts}", auth) or []
    zones, devs, rows = [], [], []
    for x in acts:
        rows.append([x.get("startTimeLocal"), x.get("activityName"), (x.get("activityType") or {}).get("typeKey"),
                     round((x.get("duration") or 0) / 60), x.get("averageHR"), x.get("maxHR"), x.get("distance") or 0])
        z = [round(x.get(f"hrTimeInZone_{n}") or 0) for n in range(1, 6)]
        if any(z):
            zones.append([x.get("startTimeLocal"), x.get("activityId"), z, [97, 116, 135, 154, 174]])  # zone lows as pulled 11/7 (list endpoint has no boundaries)
        devs.append([x.get("startTimeLocal"), x.get("activityId"), x.get("deviceId") or 0, x.get("manufacturer") or ""])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"daily": daily, "acts": rows, "zones": zones, "devs": devs}), encoding="utf-8")
    print(f"wrote {OUT}: {len(daily)} day(s), {len(rows)} activities, {len(zones)} with zone time")
    if a.merge_kv:
        merge_kv(Path(a.merge_kv), daily, rows, zones)


COLS = ["date", "steps", "restingHr", "minHr", "maxHr", "modMin", "vigMin", "hrZ2Min", "hrAboveMin", "wornMin"]  # = fq.py COLS


def merge_kv(d, daily, rows, zones):
    """Same merge as fq.py garmin, but on the db docs themselves (no tools/data history needed)."""
    val = lambda f: (lambda x: x.get("value", x.get("data", {}).get("value") if isinstance(x.get("data"), dict) else None))(json.loads((d / "kv" / f).read_text(encoding="utf-8")))
    days = {r["date"]: r for r in (val("garminDaily.json") or [])}
    for date, v in daily.items():
        days[date] = dict(zip(COLS, [date] + v))
    acts = val("garmin.json") or []
    have = {x.get("start") for x in acts}
    zs = {str(z[0])[:16].replace(" ", "T"): z[2] for z in zones}
    added = 0
    for s, name, typ, mnt, avg, mx, meters in rows:
        start = (s or "")[:16].replace(" ", "T")
        if not start or start in have:
            continue
        x = {"start": start, "date": start[:10], "time": start[11:16], "type": (typ or "").replace("_", " ").title(), "title": name, "minutes": mnt, "avgHr": avg, "maxHr": mx}
        if meters:
            x["distanceMi"] = round(meters / 1609.34, 2)
        acts.append(x); added += 1
    for x in acts:
        if x.get("start") in zs and not x.get("zs"):
            x["zs"] = zs[x["start"]]
    acts.sort(key=lambda x: x.get("start", ""))
    (d / "kv_garminDaily.json").write_text(json.dumps({"key": "garminDaily", "value": sorted(days.values(), key=lambda r: r["date"], reverse=True)}), encoding="utf-8")
    (d / "kv_garmin.json").write_text(json.dumps({"key": "garmin", "value": acts}), encoding="utf-8")
    print(f"merged: {len(daily)} day(s), {added} new activities -> {d}/kv_garmin.json, kv_garminDaily.json")


if __name__ == "__main__":
    main()
