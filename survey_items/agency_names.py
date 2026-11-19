"""Write agency_names.csv: each two-letter agency code with the name OPM's codebook gives it.

Names come only from the codebooks (2014-2024 Excel; 2012-2013 Word tables for codes later waves lack). Where a name changed, the latest wave's is kept,
with the wave it was taken from.
"""
import csv
import glob
import re
from pathlib import Path

import docx
import openpyxl

HERE = Path(__file__).resolve().parent
SHEETS = ("Agency Variable", "Work Unit Information", "Agency")

if __name__ == "__main__":
    names = {}
    for wave in range(2014, 2025):
        files = [f for f in glob.glob(str(HERE.parent / "data" / "extracted" / str(wave) / "*.xlsx")) if "odebook" in f]
        wb = openpyxl.load_workbook(files[0], read_only=True)
        for sheet in (s for s in wb.sheetnames if s in SHEETS):
            for row in wb[sheet].iter_rows(values_only=True):
                cells = [c for c in row if c is not None]
                if len(cells) >= 2 and re.fullmatch(r"[A-Z]{2}", str(cells[0]).strip()) and str(cells[0]) != "XX":
                    names[str(cells[0]).strip()] = (re.sub(r"\s+", " ", str(cells[1])).strip(), wave)
    for wave in (2013, 2012):
        for path in glob.glob(str(HERE.parent / "data" / "extracted" / str(wave) / "*.docx")):
            for table in docx.Document(path).tables:
                for r in table.rows:
                    code, name = (c.text.strip().strip('"') for c in r.cells[:2]) if len(r.cells) > 1 else ("", "")
                    if re.fullmatch(r"[A-Z]{2}", code) and code != "XX" and code not in names and name:
                        names[code] = (re.sub(r"\s+", " ", name), wave)
    with open(HERE / "agency_names.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["agency_code", "agency_name", "name_from_wave"])
        for code in sorted(names):
            w.writerow([code, *names[code]])
    print(f"{len(names)} agencies")
