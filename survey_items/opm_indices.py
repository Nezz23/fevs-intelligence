"""Write OPM's own index definitions (2024 Indices and Dimensions Guide) to opm_index_items.csv.

Each row is one item of one OPM index, keyed by its 2024 item code. The warehouse maps the code to a
canonical question through the crosswalk, so the same definition can be applied to earlier waves, and
the gold layer reports how many of an index's items each earlier wave actually asked.
"""
import csv
import glob
import re
from pathlib import Path

import docx

HERE = Path(__file__).resolve().parent
SLUG = {"Global Satisfaction Index": ("global_satisfaction", ""),
        "Performance Confidence Index": ("performance_confidence", ""),
        "Employee Experience": ("employee_experience", ""),
        "Employee Engagement Index - Intrinsic Work Experience Subindex": ("employee_engagement", "intrinsic_work_experience"),
        "Employee Engagement Index - Leaders Lead Subindex": ("employee_engagement", "leaders_lead"),
        "Employee Engagement Index - Supervisors Subindex": ("employee_engagement", "supervisors")}

if __name__ == "__main__":
    guide = glob.glob(str(HERE.parent / "data" / "extracted" / "2024" / "*Indices*.docx"))[0]
    rows = []
    for table in docx.Document(guide).tables:
        for r in table.rows[1:]:
            name, text, code = (c.text.strip() for c in r.cells[:3])
            if name in SLUG:
                index, subindex = SLUG[name]
                rows.append({"index_name": index, "subindex_name": subindex,
                             "item_code_2024": "Q" + str(int(re.sub(r"\D", "", code))), "item_text_2024": text})
    with open(HERE / "opm_index_items.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} index items")
