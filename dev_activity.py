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
import html
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
ARCHIVE_FILENAME = "archived-projects.json"

# Path segments to ignore (noise: build artifacts, caches, tools)
IGNORED_PATH_PARTS = frozenset({
    ".git", "node_modules", ".venv", "__pycache__", ".cursor", ".idea",
    "dist", "build", ".next", ".turbo", ".cache", "vendor", ".DS_Store",
})

# Only log at most one entry per project per this many seconds
DEBOUNCE_SECONDS = 300  # 5 minutes

# Projects to never log (e.g. the watcher project itself). Comparison is case-insensitive.
IGNORED_PROJECTS = frozenset({"dev-activity", "PKM-IV", "pkm-iv.code-workspace", "pkm"})


def is_ignored_project(project: str) -> bool:
    """True if this project name should be excluded from logging and graph."""
    if not project:
        return True
    return project.upper() in {p.upper() for p in IGNORED_PROJECTS}

# Distinct hues for projects (HSV-style, then we'll use HSL in CSS)
PROJECT_HUES = [
    0, 30, 60, 120, 180, 220, 260, 300,  # red, orange, yellow, green, cyan, blue, purple, magenta
]

# Stripe overlays used only after we exhaust distinct base hues.
OVERFLOW_STRIPE_PATTERNS = [
    "repeating-linear-gradient(45deg, rgba(255,255,255,0.62) 0 2px, transparent 2px 5px)",
    "repeating-linear-gradient(-45deg, rgba(255,255,255,0.62) 0 2px, transparent 2px 5px)",
    "repeating-linear-gradient(0deg, rgba(255,255,255,0.56) 0 2px, transparent 2px 5px)",
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
            if not project or is_ignored_project(project):
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
                if d and p and not is_ignored_project(p):
                    by_date[d][p] += 1
            except json.JSONDecodeError:
                continue
    return {d: dict(by_date[d]) for d in sorted(by_date)}


def load_archived_projects(archive_path: Path) -> list[str]:
    """Load archived project names from JSON file."""
    if not archive_path.exists():
        return []
    try:
        data = json.loads(archive_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [str(item) for item in data if isinstance(item, str) and item.strip()]
    except (json.JSONDecodeError, OSError):
        return []


def save_archived_projects(archive_path: Path, projects: list[str]) -> None:
    """Persist archived project names to JSON file."""
    archive_path.write_text(json.dumps(projects, indent=2) + "\n", encoding="utf-8")


def run_archive_project(archive_path: Path, project: str) -> None:
    """Add one project to archive list."""
    name = project.strip()
    if not name:
        print("Project name cannot be empty.", file=sys.stderr)
        sys.exit(1)
    projects = load_archived_projects(archive_path)
    if any(p.casefold() == name.casefold() for p in projects):
        print(f"Project already archived: {name}")
        return
    projects.append(name)
    projects.sort(key=str.casefold)
    save_archived_projects(archive_path, projects)
    print(f"Archived project: {name}")


def run_unarchive_project(archive_path: Path, project: str) -> None:
    """Remove one project from archive list."""
    name = project.strip()
    if not name:
        print("Project name cannot be empty.", file=sys.stderr)
        sys.exit(1)
    projects = load_archived_projects(archive_path)
    remaining = [p for p in projects if p.casefold() != name.casefold()]
    if len(remaining) == len(projects):
        print(f"Project not archived: {name}")
        return
    save_archived_projects(archive_path, remaining)
    print(f"Unarchived project: {name}")


def run_list_archived_projects(archive_path: Path) -> None:
    """Print archived projects."""
    projects = load_archived_projects(archive_path)
    if not projects:
        print("No archived projects.")
        return
    print("Archived projects:")
    for p in projects:
        print(f"- {p}")


def project_color(project: str, index: int) -> str:
    """Return CSS color for a project (distinct hue, fixed saturation/lightness)."""
    hue = PROJECT_HUES[index % len(PROJECT_HUES)]
    return f"hsl({hue}, 55%, 45%)"


def project_color_light(project: str, index: int) -> str:
    """Lighter shade for high-activity cells."""
    hue = PROJECT_HUES[index % len(PROJECT_HUES)]
    return f"hsl({hue}, 55%, 55%)"


def project_pattern(index: int) -> str | None:
    """Return stripe overlay only when project index exceeds base hue palette."""
    palette_size = len(PROJECT_HUES)
    cycle = index // palette_size
    if cycle == 0:
        return None
    return OVERFLOW_STRIPE_PATTERNS[(cycle - 1) % len(OVERFLOW_STRIPE_PATTERNS)]


def generate_graph(log_path: Path, out_path: Path, open_browser: bool, archive_path: Path) -> None:
    """Generate GitHub-style activity graph HTML."""
    activity = load_activity(log_path)
    archived_projects = load_archived_projects(archive_path)
    archived_set = {p.casefold() for p in archived_projects}
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
    pattern_for = lambda p: project_pattern(project_index[p])

    def intensity_for_total(total: int) -> str:
        return "high" if total >= 10 else "mid" if total >= 3 else "low"

    def style_for_project(p: str, color: str) -> str:
        pattern = pattern_for(p)
        if pattern is None:
            return f"background:{color}"
        return f"background-image:{pattern}, linear-gradient({color}, {color})"

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
                # Weekend (Sat=5, Sun=6) with no activity: show as day off
                weekday = datetime(year, month, day).weekday()
                weekend_class = " weekend" if weekday >= 5 else ""
                row_cells.append(f'<span class="cell none{weekend_class}" title="{date_key}"></span>')
                continue
            # Sort by count descending for stable stripe order
            proj_list = sorted(projs.items(), key=lambda x: -x[1])
            total = sum(projs.values())
            intensity = intensity_for_total(total)
            tip = ", ".join(
                f"{p}{' (archived)' if p.casefold() in archived_set else ''}: {c}"
                for p, c in proj_list
            )
            tip_escaped = html.escape(f"{date_key}: {tip}", quote=True)
            project_data = html.escape("|".join(p for p, _ in proj_list), quote=True)
            project_counts_json = html.escape(json.dumps(proj_list), quote=True)
            if len(proj_list) == 1:
                p = proj_list[0][0]
                color = color_light_for(p) if intensity == "high" else color_for(p)
                row_cells.append(
                    f'<span class="cell project-cell {intensity}" data-date="{date_key}" data-projects="{project_data}" data-proj-counts="{project_counts_json}" style="{style_for_project(p, color)}" title="{tip_escaped}"></span>'
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
                    f'<span class="cell project-cell {intensity}" data-date="{date_key}" data-projects="{project_data}" data-proj-counts="{project_counts_json}" style="background:{gradient}" title="{tip_escaped}"></span>'
                )
        month_label = datetime(year, month, 1).strftime("%b %Y")
        month_rows.append(
            f'<div class="month-row"><span class="month-label">{month_label}</span>'
            + '<div class="month-cells">' + "".join(row_cells) + "</div></div>"
        )

    legend = "".join(
        (
            f'<span class="legend-entry" data-project="{html.escape(p, quote=True)}" data-archived="{"true" if p.casefold() in archived_set else "false"}">'
            f'<span class="legend-item" style="{style_for_project(p, color_for(p))}"></span>'
            f'<span class="legend-name">{html.escape(p)}</span>'
            "</span>"
        )
        for p in project_order
    )

    archived_json = json.dumps(sorted(archived_projects, key=str.casefold))
    project_styles = {
        p: {
            "lowColor": color_for(p),
            "highColor": color_light_for(p),
            "lowStyle": style_for_project(p, color_for(p)),
            "highStyle": style_for_project(p, color_light_for(p)),
        }
        for p in project_order
    }
    project_styles_json = json.dumps(project_styles)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Project activity</title>
  <style>
    :root {{ font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3; }}
    body {{ max-width: 900px; margin: 1rem auto; padding: 1rem; }}
    h1 {{ font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; }}
    .subtitle {{ color: #8b949e; font-size: 0.875rem; margin-bottom: 0.75rem; }}
    .controls {{ display: flex; align-items: center; gap: 12px; margin-bottom: 1rem; font-size: 13px; color: #c9d1d9; }}
    .controls label {{ display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }}
    .grid {{ display: flex; flex-direction: column; gap: 4px; }}
    .month-row {{ display: flex; align-items: center; gap: 8px; }}
    .month-label {{ width: 64px; font-size: 11px; color: #8b949e; }}
    .month-cells {{ display: flex; flex-wrap: wrap; gap: 2px; }}
    .cell {{ width: 12px; height: 12px; border-radius: 2px; display: inline-block; }}
    .cell.filtered {{ visibility: hidden; }}
    .cell.empty {{ background: transparent; }}
    .cell.none {{ background: #21262d; }}
    .cell.none.weekend {{ opacity: 0.45; background: linear-gradient(135deg, transparent 46%, rgba(255,255,255,0.12) 50%, transparent 54%), #21262d; }}
    .cell.low {{ opacity: 0.58; filter: saturate(0.72); }}
    .cell.mid {{ opacity: 0.94; }}
    .cell.high {{ box-shadow: 0 0 0 1px rgba(255,255,255,0.2); }}
    .intensity-legend {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-top: 0.75rem; font-size: 12px; color: #8b949e; }}
    .intensity-entry {{ display: inline-flex; align-items: center; gap: 6px; }}
    .legend {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; margin-top: 1rem; font-size: 12px; }}
    .legend-entry {{ display: inline-flex; align-items: center; gap: 6px; }}
    .legend-entry.archived .legend-name {{ opacity: 0.55; }}
    .legend-entry.hidden {{ display: none; }}
    .legend-item {{ width: 12px; height: 12px; border-radius: 2px; display: inline-block; }}
    .legend-name {{ color: #8b949e; }}
  </style>
</head>
<body>
  <h1>Project activity</h1>
  <p class="subtitle">Days with file changes, by project (from activity log in the current working directory)</p>
  <div class="controls">
    <label><input id="show-archived" type="checkbox"> Show archived projects</label>
  </div>
  <div class="grid">
    {"".join(month_rows)}
  </div>
  <div class="intensity-legend">
    <span>Intensity:</span>
    <span class="intensity-entry"><span class="legend-item cell low" style="background:#6e7681"></span><span>low (1-2)</span></span>
    <span class="intensity-entry"><span class="legend-item cell mid" style="background:#6e7681"></span><span>mid (3-9)</span></span>
    <span class="intensity-entry"><span class="legend-item cell high" style="background:#6e7681"></span><span>high (10+) with border</span></span>
  </div>
  <div class="legend">
    {legend}
  </div>
  <script>
    const archivedProjects = new Set({archived_json}.map(p => p.toLowerCase()));
    const projectStyles = {project_styles_json};
    const storageKey = "dev-activity.show-archived";
    const showArchivedInput = document.getElementById("show-archived");
    const projectCells = Array.from(document.querySelectorAll(".project-cell"));
    const legendEntries = Array.from(document.querySelectorAll(".legend-entry"));

    function cellProjects(cell) {{
      const raw = cell.getAttribute("data-projects") || "";
      return raw ? raw.split("|") : [];
    }}

    function applyFilters() {{
      const showArchived = showArchivedInput.checked;
      localStorage.setItem(storageKey, showArchived ? "1" : "0");

      function intensityForTotal(total) {{
        if (total >= 10) return "high";
        if (total >= 3) return "mid";
        return "low";
      }}

      function parseProjectCounts(cell) {{
        const raw = cell.getAttribute("data-proj-counts");
        if (!raw) return [];
        try {{
          const parsed = JSON.parse(raw);
          if (!Array.isArray(parsed)) return [];
          return parsed.filter(item => Array.isArray(item) && item.length === 2);
        }} catch {{
          return [];
        }}
      }}

      function setIntensityClass(cell, intensity) {{
        cell.classList.remove("low", "mid", "high");
        cell.classList.add(intensity);
      }}

      for (const cell of projectCells) {{
        const dateKey = cell.getAttribute("data-date") || "";
        const allEntries = parseProjectCounts(cell)
          .map(([p, c]) => [String(p), Number(c)])
          .filter(([, c]) => Number.isFinite(c) && c > 0);
        const visibleEntries = showArchived
          ? allEntries
          : allEntries.filter(([p]) => !archivedProjects.has(p.toLowerCase()));

        if (visibleEntries.length === 0) {{
          cell.classList.add("filtered");
          cell.style.background = "";
          cell.title = dateKey;
          continue;
        }}

        cell.classList.remove("filtered");
        visibleEntries.sort((a, b) => b[1] - a[1]);
        const total = visibleEntries.reduce((sum, [, c]) => sum + c, 0);
        const intensity = intensityForTotal(total);
        setIntensityClass(cell, intensity);

        const tip = visibleEntries
          .map(([p, c]) => `${{p}}${{archivedProjects.has(p.toLowerCase()) ? " (archived)" : ""}}: ${{c}}`)
          .join(", ");
        cell.title = `${{dateKey}}: ${{tip}}`;

        if (visibleEntries.length === 1) {{
          const [projectName] = visibleEntries[0];
          const style = projectStyles[projectName]?.[intensity === "high" ? "highStyle" : "lowStyle"] || "";
          cell.style.cssText = style;
          continue;
        }}

        const stops = [];
        let acc = 0;
        for (const [projectName, count] of visibleEntries) {{
          const startPct = (acc / total) * 100;
          acc += count;
          const endPct = (acc / total) * 100;
          const color = projectStyles[projectName]?.[intensity === "high" ? "highColor" : "lowColor"] || "#6e7681";
          stops.push(`${{color}} ${{startPct}}%`);
          stops.push(`${{color}} ${{endPct}}%`);
        }}
        cell.style.background = `linear-gradient(to bottom, ${{stops.join(", ")}})`;
      }}

      for (const entry of legendEntries) {{
        const isArchived = (entry.getAttribute("data-archived") || "false") === "true";
        entry.classList.toggle("archived", isArchived);
        entry.classList.toggle("hidden", !showArchived && isArchived);
      }}
    }}

    showArchivedInput.checked = localStorage.getItem(storageKey) === "1";
    showArchivedInput.addEventListener("change", applyFilters);
    applyFilters();
  </script>
</body>
</html>
"""

    out_path.write_text(html_doc, encoding="utf-8")
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
    graph_parser.add_argument("--archives", default=ARCHIVE_FILENAME, help="Archived projects file (default: archived-projects.json)")
    archive_parser = sub.add_parser("archive", help="Archive project (hidden by default in graph)")
    archive_parser.add_argument("project", help="Project name to archive")
    archive_parser.add_argument("--archives", default=ARCHIVE_FILENAME, help="Archived projects file (default: archived-projects.json)")
    unarchive_parser = sub.add_parser("unarchive", help="Unarchive project")
    unarchive_parser.add_argument("project", help="Project name to unarchive")
    unarchive_parser.add_argument("--archives", default=ARCHIVE_FILENAME, help="Archived projects file (default: archived-projects.json)")
    archives_parser = sub.add_parser("archives", help="List archived projects")
    archives_parser.add_argument("--archives", default=ARCHIVE_FILENAME, help="Archived projects file (default: archived-projects.json)")
    backfill_parser = sub.add_parser("backfill-github", help="Append GitHub commit activity for a month (requires gh CLI)")
    backfill_parser.add_argument("--month", type=int, default=None, help="Month (1-12, default: current)")
    backfill_parser.add_argument("--year", type=int, default=None, help="Year (default: current)")
    backfill_parser.add_argument("--log", default=LOG_FILENAME, help="Activity log file (default: activity.jsonl)")
    args = parser.parse_args()

    if args.cmd == "watch":
        run_watch(args.path)
    elif args.cmd == "archive":
        run_archive_project(Path(args.archives), args.project)
    elif args.cmd == "unarchive":
        run_unarchive_project(Path(args.archives), args.project)
    elif args.cmd == "archives":
        run_list_archived_projects(Path(args.archives))
    elif args.cmd == "backfill-github":
        now = datetime.now()
        year = args.year if args.year is not None else now.year
        month = args.month if args.month is not None else now.month
        run_backfill_github(Path(args.log), year, month)
    else:
        log_path = Path(args.log)
        out_path = Path.cwd() / GRAPH_FILENAME
        generate_graph(log_path, out_path, getattr(args, "open", False), Path(args.archives))


if __name__ == "__main__":
    main()
