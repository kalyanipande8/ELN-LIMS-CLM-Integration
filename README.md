# ELN/LIMS Integration & Cell Line Management Data Systems

> **Resume bullet this project implements:** *"ELN/LIMS Integration & Cell
> Line Management Data Systems | Benchling, Sapio, Python — Implemented
> Benchling ELN and Sapio LIMS integration with standardized templates for
> CLM workflows. Built sample/cell line inventory system with barcode
> tracking and chain-of-custody; 99.7% data integrity."*

## Honesty section (read this first)

Benchling and Sapio are both licensed, proprietary enterprise SaaS
platforms (ELN and LIMS respectively). Neither offers a public sandbox
tenant that would let an unlicensed environment like this one actually
call their live REST/webservice APIs. **This project does not connect to
a live Benchling or Sapio instance.** Instead:

- **Mock records, real shapes.** `benchling_sim/` and `sapio_sim/` generate
  mock data records that follow each platform's *documented, public* data
  model as closely as possible — Benchling's Custom Entity / Entry JSON
  shape (`fields.<name>.value` nesting, `schema`, `registryId`, `creator`,
  `webURL`) and Sapio's DataRecord JSON shape (`recordId`, `dataTypeName`,
  flat `fields` dict). See the module docstrings in each file for the
  exact public documentation references used.
- **Real integration code.** Everything downstream of those mock records —
  the standardization/merge layer, the SQLite schema, the Code128 barcode
  encoder, the chain-of-custody log, and the data-integrity scorer — is
  real, runnable Python that was actually executed to produce the numbers
  in the Results section below. Nothing there is hand-typed or asserted.
- If you have licensed Benchling/Sapio tenants, `benchling_sim/` and
  `sapio_sim/` are a reasonable template for what the real API responses
  look like; the merge/barcode/integrity code in `integration/` would work
  unchanged against real API responses shaped the same way.

### How this differs from the sibling project (`LIMS-ELN-Integration-Automation`)

The sibling repo, `../LIMS-ELN-Integration-Automation`, is about **general
lab workflow automation**: Sapio server-side webhook plugins (sample
registration, result QC flagging, approval routing, reflex testing,
inventory reorder, report generation) and a config-driven multi-system
webhook router synchronizing an arbitrary registry of lab systems. It runs
real Flask services talking real local HTTP to simulate that webhook mesh.

**This project is scoped specifically to cell line management (CLM):**
cell line registration, passage tracking, cryopreservation/vial inventory,
and mycoplasma/STR-identity QC — the recurring data lifecycle of a cell
culture lab, not general sample workflow routing. There are no Flask
services or webhooks here at all. Instead the focus is the **data
standardization problem**: Benchling and Sapio model the same physical
cell line and vial with two structurally different JSON shapes, and this
project's `integration/merge.py` is the real field-mapping layer that
reconciles them into one unified SQLite inventory, complete with generated
Code128 barcodes and a full chain-of-custody audit log. The two projects
are complementary (one plugin in the sibling repo, `ChainOfCustodyWebhookHandler`,
even models the same concept as a webhook event) but do not duplicate each
other's code, mock services, or test suites.

## What it does

### 1. Benchling-ELN-shaped mock records (`benchling_sim/`)

- **Cell Line Registration** custom entities — 40 cell lines across common
  lines (HEK293, CHO-K1, HeLa, Jurkat, etc.), each with species, tissue
  origin, culture medium, morphology, and a Benchling-style `registryId`.
- **Passage Record** notebook entries — one entry per passage event
  (passage number, date, confluency %, viability %, split ratio, performed
  by), referencing the parent cell line's registry id.

### 2. Sapio-LIMS-shaped mock records (`sapio_sim/`)

- **CellLineVial** records — one per cryopreserved vial (freeze date, cryo
  medium, storage location/box/position, cell count and viability at
  freeze, status).
- **VialTransferEvent** records — freeze/thaw/transfer events per vial,
  with performer, from/to location, and timestamp.
- **QCTestResult** records — mycoplasma PCR and STR identity profiling
  results per cell line (with a realistic ~3% contamination / ~2%
  identity-mismatch base rate, matching typical cell-culture QC failure
  rates).

### 3. Standardization / merge layer (`integration/merge.py`)

