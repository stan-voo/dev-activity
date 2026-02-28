# Project activity tracking script
_Exported on 28/02/2026 at 17:16:31 CET from Cursor (2.5.26)_

---

**User**

I have an idea. I'd like to track the projects I am working on, and I put all of my working files in a dev folder on my local machine. Is it possible to create a script that will watch that folder for changes and create a GitHub-style graph that shows days of the month and colour-codes the projects I work on?

---

**Cursor**

Checking the workspace structure, then creating a file watcher and a GitHub-style activity graph generator.


Creating a Python solution that watches your dev folder and generates a GitHub-style activity graph. Checking for an existing dev path or Python setup:


Creating a single Python script with watch and graph subcommands, plus a requirements file and a short README.


Cleaning up the script: removing the unused `html_cells` logic and moving the `calendar` import to the top.


Summary of what’s in place:

## `dev-activity/` – watcher + graph

**1. Watch your dev folder**

- **`python dev_activity.py watch`** — Watches `~/dev` (or `DEV_FOLDER` / a path you pass) and logs every file change to `activity.jsonl`.
- **Project** = first folder under that root (e.g. `~/dev/pkm-iv/foo/bar.py` → project `pkm-iv`).

**2. Generate the graph**

- **`python dev_activity.py graph`** — Reads `activity.jsonl` and writes **`activity-graph.html`**.
- **`python dev_activity.py graph --open`** — Same, then opens the HTML in your browser.

The graph is GitHub-style: one row per month, one small square per day. Each day is colored by the project with the most activity that day; intensity (darker/lighter) reflects how much activity. Hover shows the date and project counts. A legend lists all projects and their colors.

**Setup:**

```bash
cd /Users/stan/dev/pkm-iv/dev-activity
pip install -r requirements.txt
```

Then, in one terminal (or in the background), start the watcher so it keeps logging:

```bash
python dev_activity.py watch
```

Use your real dev folder if it’s not `~/dev`:

```bash
python dev_activity.py watch /Users/stan/dev
```

When you want to see the graph, run (from the same directory so it finds `activity.jsonl`):

```bash
python dev_activity.py graph --open
```

`activity.jsonl` is append-only, so you can stop/restart the watcher without losing history. For an empty log, the graph still renders; it just shows no activity until you’ve had the watcher running for a while.

---

**User**

I'm currently in the pkm-IV folder that is inside the dev folder. How do I move all of this there?

---

**Cursor**

Moving the dev-activity tool from `~/dev/pkm-iv/dev-activity` to `~/dev/dev-activity` so it sits alongside your projects and the watcher can track all of them (including pkm-iv).


Creating the tool in `~/dev/dev-activity` and removing it from `pkm-iv`.


Removing the old copy from pkm-iv:


Summary of what’s done:

**Moved to `~/dev/dev-activity/`**

- **`/Users/stan/dev/dev-activity/requirements.txt`**
- **`/Users/stan/dev/dev-activity/dev_activity.py`**
- **`/Users/stan/dev/dev-activity/README.md`**

The old files under `pkm-iv/dev-activity/` are removed. If the folder is still there and empty, you can delete it with:

```bash
rmdir /Users/stan/dev/pkm-iv/dev-activity
```

**Using it from the new location**

```bash
cd ~/dev/dev-activity
pip install -r requirements.txt
python dev_activity.py watch          # watches ~/dev, logs to this folder
python dev_activity.py graph --open   # build and open the graph
```

The README there is updated so all instructions use `~/dev/dev-activity` and `~/dev`. The watcher will track every project under `~/dev` (including pkm-iv), and the log and graph stay in `~/dev/dev-activity` instead of inside one project.

---

**User**

@/Users/stan/.cursor/projects/Users-stan-dev-pkm-iv/terminals/4.txt:21-22 

---

**Cursor**

`pip` isn’t on your PATH (common on macOS). Use the module form instead:

```bash
python3 -m pip install -r requirements.txt
```

If you use a virtual environment, activate it first, then run the same command from inside it.

---

**User**

@/Users/stan/.cursor/projects/Users-stan-dev-pkm-iv/terminals/4.txt:26-54 

---

**Cursor**

Adding a virtual environment and updating the README with setup steps:


Your system Python is “externally managed,” so install into a venv instead. Run:

