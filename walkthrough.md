# Dev Activity: setup and usage

*2026-02-28T16:30:00Z by Showboat 0.6.1*
<!-- showboat-id: a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d -->

**Dev Activity** watches a folder of projects (e.g. your `~/dev` directory) for file changes and generates a **GitHub-style activity graph**. Each day is a small square; color indicates which project you worked in, and intensity reflects how much activity happened that day.

This walkthrough is a **showboat** demo document: it mixes commentary, executable code blocks, and captured output. You can re-run all code blocks and confirm outputs match with:

```bash
uvx showboat verify walkthrough.md
```

If everything matches, the demo is still valid. (Showboat: *Create executable demo documents that show and prove an agent's work.*)

---

**1. Project layout** — From the dev-activity directory: script, requirements, README, and (after setup) a virtual environment.

```bash
ls dev_activity.py requirements.txt README.md dev-activity.watcher.plist 2>/dev/null
```

```output
README.md
dev-activity.watcher.plist
dev_activity.py
requirements.txt
```

**2. Setup** — Create a virtual environment and install the watchdog dependency (recommended on macOS with Homebrew Python).

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt && echo 'Ready.'
```

```output
Ready.
```

**3. Generate the graph** — With activity already logged, generate the GitHub-style calendar HTML. Use `--open` to open it in your browser.

```bash
. .venv/bin/activate && python dev_activity.py graph
```

```output
Wrote /Users/stan/dev/dev-activity/activity-graph.html
```

**4. Run in the background (LaunchAgent)** — On macOS you can run the watcher as a LaunchAgent so it starts at login and keeps running.

- **Stop it** (stops now; will start again next login unless you move the plist out): `launchctl unload ~/Library/LaunchAgents/dev-activity.watcher.plist`
- **Start it**: `launchctl load ~/Library/LaunchAgents/dev-activity.watcher.plist`

```bash
launchctl list | grep -q dev.activity && echo 'Watcher is running (LaunchAgent loaded).' || echo 'Watcher is not loaded.'
```

```output
Watcher is running (LaunchAgent loaded).
```

See **README.md** for full details: one-time plist copy, optional run-from-terminal, and graph `--open`.
