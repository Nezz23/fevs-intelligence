"""Land each wave in Snowflake (FEVS.RAW.FEVS_<wave>), exactly as published, after its contract passes.

The same contract check as the DuckDB loader runs first. The file is then PUT to an internal stage
(compressed on the way, no S3 needed) and COPYed into an all-text table with the same lineage columns:
file row number, file name, SHA-256, contract version, load time. A wave whose file and contract are
unchanged since its last load is skipped. Connection settings come from the environment (.env); login
is by key pair, so no password exists anywhere.

    source .env && python -m ingestion.load_snowflake [waves...]
"""
from __future__ import annotations

import os
import sys
import time

import snowflake.connector

from ingestion.contracts import ContractViolation, check, data_file, header, waves


def connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"], role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"], database=os.environ["SNOWFLAKE_DATABASE"])


def ident(name: str) -> str:
    """Upper-case, quoted: Snowflake's own spelling of an unquoted name, safe for any header."""
    return '"' + name.upper().replace('"', '""') + '"'


def setup(cur) -> None:
    cur.execute("create schema if not exists raw")
    cur.execute("create stage if not exists raw.landing comment = 'OPM public data files, as downloaded'")
    cur.execute("create table if not exists raw._loads (wave int, sha256 varchar, contract_version int, "
                "row_count bigint, loaded_at timestamp_ntz)")


def load(cur, wave: int) -> str:
    contract = check(wave)  # raises before anything is uploaded
    done = cur.execute("select sha256, contract_version from raw._loads where wave = %s", (wave,)).fetchall()
    if done and tuple(done[-1]) == (contract["sha256"], contract["version"]):
        return f"{wave}: unchanged, skipped"
    start = time.perf_counter()
    path = data_file(wave)
    cols = header(path)
    cur.execute(f"put 'file://{path}' @raw.landing/{wave}/ auto_compress = true overwrite = true parallel = 8")
    table = f"raw.fevs_{wave}"
    meta = ['"_ROW_NUMBER" bigint', '"_SOURCE_FILE" varchar', '"_FILE_SHA256" varchar',
            '"_CONTRACT_VERSION" int', '"_LOADED_AT" timestamp_ntz']
    cur.execute(f"create or replace table {table} ({', '.join(f'{ident(c)} varchar' for c in cols)}, "
                f"{', '.join(meta)})")
    picks = ", ".join(f"${i}" for i in range(1, len(cols) + 1))
    cur.execute(f"""
        copy into {table}
        from (select {picks}, metadata$file_row_number, '{path.name}', '{contract["sha256"]}',
                     {contract["version"]}, current_timestamp()::timestamp_ntz
              from @raw.landing/{wave}/)
        file_format = (type = csv skip_header = 1 field_optionally_enclosed_by = '"'
                       empty_field_as_null = true encoding = 'UTF8')
        on_error = abort_statement""")
    rows = cur.execute(f"select count(*) from {table}").fetchone()[0]
    if rows != contract["row_count"]:
        cur.execute(f"drop table {table}")
        raise ContractViolation(f"wave {wave}: loaded {rows} rows, contract says {contract['row_count']}")
    cur.execute("delete from raw._loads where wave = %s", (wave,))
    cur.execute("insert into raw._loads values (%s, %s, %s, %s, current_timestamp()::timestamp_ntz)",
                (wave, contract["sha256"], contract["version"], rows))
    return f"{wave}: loaded {rows:,} rows in {time.perf_counter() - start:.1f}s"


if __name__ == "__main__":
    with connect() as con:
        cur = con.cursor()
        setup(cur)
        for w in [int(a) for a in sys.argv[1:]] or waves():
            print(load(cur, w), flush=True)
