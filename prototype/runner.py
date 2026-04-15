#!/usr/bin/env python3
"""
runner.py -- Load a User-as-Code project and run all constraints.

Usage:
    python runner.py                          # defaults to jessica_thompson
    python runner.py /path/to/user_project
"""

import importlib
import importlib.util
import sys
import types
from pathlib import Path


SEVERITY_SYMBOLS = {
    "critical": "!!!",
    "warning": " ! ",
    "info": " i ",
}

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def load_manifest(project_path: Path) -> dict:
    """Load and return the manifest module's DOMAINS dict."""
    spec = importlib.util.spec_from_file_location(
        "manifest", project_path / "manifest.py"
    )
    manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest)
    return manifest.DOMAINS


def discover_constraints(project_path: Path) -> list[Path]:
    """Find all constraint .py files in the project's constraints/ directory."""
    constraints_dir = project_path / "constraints"
    if not constraints_dir.exists():
        return []
    return sorted(
        p for p in constraints_dir.glob("*.py")
        if p.name != "__init__.py"
    )


def run_constraint(constraint_path: Path, project_path: str) -> list[dict]:
    """Load a constraint module and run its check() function."""
    module_name = f"constraint_{constraint_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, constraint_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check(project_path)


def clear_domain_modules():
    """Remove cached domain modules so each constraint gets a fresh load."""
    to_remove = [k for k in sys.modules if k.startswith("domains")]
    for k in to_remove:
        del sys.modules[k]


def print_header(project_path: Path, domains: dict):
    user_name = project_path.name.replace("_", " ").title()
    print("=" * 72)
    print(f"  User-as-Code Constraint Runner")
    print(f"  Project: {user_name}")
    print(f"  Path:    {project_path}")
    print("=" * 72)
    print()
    print("  Registered domains:")
    for name, info in domains.items():
        print(f"    - {name:12s}  {info['summary']}")
    print()


def print_alerts(all_alerts: list[dict]):
    if not all_alerts:
        print("  No alerts. All constraints passed.")
        return

    # Sort by severity
    all_alerts.sort(key=lambda a: SEVERITY_ORDER.get(a.get("severity", "info"), 9))

    print(f"  {len(all_alerts)} alert(s) found:\n")
    print("-" * 72)
    for i, alert in enumerate(all_alerts, 1):
        sev = alert.get("severity", "info")
        sym = SEVERITY_SYMBOLS.get(sev, " ? ")
        source = alert.get("source", "unknown")
        domain = alert.get("domain", "")
        msg = alert.get("message", "")
        print(f"  [{sym}] Alert #{i}  ({sev.upper()})")
        print(f"       Source:  {source}")
        if domain:
            print(f"       Domain:  {domain}")
        # Wrap message at ~60 chars for readability
        words = msg.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 > 60:
                lines.append(current_line)
                current_line = word
            else:
                current_line = f"{current_line} {word}".strip()
        if current_line:
            lines.append(current_line)
        for j, line in enumerate(lines):
            prefix = "       Message: " if j == 0 else "                "
            print(f"{prefix}{line}")
        print("-" * 72)


def main():
    if len(sys.argv) > 1:
        project_path = Path(sys.argv[1]).resolve()
    else:
        project_path = Path(__file__).resolve().parent / "jessica_thompson"

    if not project_path.exists():
        print(f"Error: project path does not exist: {project_path}")
        sys.exit(1)

    # Load manifest
    domains = load_manifest(project_path)
    print_header(project_path, domains)

    # Discover and run constraints
    constraint_files = discover_constraints(project_path)
    print(f"  Running {len(constraint_files)} constraint(s)...\n")

    all_alerts: list[dict] = []
    for cf in constraint_files:
        clear_domain_modules()
        name = cf.stem
        print(f"    -> {name} ... ", end="")
        try:
            alerts = run_constraint(cf, str(project_path))
            all_alerts.extend(alerts)
            if alerts:
                print(f"{len(alerts)} alert(s)")
            else:
                print("OK")
        except Exception as e:
            print(f"ERROR: {e}")

    print()
    print_alerts(all_alerts)
    print()


if __name__ == "__main__":
    main()
