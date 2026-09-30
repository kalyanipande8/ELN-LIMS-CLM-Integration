"""
Benchling-ELN-shaped mock record generator for cell-line-management (CLM) workflows.

Honesty note: Benchling is a licensed, proprietary SaaS ELN with no free
public sandbox that models arbitrary custom entity schemas without a paid
tenant. There is no live Benchling connection here. What follows is
generated to match Benchling's *documented, public* data shapes as closely
as possible:

  - Custom Entities   https://docs.benchling.com/reference/entities
  - Notebook Entries  https://docs.benchling.com/reference/entries
  - Entry schema/fields pattern (schema id + fields dict keyed by field name)

Two Benchling entities are modeled, both as custom-entity-shaped records
with an attached notebook Entry, exactly as a real "Cell Line Registration"
and "Passage Record" schema would appear via the Benchling REST API
(`GET /custom-entities`, `GET /entries`):

  1. Cell Line Registration entities (one per registered cell line)
  2. Passage Record entries (one per passage event, referencing the cell line)

Output: data/benchling_cell_lines.json, data/benchling_passages.json
"""
import json
import random
import string
import datetime
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SPECIES = ["Homo sapiens", "Mus musculus", "Cricetulus griseus"]
TISSUE = ["Kidney", "Ovary", "Lung", "Liver", "Bone marrow", "Embryo"]
CELL_LINE_BASES = [
    "HEK293", "CHO-K1", "HeLa", "Jurkat", "NIH-3T3", "A549", "HepG2",
    "MCF-7", "U2OS", "K562", "THP-1", "COS-7",
]
SCIENTISTS = [
    ("kpande", "K. Pande"), ("jchen", "J. Chen"), ("mrodriguez", "M. Rodriguez"),
    ("asingh", "A. Singh"), ("tokafor", "T. Okafor"), ("lwu", "L. Wu"),
]


def _benchling_id(prefix):
    return f"{prefix}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=14))}"


def generate_cell_lines(n=40):
    """Benchling custom-entity-shaped 'Cell Line Registration' records."""
    records = []
    start = datetime.datetime(2025, 1, 6, 9, 0, 0)
    for i in range(n):
        base = random.choice(CELL_LINE_BASES)
        clone = random.randint(1, 40)
        name = f"{base}-C{clone}"
        handle, display = random.choice(SCIENTISTS)
        created = start + datetime.timedelta(days=i * 2, hours=random.randint(0, 8))
        rec = {
            "id": _benchling_id("ent"),
            "entityType": "custom_entity",
            "schema": {"id": "ts_cellline01", "name": "Cell Line Registration"},
            "name": name,
            "registryId": f"CL-{2025000 + i}",
            "fields": {
                "cell_line_name": {"value": name},
                "species": {"value": random.choice(SPECIES)},
                "tissue_origin": {"value": random.choice(TISSUE)},
                "culture_medium": {"value": random.choice(
                    ["DMEM + 10% FBS", "RPMI-1640 + 10% FBS", "F-12K + 10% FBS", "IMDM + 10% FBS"]
                )},
                "morphology": {"value": random.choice(["Adherent, epithelial", "Suspension", "Adherent, fibroblast-like"])},
                "source_organism_sex": {"value": random.choice(["Female", "Male", "Unknown"])},
            },
            "creator": {"handle": handle, "name": display},
            "createdAt": created.isoformat() + "Z",
            "modifiedAt": created.isoformat() + "Z",
            "webURL": f"https://stonybrook.benchling.com/stonybrook/f_/entity-{i}/",
        }
        records.append(rec)
    return records


def generate_passages(cell_lines, avg_passages=6):
    """Benchling notebook-Entry-shaped 'Passage Record' entries, one per passage event."""
    records = []
    for cl in cell_lines:
        n_passages = max(1, int(random.gauss(avg_passages, 2)))
        t = datetime.datetime.fromisoformat(cl["createdAt"].replace("Z", "")) + datetime.timedelta(days=3)
        passage_no = 1
        for _ in range(n_passages):
            handle, display = random.choice(SCIENTISTS)
            rec = {
                "id": _benchling_id("etr"),
                "entityType": "entry",
                "schema": {"id": "ts_passage01", "name": "Passage Record"},
                "name": f"Passage {passage_no} - {cl['fields']['cell_line_name']['value']}",
                "fields": {
                    "cell_line_registry_id": {"value": cl["registryId"]},
                    "cell_line_entity_id": {"value": cl["id"]},
                    "passage_number": {"value": passage_no},
                    "passage_date": {"value": t.date().isoformat()},
                    "confluency_pct": {"value": round(random.uniform(70, 95), 1)},
                    "viability_pct": {"value": round(random.uniform(88, 99.5), 1)},
                    "split_ratio": {"value": random.choice(["1:3", "1:4", "1:5", "1:6", "1:10"])},
                    "performed_by": {"value": display},
                },
                "creator": {"handle": handle, "name": display},
                "createdAt": t.isoformat() + "Z",
                "webURL": f"https://stonybrook.benchling.com/stonybrook/f_/entry-{cl['id']}-{passage_no}/",
            }
            records.append(rec)
            passage_no += 1
            t += datetime.timedelta(days=random.randint(2, 5))
    return records


def main():
    cell_lines = generate_cell_lines(40)
    passages = generate_passages(cell_lines)
    (DATA_DIR / "benchling_cell_lines.json").write_text(json.dumps(cell_lines, indent=2))
    (DATA_DIR / "benchling_passages.json").write_text(json.dumps(passages, indent=2))
    print(f"Generated {len(cell_lines)} Benchling cell-line entities, {len(passages)} passage entries")


if __name__ == "__main__":
    main()
