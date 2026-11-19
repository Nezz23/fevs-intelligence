"""Read every FEVS wave's codebook into one item catalog.

OPM published the codebook in four layouts over the years:
  2012-2013  Word document, items as numbered paragraphs ("10.\\tMy workload is reasonable.")
  2014-2019  Excel, sheet 'Core Survey Items', one row per item, labels across columns
  2020       Excel, one row per variable with response rows underneath
  2021-2024  Excel, long format: one row per item x response value

Each reader returns rows of (wave, item_code, item_text, responses) where responses maps a coded
value to its label. Only items that appear as columns in that wave's data file are kept, so the
catalog never claims an item exists in a wave when the data has no such column.
"""
from __future__ import annotations

import csv
import glob
import re
from pathlib import Path

import docx
import openpyxl

ITEM_COLUMN = re.compile(r"^[QV]\d+[A-Z]?(_\d+)?$", re.I)
REDACTED = re.compile(r"redacted", re.I)


def data_columns(wave_dir: Path) -> list[str]:
    """Item columns in the wave's data file: the ground truth for which items exist."""
    path = next(p for p in wave_dir.glob("*.csv"))
    with open(path, newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    return [c.strip().upper() for c in header if ITEM_COLUMN.match(c.strip())]


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _from_docx(path: Path) -> dict[str, dict]:
    items, last = {}, 0
    for p in docx.Document(path).paragraphs:
        m = re.match(r"^(\d+)\.\s+(.*)$", p.text.strip())
        if not m:
            continue
        n = int(m.group(1))
        if n <= last:  # numbering restarts in the demographics section
            break
        items[f"Q{n}"] = {"item_text": _clean(m.group(2)), "responses": {}}
        last = n
    return items


def _from_xlsx_wide(path: Path) -> dict[str, dict]:
    """2014-2019: a values row (blank first cell, coded values from column C) precedes each block of items,
    and each item row holds the label for each coded value in the same column."""
    wb = openpyxl.load_workbook(path, read_only=True)
    items, values, stem = {}, [], ""
    for r in wb["Core Survey Items"].iter_rows(values_only=True):
        r = list(r) + [None] * 3
        if r[0] is None and r[2] is not None and str(r[2]).strip().isdigit():
            values, stem = [None if c is None else str(c).strip() for c in r[2:]], ""
        elif r[0] is None and r[1] and r[2] is None:
            stem = _clean(r[1])  # e.g. "Do you participate in the following Work/Life programs?"
        elif r[0] is None and r[1] is None:
            stem = ""  # a blank row ends the block the stem applies to
        elif r[0] is not None and str(r[0]).strip().isdigit() and r[1]:
            labels = r[2:]
            text = re.sub(r"^\d+\.\s*", "", _clean(r[1]))  # some rows repeat their number: "74. Telework"
            items[f"Q{int(r[0])}"] = {"item_text": f"{stem} {text}".strip(), "responses": {
                v: _clean(l) for v, l in zip(values, labels) if v is not None and l is not None}}
    for ws in wb.worksheets:  # e.g. 2019 'Shutdown' sheet in the long layout
        if ws.title != "Core Survey Items":
            items.update({k: v for k, v in _read_long_sheet(ws).items() if k not in items})
    return items


def _var_code(var) -> str | None:
    if var is None:
        return None
    v = str(var).strip().upper()
    if v.isdigit():
        v = f"Q{int(v)}"
    return v if ITEM_COLUMN.match(v) else None


def _read_long_sheet(ws) -> dict[str, dict]:
    rows = list(ws.iter_rows(values_only=True))
    if not rows or not rows[0] or str(rows[0][0]).strip().upper() != "VARIABLE":
        return {}
    items, current = {}, None
    for r in rows[1:]:
        var, text, value, label = (list(r) + [None] * 4)[:4]
        code = _var_code(var)
        if code:
            current = code
            entry = items.setdefault(code, {"item_text": "", "responses": {}})
            if text and not entry["item_text"]:
                entry["item_text"] = _clean(text)
            if not entry["item_text"] and label:  # multi-select boxes carry their text in the label column
                entry["item_text"] = _clean(label)
        elif var is not None:
            current = None  # a non-item variable (demographics, agency) ends the block
        if current and value is not None and label is not None:
            items[current]["responses"][_clean(value)] = _clean(label)
    return items


def _from_xlsx_long(path: Path) -> dict[str, dict]:
    items = {}
    for ws in openpyxl.load_workbook(path, read_only=True).worksheets:
        items.update({k: v for k, v in _read_long_sheet(ws).items() if k not in items})
    return items


def read_wave(wave_dir: Path) -> list[dict]:
    wave = int(wave_dir.name)
    docx_files = [p for p in wave_dir.glob("*.docx") if "codebook" in p.name.lower()]
    xlsx_files = [p for p in wave_dir.glob("*.xlsx") if "codebook" in p.name.lower()]
    if docx_files:
        parsed = _from_docx(docx_files[0])
    elif "Core Survey Items" in openpyxl.load_workbook(xlsx_files[0], read_only=True).sheetnames:
        parsed = _from_xlsx_wide(xlsx_files[0])
    else:
        parsed = _from_xlsx_long(xlsx_files[0])
    rows = []
    for code in data_columns(wave_dir):
        entry = parsed.get(code, {"item_text": "", "responses": {}})
        rows.append({"wave": wave, "item_code": code, "item_text": entry["item_text"],
                     "is_redacted": bool(REDACTED.search(entry["item_text"])),
                     "responses": entry["responses"]})
    return rows


def read_all(extracted: Path) -> list[dict]:
    return [row for d in sorted(extracted.iterdir()) if d.is_dir() for row in read_wave(d)]
