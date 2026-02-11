from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from pathlib import Path


def get_last_commit_time(repo_root: Path) -> dt.datetime:
    """Return the latest commit timestamp as a timezone-aware datetime."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "log", "-1", "--format=%cI"],
        check=True,
        capture_output=True,
        text=True,
    )
    commit_time_raw = result.stdout.strip()
    if not commit_time_raw:
        raise RuntimeError("Could not read the latest git commit timestamp.")
    return dt.datetime.fromisoformat(commit_time_raw)


def build_version_contents(
    *,
    major: int,
    minor: int,
    last_commit_time: dt.datetime,
    project_started_date: dt.date,
) -> str:
    """Build the .version file content."""
    days_since_project_started = (last_commit_time.date() - project_started_date).days
    minutes_since_midnight = last_commit_time.hour * 60 + last_commit_time.minute
    return (
        f"MAJOR={major}\n"
        f"MINOR={minor}\n"
        f"BUILD={days_since_project_started}.{minutes_since_midnight}\n"
        f"LAST_COMMIT_TIME={last_commit_time.isoformat()}"
    )


def build_semantic_version(
    *,
    major: int,
    minor: int,
    last_commit_time: dt.datetime,
    project_started_date: dt.date,
) -> str:
    days_since_project_started = (last_commit_time.date() - project_started_date).days
    minutes_since_midnight = last_commit_time.hour * 60 + last_commit_time.minute
    build = f"{days_since_project_started}.{minutes_since_midnight}"
    return f"{major}.{minor}.{build}"


def update_readme_current_version(readme_path: Path, version: str) -> None:
    """Update the README's 'Current Version:' line, creating it if missing."""
    if not readme_path.exists():
        return

    contents = readme_path.read_text(encoding="utf-8")
    current_version_line = f"Current Version: `{version}`"
    lines = contents.splitlines()

    for idx, line in enumerate(lines):
        if line.startswith("Current Version:"):
            lines[idx] = current_version_line
            updated_contents = "\n".join(lines)
            if contents.endswith("\n"):
                updated_contents += "\n"
            readme_path.write_text(updated_contents, encoding="utf-8")
            return

    # If the line does not exist yet, insert it under the "Generate Version File" section.
    insert_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Generate Version File":
            insert_idx = idx + 2
            break
    if insert_idx is None:
        return

    new_lines = lines[:insert_idx] + [current_version_line, ""] + lines[insert_idx:]
    updated_contents = "\n".join(new_lines)
    if contents.endswith("\n"):
        updated_contents += "\n"
    readme_path.write_text(updated_contents, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a .version file from the latest git commit timestamp."
    )
    parser.add_argument("--major", type=int, default=1, help="Major version (default: 1)")
    parser.add_argument("--minor", type=int, default=0, help="Minor version (default: 0)")
    parser.add_argument(
        "--project-start-date",
        default="2025-11-14",
        help="Project start date in YYYY-MM-DD format (default: 2025-11-14)",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Path to the git repository root (default: project root)",
    )
    parser.add_argument(
        "--output",
        default=".version",
        help="Output file path. Relative paths are resolved from repo root.",
    )
    parser.add_argument(
        "--readme-path",
        default="README.md",
        help="README path to update with the current version line (default: README.md).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    project_started_date = dt.date.fromisoformat(args.project_start_date)

    last_commit_time = get_last_commit_time(repo_root)
    version_contents = build_version_contents(
        major=args.major,
        minor=args.minor,
        last_commit_time=last_commit_time,
        project_started_date=project_started_date,
    )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    output_path.write_text(version_contents, encoding="utf-8")

    semantic_version = build_semantic_version(
        major=args.major,
        minor=args.minor,
        last_commit_time=last_commit_time,
        project_started_date=project_started_date,
    )
    readme_path = Path(args.readme_path)
    if not readme_path.is_absolute():
        readme_path = repo_root / readme_path
    update_readme_current_version(readme_path, semantic_version)

    print(f"Version file generated at: {output_path}")
    print(f"Current version: {semantic_version}")


if __name__ == "__main__":
    main()
