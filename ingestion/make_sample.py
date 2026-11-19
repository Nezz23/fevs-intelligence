"""Write the CI fixture: a systematic sample of about 1,000 real rows per wave, from OPM's public files.

CI cannot download 1.3 GB per run, and invented rows would test nothing real. Every k-th row keeps each
wave's real layout and answer codes, so CI runs the same contracts, models and tests as a full build
(except the reconciliation against OPM's published figures, which needs every row). Respondent IDs
are replaced by the row's position in the sample.

    python -m ingestion.make_sample
"""
import csv
from pathlib import Path

import yaml

from ingestion.contracts import data_file, path_for, waves

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "fixtures" / "sample"
TARGET_ROWS = 1000

if __name__ == "__main__":
    SAMPLE.mkdir(parents=True, exist_ok=True)
    for wave in waves():
        contract = yaml.safe_load(path_for(wave).read_text())
        ids = {c["name"] for c in contract["columns"] if c["role"] == "respondent_id"}
        step = max(1, contract["row_count"] // TARGET_ROWS)
        with open(data_file(wave), newline="", encoding="utf-8-sig") as src, \
                open(SAMPLE / f"fevs_{wave}.csv", "w", newline="") as out:
            reader, writer = csv.DictReader(src), None
            n = 0
            for i, row in enumerate(reader):
                if i % step:
                    continue
                n += 1
                for c in ids:
                    row[c] = str(n)
                writer = writer or csv.DictWriter(out, fieldnames=reader.fieldnames)
                if n == 1:
                    writer.writeheader()
                writer.writerow(row)
        print(f"{wave}: {n} rows (every {step}th)")
