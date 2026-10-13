# For any AI agent working in this folder

This is Mike's Food Tracker. Start here, whatever model or tool you are:

1. `CLAUDE.md` — the owner's rules, targets, data model. Kept only on the owner's PC (personal health data), not in this repo.
2. `README.md` — how the online app, the offline uploader and the PC tooling fit together.
3. Task playbooks (plain Markdown, readable by any agent):
   - Logging food / "process my queue" / Garmin → `docs/process-food-queue.md (public copy; the live one is .claude/skills/process-food-queue/SKILL.md)`
   - Building, fixing or shipping the app → `docs/food-app-dev.md (public copy; live: .claude/skills/food-app-dev/SKILL.md)`

Deterministic helpers live in `tools/fq/` (`python tools/fq/fq.py --help`). Prefer them over ad-hoc code;
the only judgment step is estimating nutrition from photos and notes.
