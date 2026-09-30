"""SQLite schema for the unified cell-line / sample inventory."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "clm_inventory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cell_lines (
    registry_id TEXT PRIMARY KEY,
    benchling_entity_id TEXT NOT NULL,
    cell_line_name TEXT NOT NULL,
    species TEXT,
    tissue_origin TEXT,
    culture_medium TEXT,
    registered_by TEXT,
    registered_at TEXT,
    source_system TEXT DEFAULT 'benchling'
);

CREATE TABLE IF NOT EXISTS passages (
    passage_uid TEXT PRIMARY KEY,
    registry_id TEXT NOT NULL REFERENCES cell_lines(registry_id),
    passage_number INTEGER,
    passage_date TEXT,
    confluency_pct REAL,
    viability_pct REAL,
    split_ratio TEXT,
    performed_by TEXT,
    source_system TEXT DEFAULT 'benchling'
);

CREATE TABLE IF NOT EXISTS vials (
    vial_id TEXT PRIMARY KEY,
    registry_id TEXT REFERENCES cell_lines(registry_id),
    sapio_record_id INTEGER,
    passage_at_freeze INTEGER,
    freeze_date TEXT,
    cryo_medium TEXT,
    storage_location TEXT,
    storage_box TEXT,
    storage_position TEXT,
    cell_count_at_freeze INTEGER,
    viability_pct_at_freeze REAL,
    frozen_by TEXT,
    status TEXT,
    barcode_data TEXT,
    barcode_pattern TEXT,
    barcode_checksum INTEGER,
    source_system TEXT DEFAULT 'sapio'
);

CREATE TABLE IF NOT EXISTS qc_results (
    qc_uid TEXT PRIMARY KEY,
    registry_id TEXT REFERENCES cell_lines(registry_id),
    test_date TEXT,
    tested_by TEXT,
    mycoplasma_result TEXT,
    mycoplasma_method TEXT,
    str_identity_result TEXT,
    str_identity_method TEXT,
    str_markers_matched INTEGER,
    source_system TEXT DEFAULT 'sapio'
);

CREATE TABLE IF NOT EXISTS chain_of_custody (
    event_uid TEXT PRIMARY KEY,
    vial_id TEXT REFERENCES vials(vial_id),
    registry_id TEXT REFERENCES cell_lines(registry_id),
    event_type TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    performed_by TEXT,
    from_location TEXT,
    to_location TEXT,
    notes TEXT,
    sequence_no INTEGER,
    source_system TEXT DEFAULT 'sapio'
);

CREATE TABLE IF NOT EXISTS integrity_findings (
    finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT,
    entity_id TEXT,
    check_name TEXT,
    passed INTEGER,
    detail TEXT
);
"""


def get_connection(fresh=False):
    if fresh and DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA)
    return conn
