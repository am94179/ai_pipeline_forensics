#!/usr/bin/env python3
"""Generate the checked-in Phase 1 enum-change scenario artifacts."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from investigator.synthetic.enum_change import generate_scenario  # noqa: E402


if __name__ == "__main__":
    scenario_dir = PROJECT_ROOT / "data" / "scenarios" / "enum_change"
    manifest = generate_scenario(scenario_dir)
    print(f"Generated {manifest.scenario_id} at {scenario_dir}")

