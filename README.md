# Dev Activity

**Dev Activity** watches a folder of projects (e.g. your `~/dev` directory) for file changes and generates a **GitHub-style activity graph**. Each day is a small square; color indicates which project (top-level subfolder) you worked in, and intensity reflects how much activity happened that day.

## Walkthrough

**[walkthrough.md](walkthrough.md)** is a step-by-step demo of this project. It’s a [showboat](https://github.com/simonw/showboat) document: it mixes commentary, executable bash blocks, and captured output. You can read it as a guide and run the commands yourself, or verify that the recorded outputs still match by running:

```bash
uvx showboat verify walkthrough.md
```

If every code block runs and the outputs match, the walkthrough is still valid.

## Setup

Use a virtual environment (recommended on macOS with Homebrew Python):

```bash
cd ~/dev/dev-activity
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Each time you open a new terminal to run the watcher or graph, activate the venv first:

```bash
cd ~/dev/dev-activity
source .venv/bin/activate
```

## Usage

**1. Watch your dev folder** (run in the background or in a dedicated terminal):

```bash
cd ~/dev/dev-activity
source .venv/bin/activate
python dev_activity.py watch
```

This watches `~/dev` by default and appends activity to `activity.jsonl` in this directory. Every file create/modify/move under `~/dev` is logged with the date and the **project name** (the first folder under the dev root, e.g. `~/dev/pkm-iv/...` → project `pkm-iv`).

Override the folder:

```bash
python dev_activity.py watch /path/to/your/dev
# or
export DEV_FOLDER=/path/to/your/dev
python dev_activity.py watch
```

**2. Generate the graph**

```bash
cd ~/dev/dev-activity
python dev_activity.py graph
```

Writes `activity-graph.html` here. Open it in a browser to see the calendar: each day is a small square; color = project, intensity = amount of activity that day.

To generate and open in your default browser:

```bash
python dev_activity.py graph --open
```

## Files

| File                 | Purpose |
|----------------------|--------|
| `activity.jsonl`     | Log of events (one JSON object per line). Keep this file to preserve history. |
| `activity-graph.html`| Generated graph. Regenerate anytime with `graph`. |

## Run in the background (survives closing the terminal)

On macOS you can run the watcher as a **LaunchAgent** so it starts when you log in and keeps running until you stop it.

### One-time setup

Copy the plist into your LaunchAgents folder (edit the paths inside the plist first if your home directory isn't `/Users/stan`):

```bash
cp ~/dev/dev-activity/dev-activity.watcher.plist ~/Library/LaunchAgents/
```

### Stop the watcher (don't run on login)

To stop the watcher and prevent it from starting when you log in:

```bash
launchctl unload ~/Library/LaunchAgents/dev-activity.watcher.plist
```

The watcher will exit immediately. Because the plist stays in `LaunchAgents`, it will start again the next time you log in. To keep it stopped across reboots, move the plist out of that folder (e.g. back to `~/dev/dev-activity/`) after unloading; put it back and run `launchctl load` when you want to use it again.

### Start the watcher (run in background, including on login)

To start the watcher again (and have it start automatically on future logins):

```bash
launchctl load ~/Library/LaunchAgents/dev-activity.watcher.plist
```

### Check if it's running

```bash
launchctl list | grep dev.activity
```

If you see `dev.activity.watcher` in the output, the watcher is running. If you see nothing, it's stopped.

If the watcher crashes it will be restarted automatically. Log output goes to `watch.log` and `watch.err` in `~/dev/dev-activity/`.

## Tips

- Run `watch` in a terminal when you want it on demand, or use the LaunchAgent above for always-on.
- The activity log is append-only, so you can stop and restart without losing data.
- Run `graph` whenever you want to refresh the view (e.g. daily or weekly).
- To use a different log file: `python dev_activity.py graph --log mylog.jsonl`
