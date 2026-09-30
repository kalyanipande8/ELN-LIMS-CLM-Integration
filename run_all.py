#!/usr/bin/env python3
"""
End-to-end pipeline runner for the ELN/LIMS CLM integration project.

1. Generates Benchling-ELN-shaped mock records (cell line registrations, passages)
2. Generates Sapio-LIMS-shaped mock records (vials, transfer/custody events, QC)
3. Merges both into one unified SQLite inventory, generating real Code128
   barcodes for every vial and a full chain-of-custody log
4. Runs the data-integrity validator across the whole inventory
5. Prints a real summary with real numbers
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    print("=" * 70)
    print("STEP 1/4: Generating Benchling-ELN-shaped CLM records")
    print("=" * 70)
    subprocess.run([sys.executable, str(ROOT / "benchling_sim" / "generate_benchling_records.py")], check=True)

    print("\n" + "=" * 70)
    print("STEP 2/4: Generating Sapio-LIMS-shaped CLM records")
    print("=" * 70)
    subprocess.run([sys.executable, str(ROOT / "sapio_sim" / "generate_sapio_records.py")], check=True)

    print("\n" + "=" * 70)
    print("STEP 3/4: Merging into unified SQLite inventory + generating barcodes")
    print("=" * 70)
    sys.path.insert(0, str(ROOT))
    from integration.merge import run_merge
    summary = run_merge(fresh=True, inject_faults=True)
    print(json.dumps(summary, indent=2, default=list))

    print("\n" + "=" * 70)
    print("STEP 4/4: Running data-integrity validation")
    print("=" * 70)
    from integration.db import get_connection
    from integration.integrity import run_integrity_checks
    conn = get_connection(fresh=False)
    report = run_integrity_checks(conn)
    conn.close()
    (ROOT / "data" / "integrity_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    print("\n" + "=" * 70)
    print(f"RESULT: {summary['cell_lines']} cell lines, {summary['vials']} vials, "
          f"{summary['transfer_events'] + summary['passages']} chain-of-custody-relevant events")
    print(f"RESULT: Data integrity = {report['integrity_pct']}% "
          f"({report['passed_checks']}/{report['total_checks']} checks passed)")
    print("=" * 70)


if __name__ == "__main__":
    main()
