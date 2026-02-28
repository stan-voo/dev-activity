#!/usr/bin/env python3
"""
Watch a dev folder for file changes and generate a GitHub-style activity graph
color-coded by project (top-level subfolder).

Usage:
  python dev_activity.py watch [path]     # Watch path (default: ~/dev), log activity
  python dev_activity.py graph [path]     # Generate activity-graph.html from log
  python dev_activity.py graph --open     # Generate and open in browser

Set DEV_FOLDER to override default watch path. Log is stored in activity.jsonl
in the current working directory.
"""

import argparse
import calendar
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Default folder to watch (override with DEV_FOLDER env)
DEFAULT_DEV_FOLDER = os.path.expanduser("~/dev")
LOG_FILENAME = "activity.jsonl"
GRAPH_FILENAME = "activity-graph.html"

# Path segments to ignore (noise: build artifacts, caches, tools)
IGNORED_PATH_PARTS = frozenset({
    ".git", "node_modules", ".venv", "__pycache__", ".cursor", ".idea",
    "dist", "build", ".next", ".turbo", ".cache", "vendor", ".DS_Store",
})

# Only log at most one entry per project per this many seconds
DEBOUNCE_SECONDS = 300  # 5 minutes

# Projects to never log (e.g. the watcher project itself)
IGNORED_PROJECTS = frozenset({"dev-activity"})

# Distinct hues for projects (HSV-style, then we'll use HSL in CSS)
PROJECT_HUES = [
    0, 30, 60, 120, 180, 220, 260, 300,  # red, orange, yellow, green, cyan, blue, purple, magenta
]


def get_project_name(dev_root: Path, event_path: str) -> str | None:
    """Return the top-level project folder name under dev_root, or None."""
    try:
        full = Path(event_path).resolve()
        root = dev_root.resolve()
        if full == root or not str(full).startswith(str(root)):
            return None
        rel = full.relative_to(root)
        parts = rel.parts
        if not parts:
            return None
        return parts[0]
    except (ValueError, OSError):
        return None


def should_ignore_path(path: Path, log_path: Path, graph_path: Path) -> bool:
    """True if this path should not be logged (noise or our own output)."""
    try:
        resolved = path.resolve()
        if resolved == log_path.resolve() or resolved == graph_path.resolve():
            return True
        for part in resolved.parts:
            if part in IGNORED_PATH_PARTS:
                return True
    except (ValueError, OSError):
        pass
    return False


