# Food Capture + Food Tracker: how it works

Two ways to log food, built so they never double-count.

```
 OFFLINE capture                         ONLINE app (main)
 Food Capture (this repo, GitHub Pages)  Food Tracker (private page on claude.ai)
 photo + note + time + hunger            log, review, edit, daily totals, trends
        |  uploads when online                 |  saves to the page's own database
        v  (token stays on the phone)          v
 private inbox repo  ------------------> Claude Code on the PC ("process my food queue")
                                         estimates photos, merges duplicates,
                                         pulls watch data, ships updates
```

| | Food Capture (offline) | Food Tracker (online) |
|---|---|---|
| Works with no signal | Yes: saves on the phone, sends when back online | No |
| Where photos go | A private GitHub inbox repo (needs a fine-grained token, entered on the phone only) | The page itself (no token) |
| Numbers right away | No: estimated later on the PC | Yes for typed food. Photos the phone app can't send are estimated from the note and marked "photo pending" |
| Photo check | Claude Code on the PC | Claude directly where allowed, otherwise Claude Code |

**Same meal in both:** when the queue is processed, a capture within ~45 minutes of a logged meal with
the same food (or a "photo pending" one) corrects that meal instead of adding a second one.

## Use Food Capture

1. In Safari open `https://pethebi.github.io/Personal/` → Share → **Add to Home Screen**.
   Always open it from the Home Screen icon: Safari tabs and Home Screen apps keep separate storage,
   and Safari clears a site's storage after ~7 days unused, which is why a saved token can disappear.
2. Settings → paste the GitHub token (fine-grained, only the inbox repo, Contents read/write).
3. **Add meal**: photos (in order, one meal built up step by step), a note, time, hunger 1–5. Save.
   "⏳ waiting to send" turns into "✓ sent" when online. Sent meals can't be edited here: fix them in the
   Food Tracker (tap the meal on the Daily tab).

## Privacy

This repo holds app code only. No meals, photos, profile or history are ever committed here.
