// Run on https://connect.garmin.com/modern/ (Mike's logged-in Chrome; never type his password).
// Returns JSON for the last 3 days: daily summary columns + recent activities. NO calorie fields (Mike's rule).
// Save the returned text to tools/fq/out/garmin-pull.json, then: python tools/fq/fq.py garmin --pull tools/fq/out/garmin-pull.json
await new Promise(r => setTimeout(r, 2000));
const h = { "connect-csrf-token": document.querySelector("meta[name=csrf-token]")?.content, nk: "NT" };
const g = u => fetch("/gc-api/" + u, { headers: h }).then(r => (r.ok ? r.json() : null));
const daily = {};
for (let i = 0; i < 3; i++) {
  const d = new Date(Date.now() - i * 864e5).toLocaleDateString("en-CA");
  const s = await g("usersummary-service/usersummary/daily?calendarDate=" + d);
  const hr = await g("wellness-service/wellness/dailyHeartRate?date=" + d);
  if (!s) continue;
  let z2 = 0, ab = 0, w = 0; const v = (hr && hr.heartRateValues) || [];
  for (let j = 0; j < v.length; j++) { const x = v[j][1]; if (x == null) continue; const dt = j + 1 < v.length ? (v[j + 1][0] - v[j][0]) / 60000 : 2; w += dt; if (x >= 110 && x <= 130) z2 += dt; else if (x > 130) ab += dt; }
  daily[d] = [s.totalSteps, s.restingHeartRate, s.minHeartRate, s.maxHeartRate, s.moderateIntensityMinutes, s.vigorousIntensityMinutes, Math.round(z2), Math.round(ab), Math.round(w)];
}
const acts = (await g("activitylist-service/activities/search/activities?limit=8")) || [];
JSON.stringify({ daily, acts: acts.map(a => [a.startTimeLocal, a.activityName, a.activityType && a.activityType.typeKey, Math.round(a.duration / 60), a.averageHR, a.maxHR, a.distance || 0]) })
