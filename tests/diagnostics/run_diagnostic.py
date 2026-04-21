"""Entry point for the classifier diagnostic.

Usage:

    python -m tests.diagnostics.run_diagnostic

Writes reports to ``tests/diagnostics/reports/``.
"""

from __future__ import annotations

import sys

from tests.diagnostics.diagnostic_harness import run, write_artifacts


def main() -> int:
    print("Loading classifier and running diagnostic...", flush=True)
    results, aggregate = run()
    json_path, md_path = write_artifacts(results, aggregate)

    o = aggregate["overall"]
    print()
    print(f"=== OVERALL (n={aggregate['n']}) ===")
    print(f"  intent     {o['intent_acc']:.1%}")
    print(f"  category   {o['category_acc']:.1%}")
    print(f"  proximity  {o['proximity_acc']:.1%}")
    print(f"  open_now   {o['open_now_acc']:.1%}")
    print()
    print(f"JSON:    {json_path}")
    print(f"Report:  {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