```bash
cd ~/dev/dev-activity
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

After that, whenever you use this project in a new terminal, activate the venv first:

```bash
cd ~/dev/dev-activity
source .venv/bin/activate
```

Then run `python dev_activity.py watch` or `python dev_activity.py graph --open` as usual.

The README is updated with these venv steps, and a `.gitignore` was added so `.venv/`, `activity.jsonl`, and `activity-graph.html` aren’t committed if you put the project in git.

---

**User**

@/Users/stan/.cursor/projects/Users-stan-dev-pkm-iv/terminals/4.txt:58-81 

---

**Cursor**

The watcher is running correctly: it’s watching `/Users/stan/dev` and writing events to `activity.jsonl`.

**Next steps:**

- **Leave it running** in that terminal (or run it in the background) while you work in projects under `~/dev`. Every file change will be logged.
- **View the graph** in another terminal:
  ```bash
  cd ~/dev/dev-activity
  source .venv/bin/activate
  python dev_activity.py graph --open
  ```
  Run this whenever you want to refresh the graph; more activity in `activity.jsonl` will make the calendar fill in over time.

---

**User**

How do I make it run whenever, even if the terminal is closed?

---

**Cursor**

Creating a macOS LaunchAgent so the watcher runs in the background and starts at login, and adding setup instructions to the README.


Checking the file on disk:


Summary of what’s in place:

**1. LaunchAgent plist** — `~/dev/dev-activity/dev-activity.watcher.plist`

It’s set up to:
- Use your venv Python and the `dev_activity.py watch` command
- Use `~/dev/dev-activity` as the working directory
- Start when you log in (`RunAtLoad`)
- Restart if it exits (`KeepAlive`)
- Send stdout/stderr to `watch.log` and `watch.err` in that folder

**2. Steps to use it**

```bash
# One-time: copy the plist into LaunchAgents
cp ~/dev/dev-activity/dev-activity.watcher.plist ~/Library/LaunchAgents/

# Start the watcher (and have it start at login from now on)
launchctl load ~/Library/LaunchAgents/dev-activity.watcher.plist
```

After that, the watcher keeps running when you close the terminal and will start again after a reboot.

**Stop it when you want:**

```bash
launchctl unload ~/Library/LaunchAgents/dev-activity.watcher.plist
```

**Check that it’s running:**

```bash
launchctl list | grep dev.activity
```

If your home directory is not `/Users/stan`, open `dev-activity.watcher.plist` and replace `/Users/stan` with your actual home path in the `ProgramArguments`, `WorkingDirectory`, `StandardOutPath`, and `StandardErrorPath` entries. The README in `~/dev/dev-activity` has been updated with this LaunchAgent section.

---

**User**

@/Users/stan/.cursor/projects/Users-stan-dev-pkm-iv/terminals/4.txt:83-90 

---

**Cursor**

Those errors happen because the pasted block included the `#` comment lines, and zsh tried to interpret them. Run only these two commands (no comments):

```bash
cp ~/dev/dev-activity/dev-activity.watcher.plist ~/Library/LaunchAgents/
```

```bash
launchctl load ~/Library/LaunchAgents/dev-activity.watcher.plist
```

Run the first, then the second. After that, the watcher should be running in the background.

---

**User**

@/Users/stan/.cursor/projects/Users-stan-dev-pkm-iv/terminals/4.txt:92-95 

---

**Cursor**

Checking the plist and common causes of "Load failed: 5":


Checking whether the job is already loaded or the plist path is wrong, and fixing the plist.


The job is already loaded and running. `launchctl list` shows:

```text
45461  0  dev.activity.watcher
```

So the watcher is active; "Load failed: 5" usually means you tried to load it again while it was already loaded.

**You don’t need to do anything** — the dev-activity watcher should already be running in the background.

If you want to **restart** it (e.g. after changing the plist):

```bash
launchctl unload ~/Library/LaunchAgents/dev-activity.watcher.plist
launchctl load ~/Library/LaunchAgents/dev-activity.watcher.plist
```

To confirm it’s writing events, check that the log is growing:

```bash
wc -l ~/dev/dev-activity/activity.jsonl
```

Edit a file under `~/dev`, run `wc -l` again, and the line count should increase.

---

**User**

@/Users/stan/.cursor/projects/Users-stan-dev-pkm-iv/terminals/4.txt:95-97 

---

**Cursor**

15,489 lines means the watcher is running and has been recording file changes.

To see the graph:

```bash
cd ~/dev/dev-activity
source .venv/bin/activate
python dev_activity.py graph --open
```

That will build the calendar from the log and open it in your browser.

---

**User**

Please make sure that a @README.md  file includes instructions on how to stop the script from loading on my Mac and how to start it back.

---

**Cursor**

Clarifying one detail: after `unload`, the plist remains in LaunchAgents, so the watcher will start again on next login. Adding a short note on how to keep it stopped across reboots:


Summary of what was added to the README:

**Stop the watcher**
- **Command:** `launchctl unload ~/Library/LaunchAgents/dev-activity.watcher.plist`
- Stops the watcher right away.
- It will start again on the next login because the plist is still in LaunchAgents.
- To have it stay stopped after a reboot: after unloading, move the plist out of `~/Library/LaunchAgents/` (e.g. back to `~/dev/dev-activity/`). To use it again later, put the plist back and run the load command.

**Start the watcher**
- **Command:** `launchctl load ~/Library/LaunchAgents/dev-activity.watcher.plist`
- Starts the watcher and keeps it set to run on future logins (as long as the plist is in LaunchAgents).

There’s also a **Check if it's running** section with the `launchctl list | grep dev.activity` command.