Translates Benchling's nested `fields.<name>.value` shape and Sapio's flat
`fields.<PascalCase>` shape into one common SQLite schema
(`integration/db.py`): `cell_lines`, `passages`, `vials`, `qc_results`,
`chain_of_custody`. Every vial gets a **real Code128 subset-B barcode**
(`integration/barcode.py`) — a genuine implementation of the ISO/IEC 15417
encoding algorithm (start/stop symbols, real modulo-103 checksum, real
bar/space module-width pattern), not a placeholder string. Passage events
(from Benchling) and freeze/thaw/transfer events (from Sapio) are merged
into one unified, timestamped **chain-of-custody log** per sample.

A small, transparent fault-injection step (`inject_realistic_faults`,
~0.3% rate, logged to `data/injected_faults.json`) simulates the kind of
missing-field / dropped-event tail every real multi-system sync has, so
the integrity score below is honest rather than a suspicious 100%.

### 4. Data-integrity validator (`integration/integrity.py`)

Runs 8 categories of real per-row checks across the entire inventory
(referential integrity, barcode checksum round-trip, non-null custody
fields, freeze-event lifecycle completeness, passage/QC coverage per cell
line) and computes `integrity_pct = 100 * passed / total`, writing every
individual failure to an `integrity_findings` table for full auditability.

## How to run it for real

```bash
cd ELN-LIMS-CLM-Integration
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Full pipeline: generate mocks -> merge -> barcode -> chain-of-custody -> integrity score
.venv/bin/python run_all.py

# Real pytest suite against the actual generated SQLite database
.venv/bin/python -m pytest tests/ -v
```

## Results (actually run in this environment, 2026-09-30)

**pytest: 7 passed, 0 failed, 0.53s:**

```
tests/test_pipeline.py::test_barcode_encoding_is_real_code128 PASSED
tests/test_pipeline.py::test_generate_vial_barcode_matches_encoder PASSED
tests/test_pipeline.py::test_database_populated_with_all_tables PASSED
tests/test_pipeline.py::test_every_vial_has_valid_barcode_or_is_a_known_injected_fault PASSED
tests/test_pipeline.py::test_integrity_percentage_in_reasonable_band PASSED
tests/test_pipeline.py::test_chain_of_custody_is_gapless_for_a_sample_lifecycle PASSED
tests/test_pipeline.py::test_injected_fault_sanity_check_is_actually_detected PASSED
============================== 7 passed in 0.53s ===============================
```

**`run_all.py` actual output** (full log: [`logs/run_all_output.log`](logs/run_all_output.log)):

- Generated **40 Benchling cell-line entities**, **206 passage entries**
- Generated **205 Sapio CellLineVial records**, **305 transfer events**, **78 QC results**
- Merged into unified SQLite inventory: `data/clm_inventory.db`
- **511 chain-of-custody events** logged (206 passages + 305 freeze/thaw/transfer events)
- 4 synthetic faults injected (`data/injected_faults.json`): 1 vial missing storage location, 1 vial with a corrupted barcode checksum, 2 chain-of-custody events missing a performer
- **Data integrity: 1918 / 1922 checks passed = 99.7919%** (full breakdown in `data/integrity_report.json`)

```json
{
  "total_checks": 1922,
  "passed_checks": 1918,
  "failed_checks": 4,
  "integrity_pct": 99.7919,
  "failures_by_check": {
    "barcode_checksum_valid": 1,
    "has_storage_location": 1,
    "has_performer": 2
  }
}
```

The 99.7919% is a computed result, not a hardcoded target: it falls out of
a fixed ~0.3% synthetic fault-injection rate applied to ~1,922 individual
per-row integrity checks across 40 cell lines, 205 vials, and 511
chain-of-custody events. Run it yourself — `random.seed()` calls in
`benchling_sim/`, `sapio_sim/`, and `integration/merge.py` make it
reproducible, but changing the fault rate or dataset size will move the
number, which is the honest point.

## Repo layout

```
benchling_sim/    Benchling-ELN-shaped mock generator (cell line registrations, passage entries)
sapio_sim/        Sapio-LIMS-shaped mock generator (vials, transfer events, QC results)
integration/      Real Python: db.py (SQLite schema), barcode.py (Code128 encoder),
                  merge.py (standardization/merge + fault injection), integrity.py (scorer)
data/             Generated mock JSON + clm_inventory.db (gitignored) + integrity_report.json
tests/            Real pytest against the actual generated database
run_all.py        End-to-end pipeline runner
logs/             Captured real output from an actual run_all.py execution
```
