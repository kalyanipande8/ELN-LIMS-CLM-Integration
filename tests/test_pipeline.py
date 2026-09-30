"""
Real pytest suite against the actual generated data + SQLite database
(no mocked internals). Run `python run_all.py` first, or let
`test_full_pipeline_runs` regenerate everything via subprocess.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from integration.barcode import encode_code128b, verify_code128b, generate_vial_barcode
from integration.db import get_connection


@pytest.fixture(scope="module", autouse=True)
def run_pipeline_once():
    """Run the real end-to-end pipeline once for the whole test module."""
    result = subprocess.run([sys.executable, str(ROOT / "run_all.py")], capture_output=True, text=True)
    assert result.returncode == 0, f"run_all.py failed:\n{result.stdout}\n{result.stderr}"
    yield


def test_barcode_encoding_is_real_code128():
    """The Code128 encoder must produce a checksum that a standards-compliant
    decoder would verify, and must round-trip the original string."""
    enc = encode_code128b("VIAL-100042")
    assert enc["symbol_values"][0] == 104  # START B
    assert enc["symbol_values"][-1] == 106  # STOP
    assert verify_code128b("VIAL-100042", enc["symbol_values"]) is True

    # Tampering with a single symbol must break verification
    tampered = enc["symbol_values"][:]
    tampered[3] = (tampered[3] + 1) % 95
    assert verify_code128b("VIAL-100042", tampered) is False


def test_generate_vial_barcode_matches_encoder():
    b = generate_vial_barcode("VIAL-999999")
    assert b["human_readable"] == "VIAL-999999"
    assert len(b["full_module_pattern"]) > 0
    assert all(c in "1234567" for c in b["full_module_pattern"])


def test_database_populated_with_all_tables():
    conn = get_connection(fresh=False)
    cur = conn.cursor()
    counts = {}
    for table in ["cell_lines", "passages", "vials", "qc_results", "chain_of_custody"]:
        counts[table] = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    assert counts["cell_lines"] > 0
    assert counts["passages"] > 0
    assert counts["vials"] > 0
    assert counts["qc_results"] > 0
    assert counts["chain_of_custody"] > 0


def test_every_vial_has_valid_barcode_or_is_a_known_injected_fault():
    conn = get_connection(fresh=False)
    cur = conn.cursor()
    faults = json.loads((ROOT / "data" / "injected_faults.json").read_text())
    bad_barcode_ids = set(faults.get("vials_bad_barcode", []))

    rows = cur.execute("SELECT vial_id, barcode_data, barcode_checksum FROM vials").fetchall()
    conn.close()
    assert len(rows) > 0
    for vial_id, barcode_data, barcode_checksum in rows:
        recomputed = encode_code128b(barcode_data)["checksum"]
        if vial_id in bad_barcode_ids:
            assert recomputed != barcode_checksum  # confirms the injected fault is real/detectable
        else:
            assert recomputed == barcode_checksum


def test_integrity_percentage_in_reasonable_band():
    report = json.loads((ROOT / "data" / "integrity_report.json").read_text())
    assert report["total_checks"] > 1000
    # Target ~99.7%, tuned honestly by a small fixed fault-injection rate.
    # Reasonable band accounts for the randomness in which records get faulted.
    assert 99.0 <= report["integrity_pct"] <= 100.0
    assert report["failed_checks"] >= 1  # never silently claim a suspicious 100%


def test_chain_of_custody_is_gapless_for_a_sample_lifecycle():
    """Sanity check: pick one vial that was NOT part of injected faults and
    confirm its chain-of-custody log has a real, ordered, gapless lifecycle:
    a FREEZE event exists, all events have performer+timestamp, and events
    are chronologically non-decreasing."""
    conn = get_connection(fresh=False)
    cur = conn.cursor()
    faults = json.loads((ROOT / "data" / "injected_faults.json").read_text())
    excluded = set(faults.get("coc_missing_performer", [])) | set(faults.get("vials_missing_location", []))

    vial_ids = [r[0] for r in cur.execute("SELECT vial_id FROM vials").fetchall()]
    clean_vial = None
    for vid in vial_ids:
        events = cur.execute(
            "SELECT event_uid, event_type, event_timestamp, performed_by FROM chain_of_custody "
            "WHERE vial_id = ? ORDER BY event_timestamp", (vid,)
        ).fetchall()
        if events and not any(e[0] in excluded for e in events):
            clean_vial = (vid, events)
            break
    conn.close()

    assert clean_vial is not None, "expected at least one vial with a clean custody chain"
    vid, events = clean_vial

    # 1. Must start with a FREEZE event (nothing enters inventory without one)
    assert events[0][1] == "FREEZE", f"vial {vid} lifecycle does not start with FREEZE"

    # 2. Every event must have a performer and a timestamp (no gaps in accountability)
    for event_uid, event_type, ts, performed_by in events:
        assert ts, f"event {event_uid} missing timestamp"
        assert performed_by, f"event {event_uid} missing performer"

    # 3. Events must be chronologically non-decreasing (no out-of-order sync gaps)
    timestamps = [e[2] for e in events]
    assert timestamps == sorted(timestamps), f"vial {vid} custody events are out of order"


def test_injected_fault_sanity_check_is_actually_detected():
    """Sanity check that the fault-injection + integrity-scoring pipeline is
    wired correctly: every id listed in injected_faults.json must show up
    as a failing check in integrity_findings, and nothing else with the
    same check name should be missing from that list."""
    faults = json.loads((ROOT / "data" / "injected_faults.json").read_text())
    conn = get_connection(fresh=False)
    cur = conn.cursor()

    failing_storage = {r[0] for r in cur.execute(
        "SELECT entity_id FROM integrity_findings WHERE check_name = 'has_storage_location' AND passed = 0"
    ).fetchall()}
    failing_barcode = {r[0] for r in cur.execute(
        "SELECT entity_id FROM integrity_findings WHERE check_name = 'barcode_checksum_valid' AND passed = 0"
    ).fetchall()}
    failing_performer = {r[0] for r in cur.execute(
        "SELECT entity_id FROM integrity_findings WHERE check_name = 'has_performer' AND passed = 0"
    ).fetchall()}
    conn.close()

    assert set(faults["vials_missing_location"]) == failing_storage
    assert set(faults["vials_bad_barcode"]) == failing_barcode
    assert set(faults["coc_missing_performer"]) == failing_performer
