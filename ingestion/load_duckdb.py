"""Land each wave's public data file in DuckDB, exactly as published, after its contract passes.

Each wave lands in raw.fevs_<wave>: every column as text (nothing is reinterpreted on the way in),
plus lineage columns: the file's row number, file name, SHA-256, contract version and load time.
A wave whose file and contract are unchanged since its last load is skipped, so a rerun costs seconds.

    python -m ingestion.load_duckdb [waves...]
    python -m ingestion.load_duckdb --sample     # the committed CI fixture, into warehouse/fevs_sample.duckdb
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb

from ingestion.contracts import ContractViolation, check, data_file, sha256, waves

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "warehouse" / "fevs.duckdb"
SAMPLE_WAREHOUSE = ROOT / "warehouse" / "fevs_sample.duckdb"
SAMPLE_DIR = ROOT / "fixtures" / "sample"


def load(con: duckdb.DuckDBPyConnection, wave: int, sample: bool = False) -> str:
    path = SAMPLE_DIR / f"fevs_{wave}.csv" if sample else data_file(wave)
    contract = check(wave, path, sample=sample)  # raises before anything is written
    if sample:
        contract = {**contract, "sha256": sha256(path), "row_count": None}
    table = f"raw.fevs_{wave}"
    con.execute("create schema if not exists raw")
    con.execute("create table if not exists raw._loads (wave int primary key, sha256 text, "
                "contract_version int, row_count bigint, loaded_at timestamp)")
    done = con.execute("select sha256, contract_version from raw._loads where wave = ?", [wave]).fetchall()
    if done and done[0] == (contract["sha256"], contract["version"]):
        return f"{wave}: unchanged, skipped"
    start = time.perf_counter()
    con.execute(f"""
        create or replace table {table} as
        select *, row_number() over () as _row_number, '{path.name}' as _source_file,
               '{contract["sha256"]}' as _file_sha256, {contract["version"]} as _contract_version,
               current_timestamp as _loaded_at
        from read_csv('{path}', all_varchar=true, header=true)""")
    rows = con.execute(f"select count(*) from {table}").fetchall()[0][0]
    if contract["row_count"] is not None and rows != contract["row_count"]:
        con.execute(f"drop table {table}")
        raise ContractViolation(f"wave {wave}: loaded {rows} rows, contract says {contract['row_count']}")
    con.execute("insert or replace into raw._loads values (?, ?, ?, ?, current_timestamp)",
                [wave, contract["sha256"], contract["version"], rows])
    return f"{wave}: loaded {rows:,} rows in {time.perf_counter() - start:.1f}s"


if __name__ == "__main__":
    args = sys.argv[1:]
    sample = "--sample" in args
    WAREHOUSE.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(SAMPLE_WAREHOUSE if sample else WAREHOUSE))
    for w in [int(a) for a in args if a != "--sample"] or waves():
        print(load(con, w, sample), flush=True)