def log_activity(log_path: Path, dev_root: Path, project: str) -> None:
    """Append one activity entry to the log file."""
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "ts": datetime.now().isoformat(),
        "project": project,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def run_watch(dev_folder: str) -> None:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print("Install watchdog: pip install watchdog", file=sys.stderr)
        sys.exit(1)

    dev_path = Path(dev_folder)
    if not dev_path.is_dir():
        print(f"Dev folder does not exist: {dev_path}", file=sys.stderr)
        sys.exit(1)

    log_path = Path.cwd() / LOG_FILENAME
    graph_path = Path.cwd() / GRAPH_FILENAME

    class ActivityHandler(FileSystemEventHandler):
        def __init__(self):
            super().__init__()
            self._dev_root = dev_path
            self._log_path = log_path
            self._graph_path = graph_path
            self._last_log: dict[str, float] = {}

        def _record(self, src_path: str) -> None:
            path = Path(src_path)
            if should_ignore_path(path, self._log_path, self._graph_path):
                return
            project = get_project_name(self._dev_root, src_path)
            if not project or project in IGNORED_PROJECTS:
                return
            now = datetime.now().timestamp()
            last = self._last_log.get(project, 0)
            if now - last < DEBOUNCE_SECONDS:
                return
            self._last_log[project] = now
            log_activity(self._log_path, self._dev_root, project)

        def on_created(self, event):
            if not event.is_directory:
                self._record(event.src_path)

        def on_modified(self, event):
            if not event.is_directory:
                self._record(event.src_path)

        def on_moved(self, event):
            if not event.is_directory and event.dest_path:
                self._record(event.dest_path)

        def on_deleted(self, event):
            if not event.is_directory:
                self._record(event.src_path)

    handler = ActivityHandler()
    observer = Observer()
    observer.schedule(handler, str(dev_path), recursive=True)
    observer.start()
    print(f"Watching {dev_path} — activity logged to {log_path}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        while True:
            observer.join(timeout=1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()


def load_activity(log_path: Path) -> dict[str, dict[str, int]]:
    """Load log and return date -> { project -> count }."""
    by_date = defaultdict(lambda: defaultdict(int))
    if not log_path.exists():
        return dict(by_date)
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                d = entry.get("date")
                p = entry.get("project")
                if d and p:
                    by_date[d][p] += 1
            except json.JSONDecodeError:
                continue
    return {d: dict(by_date[d]) for d in sorted(by_date)}


def project_color(project: str, index: int) -> str:
    """Return CSS color for a project (distinct hue, fixed saturation/lightness)."""
    hue = PROJECT_HUES[index % len(PROJECT_HUES)]
    return f"hsl({hue}, 55%, 45%)"


def project_color_light(project: str, index: int) -> str:
    """Lighter shade for high-activity cells."""
    hue = PROJECT_HUES[index % len(PROJECT_HUES)]
    return f"hsl({hue}, 55%, 55%)"


def generate_graph(log_path: Path, out_path: Path, open_browser: bool) -> None:
    """Generate GitHub-style activity graph HTML."""
    activity = load_activity(log_path)
    if not activity:
        # Still write a graph so user sees the layout
        activity = {}

    # All unique projects in order of first appearance
    project_order: list[str] = []
    seen = set()
    for d in sorted(activity):
        for p in activity[d]:
            if p not in seen:
                seen.add(p)
                project_order.append(p)

    project_index = {p: i for i, p in enumerate(project_order)}
    color_for = lambda p: project_color(p, project_index[p])
    color_light_for = lambda p: project_color_light(p, project_index[p])

    # Date range: from first log to today, or last 12 months
    today = datetime.now().date()
    if activity:
        first = min(datetime.strptime(d, "%Y-%m-%d").date() for d in activity)
    else:
        first = today - timedelta(days=365)
    # Show full months
    start = first.replace(day=1)
    end = today
    months: list[tuple[int, int]] = []  # (year, month)
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    # Layout: one row per month, cells for each day (with padding for day-of-week)
    month_rows: list[str] = []
    for year, month in months:
        ndays = calendar.monthrange(year, month)[1]
        row_cells = []
        # Padding for day-of-week alignment: 1st of month starts on a weekday
        first_weekday = datetime(year, month, 1).weekday()  # 0=Mon
        for _ in range(first_weekday):
            row_cells.append('<span class="cell empty"></span>')
        for day in range(1, ndays + 1):
            date_key = f"{year}-{month:02d}-{day:02d}"
            projs = activity.get(date_key, {})
            if not projs:
                row_cells.append(f'<span class="cell none" title="{date_key}"></span>')
                continue
            # Sort by count descending for stable stripe order
            proj_list = sorted(projs.items(), key=lambda x: -x[1])
            total = sum(projs.values())
            intensity = "high" if total >= 10 else "mid" if total >= 3 else "low"
            tip = ", ".join(f"{p}: {c}" for p, c in proj_list)
            if len(proj_list) == 1:
                p = proj_list[0][0]
                color = color_light_for(p) if intensity == "high" else color_for(p)
                row_cells.append(
                    f'<span class="cell {intensity}" style="background:{color}" title="{date_key}: {tip}"></span>'
                )
            else:
                # Multiple projects: horizontal stripes (gradient)
                stops = []
                for i, (p, c) in enumerate(proj_list):
                    color = color_light_for(p) if intensity == "high" else color_for(p)
                    pct = (sum(c for _, c in proj_list[:i]) / total) * 100
                    pct_next = (sum(c for _, c in proj_list[: i + 1]) / total) * 100
                    stops.append(f"{color} {pct}%")
                    stops.append(f"{color} {pct_next}%")
                gradient = "linear-gradient(to bottom, " + ", ".join(stops) + ")"
                row_cells.append(
                    f'<span class="cell {intensity}" style="background:{gradient}" title="{date_key}: {tip}"></span>'
                )
        month_label = datetime(year, month, 1).strftime("%b %Y")
        month_rows.append(
            f'<div class="month-row"><span class="month-label">{month_label}</span>'
            + '<div class="month-cells">' + "".join(row_cells) + "</div></div>"
        )

    legend = "".join(
        f'<span class="legend-item" style="background:{color_for(p)}"></span><span class="legend-name">{p}</span>'
        for p in project_order
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Dev activity</title>
  <style>
    :root {{ font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3; }}
    body {{ max-width: 900px; margin: 1rem auto; padding: 1rem; }}
    h1 {{ font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; }}
    .subtitle {{ color: #8b949e; font-size: 0.875rem; margin-bottom: 1rem; }}
    .grid {{ display: flex; flex-direction: column; gap: 4px; }}
    .month-row {{ display: flex; align-items: center; gap: 8px; }}
    .month-label {{ width: 64px; font-size: 11px; color: #8b949e; }}
    .month-cells {{ display: flex; flex-wrap: wrap; gap: 2px; }}
    .cell {{ width: 12px; height: 12px; border-radius: 2px; display: inline-block; }}
    .cell.empty {{ background: transparent; }}
    .cell.none {{ background: #21262d; }}
    .cell.low {{ opacity: 0.85; }}
    .cell.mid {{ opacity: 1; }}
    .cell.high {{ box-shadow: 0 0 0 1px rgba(255,255,255,0.2); }}
    .legend {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; margin-top: 1rem; font-size: 12px; }}
    .legend-item {{ width: 12px; height: 12px; border-radius: 2px; display: inline-block; }}
    .legend-name {{ color: #8b949e; }}
  </style>
</head>
<body>
  <h1>Dev activity</h1>
  <p class="subtitle">Days with file changes, by project (from activity log)</p>
  <div class="grid">
    {"".join(month_rows)}
  </div>
  <div class="legend">
    {legend}
  </div>
</body>
</html>
"""

    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")

    if open_browser:
        import webbrowser
        webbrowser.open(f"file://{out_path.resolve()}")


def run_backfill_github(log_path: Path, year: int, month: int) -> None:
    """Append GitHub commit activity for the given month to the log (uses gh CLI)."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "-q", ".login"],
            capture_output=True,
            text=True,
            check=True,
        )
        username = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        if isinstance(e, FileNotFoundError):
            print("gh CLI not found. Install it: https://cli.github.com/", file=sys.stderr)
        else:
            print("Run 'gh auth login' to authenticate.", file=sys.stderr)
        sys.exit(1)

    # gh search commits returns commits; we filter by month in Python
    result = subprocess.run(
        [
            "gh", "search", "commits",
            f"--author={username}",
            "--json", "repository,commit",
            "--limit", "1000",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "gh search failed").strip()
        print(f"GitHub error: {msg}", file=sys.stderr)
        sys.exit(1)

    try:
        items = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Failed to parse gh output: {e}", file=sys.stderr)
        sys.exit(1)

    prefix = f"{year}-{month:02d}-"
    entries: list[tuple[str, str, str]] = []  # (date, project, ts)
    for item in items:
        try:
            commit = item.get("commit") or {}
            committer = commit.get("committer") or {}
            date_str = committer.get("date")
            if not date_str or not date_str.startswith(prefix):
                continue
            day = date_str[:10]
            repo = (item.get("repository") or {}).get("name") or "unknown"
            entries.append((day, repo, date_str))
        except (KeyError, TypeError):
            continue

    if not entries:
        print(f"No commits found for {year}-{month:02d}.")
        return

    with open(log_path, "a") as f:
        for day, project, ts in entries:
            entry = {
                "date": day,
                "ts": ts.replace("Z", "+00:00") if ts.endswith("Z") else ts,
                "project": project,
            }
            f.write(json.dumps(entry) + "\n")

    print(f"Appended {len(entries)} entries from GitHub ({year}-{month:02d}) to {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Track dev folder activity and show GitHub-style graph")
    sub = parser.add_subparsers(dest="cmd", required=True)
    watch_parser = sub.add_parser("watch", help="Watch dev folder and log file changes")
    watch_parser.add_argument("path", nargs="?", default=os.environ.get("DEV_FOLDER", DEFAULT_DEV_FOLDER), help="Folder to watch (default: ~/dev or DEV_FOLDER)")
    graph_parser = sub.add_parser("graph", help="Generate activity graph HTML")
    graph_parser.add_argument("--open", action="store_true", help="Open graph in browser after generating")
    graph_parser.add_argument("--log", default=LOG_FILENAME, help="Activity log file (default: activity.jsonl)")
    backfill_parser = sub.add_parser("backfill-github", help="Append GitHub commit activity for a month (requires gh CLI)")
    backfill_parser.add_argument("--month", type=int, default=None, help="Month (1-12, default: current)")
    backfill_parser.add_argument("--year", type=int, default=None, help="Year (default: current)")
    backfill_parser.add_argument("--log", default=LOG_FILENAME, help="Activity log file (default: activity.jsonl)")
    args = parser.parse_args()

    if args.cmd == "watch":
        run_watch(args.path)
    elif args.cmd == "backfill-github":
        now = datetime.now()
        year = args.year if args.year is not None else now.year
        month = args.month if args.month is not None else now.month
        run_backfill_github(Path(args.log), year, month)
    else:
        log_path = Path(args.log)
        out_path = Path.cwd() / GRAPH_FILENAME
        generate_graph(log_path, out_path, getattr(args, "open", False))


if __name__ == "__main__":
    main()
