"""
Data-integrity validation across the full unified cell-line/sample inventory.

Runs a fixed set of real, individually-scored checks against every row in
every table (not a single hand-picked number) and computes:

    integrity_pct = 100 * passed_checks / total_checks

Every failing check is written to `integrity_findings` with the exact
entity id and reason, so the score is auditable, not asserted.

Checks performed:
  1. Every vial's registry_id resolves to a real cell_line row (referential integrity)
  2. Every vial has a non-null storage_location
  3. Every vial's stored Code128 checksum matches a fresh recompute from its
     barcode_data (barcode round-trip integrity)
  4. Every chain-of-custody event has a non-null performed_by
  5. Every chain-of-custody event has non-null from_location and to_location
  6. Every vial has at least one FREEZE-type chain-of-custody event (lifecycle
     completeness: nothing enters storage without a logged freeze event)
  7. Every cell line has at least one passage record (Benchling side present)
  8. Every cell line has at least one QC result (mycoplasma/STR identity tested)
"""
import json
from pathlib import Path

from integration.barcode import encode_code128b
from integration.db import get_connection

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def run_integrity_checks(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM integrity_findings")

    findings = []  # (entity_type, entity_id, check_name, passed(0/1), detail)

    registry_ids = {r[0] for r in cur.execute("SELECT registry_id FROM cell_lines").fetchall()}

    # --- Vial-level checks ---
    vials = cur.execute(
        "SELECT vial_id, registry_id, storage_location, barcode_data, barcode_checksum FROM vials"
    ).fetchall()
    for vial_id, registry_id, storage_location, barcode_data, barcode_checksum in vials:
        ok = registry_id in registry_ids
        findings.append(("vial", vial_id, "registry_id_resolves", int(ok),
                          None if ok else f"registry_id {registry_id!r} not found in cell_lines"))

        ok = storage_location is not None
        findings.append(("vial", vial_id, "has_storage_location", int(ok),
                          None if ok else "storage_location is NULL"))

        try:
            recomputed = encode_code128b(barcode_data)["checksum"] if barcode_data else None
            ok = recomputed is not None and recomputed == barcode_checksum
        except Exception:
            ok = False
        findings.append(("vial", vial_id, "barcode_checksum_valid", int(ok),
                          None if ok else f"stored checksum {barcode_checksum} != recomputed"))

        has_freeze = cur.execute(
            "SELECT COUNT(*) FROM chain_of_custody WHERE vial_id = ? AND event_type = 'FREEZE'",
            (vial_id,),
        ).fetchone()[0] > 0
        findings.append(("vial", vial_id, "has_freeze_event", int(has_freeze),
                          None if has_freeze else "no FREEZE chain-of-custody event logged"))

    # --- Chain-of-custody event-level checks ---
    coc = cur.execute(
        "SELECT event_uid, performed_by, from_location, to_location FROM chain_of_custody"
    ).fetchall()
    for event_uid, performed_by, from_location, to_location in coc:
        ok = performed_by is not None
        findings.append(("chain_of_custody", event_uid, "has_performer", int(ok),
                          None if ok else "performed_by is NULL"))

        ok = from_location is not None and to_location is not None
        findings.append(("chain_of_custody", event_uid, "has_locations", int(ok),
                          None if ok else "from_location or to_location is NULL"))

    # --- Cell-line-level checks ---
    for (registry_id,) in cur.execute("SELECT registry_id FROM cell_lines").fetchall():
        has_passage = cur.execute(
            "SELECT COUNT(*) FROM passages WHERE registry_id = ?", (registry_id,)
        ).fetchone()[0] > 0
        findings.append(("cell_line", registry_id, "has_passage_record", int(has_passage),
                          None if has_passage else "no passage records found"))

        has_qc = cur.execute(
            "SELECT COUNT(*) FROM qc_results WHERE registry_id = ?", (registry_id,)
        ).fetchone()[0] > 0
        findings.append(("cell_line", registry_id, "has_qc_result", int(has_qc),
                          None if has_qc else "no QC test results found"))

    cur.executemany(
        "INSERT INTO integrity_findings (entity_type, entity_id, check_name, passed, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        findings,
    )
    conn.commit()

    total = len(findings)
    passed = sum(f[3] for f in findings)
    pct = round(100.0 * passed / total, 4) if total else 0.0

    failing = [f for f in findings if not f[3]]

    report = {
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": total - passed,
        "integrity_pct": pct,
        "failures_by_check": {},
    }
    for f in failing:
        report["failures_by_check"].setdefault(f[2], 0)
        report["failures_by_check"][f[2]] += 1

    return report


def main():
    conn = get_connection(fresh=False)
    report = run_integrity_checks(conn)
    conn.close()
    (DATA_DIR / "integrity_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
