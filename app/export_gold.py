"""Export the gold layer (and only the gold layer) to app/data/ as Parquet for the app and the assistant.

The app never opens the warehouse: it reads these files, which hold survey-weighted aggregates only.
Suppressed groups (under OPM's Rule of Ten) are exported with every value empty, including their
respondent count, so the app can say a result exists but is hidden without revealing how small it is.

    python -m app.export_gold
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "warehouse" / "fevs.duckdb"
OUT = Path(__file__).resolve().parent / "data"

EXPORTS = {
    "question_results": """
        select r.wave, r.question_id, r.canonical_text, r.scale_type, r.org_level, r.agency_code, a.agency_name,
               case when r.is_suppressed then null else r.respondents end as respondents,
               r.weighted_respondents, r.pct_positive, r.pct_neutral, r.pct_negative, r.pct_do_not_know,
               r.is_suppressed, r.wording_status
        from gold.gld_question_results r left join reference.agency_names a using (agency_code)""",
    "index_scores": """
        select s.*, a.agency_name from gold.gld_index_scores s left join reference.agency_names a using (agency_code)""",
    "leave_intent": """
        select l.wave, l.org_level, l.agency_code, a.agency_name,
               case when l.is_suppressed then null else l.respondents end as respondents,
               l.pct_considering_leaving, l.pct_to_another_federal_job, l.pct_to_leave_government,
               l.pct_other_reason, l.is_suppressed
        from gold.gld_leave_intent l left join reference.agency_names a using (agency_code)""",
    "paradox": """
        select wave, job_satisfied, trusts_supervisor, respects_senior_leaders, workload_reasonable,
               case when is_suppressed then null else respondents end as respondents,
               case when is_suppressed then null else pct_considering_leaving end as pct_considering_leaving,
               case when is_suppressed then null else share_of_workforce end as share_of_workforce, is_suppressed
        from gold.gld_workplace_paradox""",
    "reconciliation": "select * from gold.gld_opm_reconciliation",
    "questions": "select * from reference.question_catalog",
    "crosswalk": "select * from reference.question_crosswalk",
    "wording_decisions": "select * from reference.wording_decisions",
    "paradox_questions": "select * from reference.paradox_questions",
    "index_items": "select * from reference.opm_index_items",
    "leave_codes": "select * from reference.leave_intent_codes",
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    counts = {}
    for name, sql in EXPORTS.items():
        con.execute(f"copy ({sql}) to '{OUT / name}.parquet' (format parquet, compression zstd)")
        counts[name] = con.sql(f"select count(*) from '{OUT / name}.parquet'").fetchall()[0][0]
    stats = con.sql("""select count(*) from silver.slv_respondents""").fetchall()[0][0]
    answers = con.sql("""select count(*) from silver.slv_item_responses""").fetchall()[0][0]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {"exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_commit": commit,
                "respondents": stats, "item_answers": answers, "rows": counts,
                "min_cell_respondents": 10}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
