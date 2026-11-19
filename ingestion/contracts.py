"""Versioned data contracts for the FEVS public data files: one YAML file per wave.

A contract records what a wave's file looked like when it was reviewed: its columns in order, each
column's role, the values each column may hold, the row count and the file's SHA-256. Loading checks
the file against its contract first and refuses to load on any difference, printing every one. OPM
re-issues files (2024's is named ..._rv20261007), so a changed file is caught and reviewed, then the
contract's version is raised on purpose. Nothing drifts in silently.

    python -m ingestion.contracts write 2024    # draft a contract from the file and the codebook
    python -m ingestion.contracts check         # check every wave's file against its contract
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
EXTRACTED = ROOT / "data" / "extracted"
CONTRACTS = Path(__file__).resolve().parent / "contracts"
ITEM = re.compile(r"^[QV]\d+[A-Z]?(_\d+)?$", re.I)
# Respondent-level identifiers are kept out of every layer past raw: no ID is needed for aggregates.
ROLES = {"POSTWT": "weight", "AGENCY": "org", "SUBELEM": "org", "PLEVEL1": "org", "PLEVEL2": "org",
         "LEVEL1": "org", "USERID": "respondent_id", "RANDOMID": "respondent_id", "RANDOM": "sample_flag",
         "YEAR": "wave"}
MAX_DOMAIN = 60  # columns with more distinct values than this (ids, weights, org codes) get no value list


class ContractViolation(ValueError):
    pass


def data_file(wave: int) -> Path:
    return next((EXTRACTED / str(wave)).glob("*.csv"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def header(path: Path) -> list[str]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [c.strip() for c in next(csv.reader(f))]


def role(column: str) -> str:
    c = column.upper()
    if ITEM.match(c):
        return "item"
    if c in ROLES:
        return ROLES[c]
    return "demographic" if c.startswith("D") else "other"


def profile(path: Path) -> tuple[int, dict[str, list[str] | None]]:
    """Row count and, per column, its distinct non-empty values (None when there are too many)."""
    con = duckdb.connect()
    con.execute(f"create table f as select * from read_csv('{path}', all_varchar=true, header=true)")
    rows = con.sql("select count(*) from f").fetchall()[0][0]
    pairs = con.sql("select col, list(distinct val order by val) from "
                    "(unpivot f on columns(*) into name col value val) "
                    "where trim(val) <> '' group by col").fetchall()
    domains = {c: None for c in header(path)}
    domains.update({c: (v if len(v) <= MAX_DOMAIN else None) for c, v in pairs})
    for c in domains:  # a column that is blank in every row has an empty domain, not an unknown one
        if c not in dict(pairs):
            domains[c] = []
    return rows, domains


def draft(wave: int) -> dict:
    path = data_file(wave)
    rows, domains = profile(path)
    columns = []
    for c in header(path):
        entry = {"name": c, "role": role(c)}
        if entry["role"] == "weight":
            entry["rule"] = "positive number, no blanks"
        elif domains[c] is not None and entry["role"] in ("item", "demographic", "sample_flag", "wave"):
            entry["allowed"] = domains[c]
        columns.append(entry)
    return {"contract": "opm_fevs_public_data_file", "wave": wave, "version": 1,
            "source_file": path.name, "sha256": sha256(path), "row_count": rows, "columns": columns}


def path_for(wave: int) -> Path:
    return CONTRACTS / f"fevs_{wave}.yml"


def check(wave: int, path: Path | None = None, sample: bool = False) -> dict:
    """Return the contract if the file matches it; raise ContractViolation listing every difference.

    sample=True checks a sample of the file (the CI fixture): its columns and answer codes must match the
    contract, but its name, size and checksum are its own."""
    contract = yaml.safe_load(path_for(wave).read_text())
    path = path or data_file(wave)
    problems = []
    digest = None
    if not sample:
        if path.name != contract["source_file"]:
            problems.append(f"file name changed: {contract['source_file']} -> {path.name}")
        digest = sha256(path)
        if digest != contract["sha256"]:
            problems.append(f"file content changed (sha256 {contract['sha256'][:12]}... -> {digest[:12]}...)")
    expected = [c["name"] for c in contract["columns"]]
    actual = header(path)
    for c in expected:
        if c not in actual:
            problems.append(f"column removed: {c}")
    for c in actual:
        if c not in expected:
            problems.append(f"column added: {c}")
    if not [p for p in problems if "column" in p] and expected != actual:
        problems.append("columns reordered")
    if (sample or digest != contract["sha256"]) and not [p for p in problems if "column" in p]:
        rows, domains = profile(path)
        if not sample and rows != contract["row_count"]:
            problems.append(f"row count changed: {contract['row_count']} -> {rows}")
        for c in contract["columns"]:
            new = set(domains.get(c["name"]) or []) - set(c.get("allowed", []))
            if "allowed" in c and new:
                problems.append(f"{c['name']}: values not in contract: {sorted(new)}")
    if problems:
        raise ContractViolation(f"wave {wave} breaks contract v{contract['version']}:\n  " + "\n  ".join(problems))
    return contract


class _Flow(list):
    pass


def _dump(contract: dict) -> str:
    """YAML with each value list on one line, so a diff of a changed contract reads at a glance."""
    yaml.SafeDumper.add_representer(_Flow, lambda d, v: d.represent_sequence("tag:yaml.org,2002:seq", v,
                                                                             flow_style=True))
    for c in contract["columns"]:
        if "allowed" in c:
            c["allowed"] = _Flow(c["allowed"])
    return yaml.safe_dump(contract, sort_keys=False, width=120)


def waves() -> list[int]:
    """Every wave with a contract: the contracts, not the downloaded files, define the warehouse."""
    return sorted(int(p.stem.split("_")[1]) for p in CONTRACTS.glob("fevs_*.yml"))


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["check"]
    if cmd == "write":
        CONTRACTS.mkdir(exist_ok=True)
        for w in [int(a) for a in args] or waves():
            if path_for(w).exists():
                sys.exit(f"{path_for(w).name} exists; edit it and raise its version instead of overwriting")
            path_for(w).write_text(_dump(draft(w)))
            print(f"wrote {path_for(w).relative_to(ROOT)}")
    else:
        failed = 0
        for w in [int(a) for a in args] or waves():
            try:
                c = check(w)
                print(f"{w}: ok (contract v{c['version']}, {c['row_count']:,} rows)")
            except ContractViolation as e:
                failed += 1
                print(e)
        sys.exit(1 if failed else 0)
