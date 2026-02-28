# Dev Activity: setup and usage

*2026-02-28T16:17:49Z by Showboat 0.6.1*
<!-- showboat-id: e9626d4d-b99b-4b7a-ac70-05a881cb75ef -->

Dev Activity watches your `~/dev` folder for file changes and builds a GitHub-style calendar graph color-coded by project. This walkthrough sets up the tool and shows how to run it.

**1. Project layout** — From the dev-activity directory we have the script, requirements, and (after setup) a virtual environment.

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

[notice] A new release of pip is available: 26.0 -> 26.0.1
[notice] To update, run: pip install --upgrade pip
Ready.
```

**3. Generate the graph** — With activity already logged, generate the GitHub-style calendar HTML. Use `--open` to open it in your browser.

```bash
. .venv/bin/activate && python dev_activity.py graph
```

```output
Wrote /Users/stan/dev/dev-activity/activity-graph.html
```

**4. Run in the background (LaunchAgent)** — On macOS you can run the watcher as a LaunchAgent so it starts at login and keeps running. **Stop it** (stops now; will start again next login unless you move the plist out): `launchctl unload ~/Library/LaunchAgents/dev-activity.watcher.plist` **Start it**: `launchctl load ~/Library/LaunchAgents/dev-activity.watcher.plist`

```bash
launchctl list | grep -q dev.activity && echo 'Watcher is running (LaunchAgent loaded).' || echo 'Watcher is not loaded.'
```

```output
Watcher is running (LaunchAgent loaded).
```

See **README.md** for full details: one-time plist copy, optional run-from-terminal, and graph `--open`.
