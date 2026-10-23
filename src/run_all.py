#!/usr/bin/env python3
"""Run the full PulseIQ Phase 1 pipeline from the repository root."""
from pathlib import Path
import subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
STEPS=[
    [sys.executable,"src/run_etl.py"],
    [sys.executable,"src/run_dq_checks.py"],
    [sys.executable,"src/build_warehouse.py"],
]
for command in STEPS:
    print("\n$", " ".join(command), flush=True)
    result=subprocess.run(command,cwd=ROOT)
    if result.returncode:
        print(f"FAILED (exit {result.returncode}): {' '.join(command)}",file=sys.stderr)
        sys.exit(result.returncode)
print("\nPulseIQ Phase 1 run completed. Review README acceptance checklist and SQL DQ results.")
