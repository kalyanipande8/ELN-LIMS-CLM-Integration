"""
Sapio-LIMS-shaped mock record generator for cell-line-management (CLM)
vial inventory, cryopreservation, and QC testing.

Honesty note: Sapio is a licensed, proprietary enterprise LIMS platform.
There is no public sandbox or free tenant that exposes its Data Designer /
Webservice API without a paid license, so this is not a live Sapio
connection. Records below are shaped to match Sapio's documented,
public data model as closely as possible:

  - DataRecord model: {recordId, dataTypeName, fields: {...}}
    https://help.sapiosciences.com/ (Platform SDK: VeloxDataRecord / webservice
    DataRecord JSON payloads used by ELN/LIMS record retrieval endpoints)

Three Sapio DataTypes are modeled:
  1. CellLineVial       - one record per cryopreserved vial in inventory
  2. VialTransferEvent  - one record per freeze/thaw/transfer/storage-move
  3. QCTestResult       - one record per mycoplasma / STR-identity test

Output: data/sapio_vials.json, data/sapio_transfers.json, data/sapio_qc.json
"""
import json
import random
import datetime
from pathlib import Path

random.seed(7)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

TECHS = ["K. Pande", "J. Chen", "M. Rodriguez", "A. Singh", "T. Okafor", "L. Wu"]
FREEZERS = ["LN2-Tank-01", "LN2-Tank-02", "ULT-Freezer-A", "ULT-Freezer-B"]
CRYOMEDIA = ["90% FBS + 10% DMSO", "CryoStor CS10", "95% FBS + 5% DMSO"]


def load_benchling_cell_lines():
    with open(DATA_DIR / "benchling_cell_lines.json") as f:
        return json.load(f)


def generate_vials(cell_lines, record_id_start=100000):
    records = []
    rid = record_id_start
    t0 = datetime.datetime(2025, 1, 10, 10, 0, 0)
    for cl in cell_lines:
        n_vials = random.randint(2, 8)
        cl_name = cl["fields"]["cell_line_name"]["value"]
        for v in range(n_vials):
            freeze_date = t0 + datetime.timedelta(days=random.randint(0, 250))
            rec = {
                "recordId": rid,
                "dataTypeName": "CellLineVial",
                "fields": {
                    "CellLineRegistryId": cl["registryId"],
                    "CellLineName": cl_name,
                    "VialId": f"VIAL-{rid}",
                    "PassageAtFreeze": random.randint(1, 15),
                    "FreezeDate": freeze_date.date().isoformat(),
                    "CryoMedium": random.choice(CRYOMEDIA),
                    "StorageLocation": random.choice(FREEZERS),
                    "StorageBox": f"Box-{random.randint(1, 20):02d}",
                    "StoragePosition": f"{random.choice('ABCDEFGH')}{random.randint(1, 9)}",
                    "CellCountAtFreeze": random.randint(1_000_000, 5_000_000),
                    "ViabilityPctAtFreeze": round(random.uniform(85, 99), 1),
                    "FrozenBy": random.choice(TECHS),
                    "Status": "IN_STORAGE",
                },
            }
            records.append(rec)
            rid += 1
    return records


def generate_transfers(vials):
    """VialTransferEvent records: freeze (initial), plus some thaw/transfer events."""
    records = []
    tid = 500000
    for vial in vials:
        freeze_date = datetime.datetime.fromisoformat(vial["fields"]["FreezeDate"])
        # Initial freeze event
        records.append({
            "recordId": tid,
            "dataTypeName": "VialTransferEvent",
            "fields": {
                "VialId": vial["fields"]["VialId"],
                "EventType": "FREEZE",
                "EventTimestamp": (freeze_date + datetime.timedelta(hours=1)).isoformat(),
                "PerformedBy": vial["fields"]["FrozenBy"],
                "FromLocation": "Culture Hood",
                "ToLocation": vial["fields"]["StorageLocation"],
                "Notes": "Initial cryopreservation",
            },
        })
        tid += 1
        # Some vials get a later thaw or inter-freezer transfer
        roll = random.random()
        if roll < 0.35:
            thaw_date = freeze_date + datetime.timedelta(days=random.randint(10, 200))
            records.append({
                "recordId": tid,
                "dataTypeName": "VialTransferEvent",
                "fields": {
                    "VialId": vial["fields"]["VialId"],
                    "EventType": "THAW",
                    "EventTimestamp": thaw_date.isoformat(),
                    "PerformedBy": random.choice(TECHS),
                    "FromLocation": vial["fields"]["StorageLocation"],
                    "ToLocation": "Culture Hood",
                    "Notes": "Thawed for expansion",
                },
            })
            tid += 1
            vial["fields"]["Status"] = "THAWED"
        elif roll < 0.5:
            transfer_date = freeze_date + datetime.timedelta(days=random.randint(5, 150))
            new_loc = random.choice([f for f in FREEZERS if f != vial["fields"]["StorageLocation"]])
            records.append({
                "recordId": tid,
                "dataTypeName": "VialTransferEvent",
                "fields": {
                    "VialId": vial["fields"]["VialId"],
                    "EventType": "TRANSFER",
                    "EventTimestamp": transfer_date.isoformat(),
                    "PerformedBy": random.choice(TECHS),
                    "FromLocation": vial["fields"]["StorageLocation"],
                    "ToLocation": new_loc,
                    "Notes": "Freezer capacity rebalancing",
                },
            })
            vial["fields"]["StorageLocation"] = new_loc
            tid += 1
    return records


def generate_qc(cell_lines, record_id_start=700000):
    """QCTestResult records: mycoplasma + STR identity per cell line, periodically."""
    records = []
    rid = record_id_start
    for cl in cell_lines:
        cl_name = cl["fields"]["cell_line_name"]["value"]
        n_tests = random.randint(1, 3)
        t = datetime.datetime.fromisoformat(cl["createdAt"].replace("Z", "")) + datetime.timedelta(days=14)
        for _ in range(n_tests):
            myco_positive = random.random() < 0.03  # ~3% contamination rate, realistic
            str_match = random.random() > 0.02  # ~2% identity mismatch rate
            records.append({
                "recordId": rid,
                "dataTypeName": "QCTestResult",
                "fields": {
                    "CellLineRegistryId": cl["registryId"],
                    "CellLineName": cl_name,
                    "TestDate": t.date().isoformat(),
                    "TestedBy": random.choice(TECHS),
                    "MycoplasmaResult": "POSITIVE" if myco_positive else "NEGATIVE",
                    "MycoplasmaMethod": "PCR (Lonza MycoAlert)",
                    "STRIdentityResult": "MATCH" if str_match else "NO_MATCH",
                    "STRIdentityMethod": "ATCC STR Profiling (16 markers)",
                    "STRMarkersMatched": 16 if str_match else random.randint(6, 14),
                },
            })
            rid += 1
            t += datetime.timedelta(days=random.randint(30, 90))
    return records


def main():
    cell_lines = load_benchling_cell_lines()
    vials = generate_vials(cell_lines)
    transfers = generate_transfers(vials)
    qc = generate_qc(cell_lines)
    (DATA_DIR / "sapio_vials.json").write_text(json.dumps(vials, indent=2))
    (DATA_DIR / "sapio_transfers.json").write_text(json.dumps(transfers, indent=2))
    (DATA_DIR / "sapio_qc.json").write_text(json.dumps(qc, indent=2))
    print(f"Generated {len(vials)} Sapio CellLineVial records, {len(transfers)} transfer events, {len(qc)} QC results")


if __name__ == "__main__":
    main()
