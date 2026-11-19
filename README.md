# FEVS Intelligence

**What makes people love, hate, or leave their jobs?**

An analytics-engineering warehouse over every public wave (2012-2024) of OPM's Federal Employee Viewpoint
Survey: 6.8 million federal employees' answers, 539 million item responses, 13 different file layouts.
It turns them into survey-weighted, trend-safe People Analytics metrics that reconcile with OPM's own
published results.

## Results

**It reproduces OPM's published numbers.** All 67 governmentwide figures in OPM's 2024 Governmentwide
Management Report that this warehouse scores (Employee Engagement Index and its three subindices,
Global Satisfaction Index and its four items, Performance Confidence Index and its four items, Employee
Experience Index, 2020-2024) equal ours once ours is rounded as OPM rounds. A dbt test
(`matches_opm_published_results`) keeps it that way. The five figures it does not score are listed in
that test with the reason (2020 Performance Confidence, see below).

**The Workplace Happiness Paradox (2024).** Job satisfaction and intention to stay are not the same thing:

| Profile (2024, survey-weighted) | Share of workforce | Considering leaving |
|---|---|---|
| Satisfied with job, trusts supervisor, respects senior leaders, workload reasonable | 41.1% | 19.1% |
| Satisfied with job, but none of the other three | 1.2% | 40.3% |
| Not satisfied with job, but all of the other three | 2.5% | 56.4% |
| None of the four | 8.2% | 73.5% |

Even among people satisfied with their job, 23.8% said they were considering leaving within a year
(2013: 20.4%). These are associations in observational survey data, not causes, and "considering
leaving" is a stated intention, not observed turnover.

## Architecture

```mermaid
flowchart LR
    OPM[OPM public data files<br/>13 waves, 4 codebook layouts] --> C{Data contract<br/>per wave}
    C -- pass --> RAW[(raw.fevs_YYYY<br/>as published, all text)]
    C -- any difference --> X[Load refused,<br/>every difference listed]
    CB[Codebooks] --> XW[Question crosswalk<br/>+ reviewed wording decisions]
    RAW --> B[bronze<br/>views: unpivot each layout]
    B --> S[silver<br/>incremental by wave + mapping fingerprint]
    XW --> S
    S --> G[gold<br/>weighted metrics, Rule of Ten]
    G --> T[Tests: contracts, grain,<br/>OPM reconciliation]
```

| Layer | What it holds | Key rule |
|---|---|---|
| raw | Each wave's file exactly as published, plus row number, file SHA-256, contract version | Loaded only if the file matches its versioned contract |
| bronze | One respondent table and one long item-answer view across all 13 layouts | Item columns are read from each raw table at run time; respondent IDs are dropped |
| silver | Typed respondents; every answer linked to its canonical question and scored | Incremental: rebuilds only waves whose file or reviewed mapping changed |
| gold | Question results, OPM indices, stated leave intent, the paradox profiles | Weighted by POSTWT; any group under 10 respondents is suppressed (OPM's Rule of Ten) |

One dbt project runs on DuckDB (local and CI) and has a Snowflake target (`prod`); SQL that differs
between them goes through adapter dispatch (`macros/reference_version.sql`). The Snowflake target is
configured but has not been run yet.

## What the data gets wrong if you trust it naively

These traps are each handled in code and pinned by a test or a reviewed table:

- **Item codes are not questions.** OPM renumbers items (job satisfaction is Q69 in 2012, Q70 in 2024) and
  reuses codes. The crosswalk (`survey_items/`) maps 1,070 item-waves to 271 questions by wording and
  answer scale, never by code.
- **Wording changes.** 44 near-identical wordings each have a written decision in
  `wording_decisions.csv`: `same` (typo), `reworded` (trend kept, break marked), or `different`. The build
  fails on any near-duplicate nobody has reviewed. Examples: "supervisor/team leader" became
  "supervisor" in 2014 (reworded); "the workforce has the job-relevant knowledge" became "my work unit"
  in 2018 (different: a different group is rated); one security item split into cyber and physical in
  2022 (different).
- **Same words, different answers.** The 2021 and 2023 telework questions share their wording but not
  their answer options, so they are separate questions.
- **Leave-intent codes swapped meaning in 2020.** Through 2019, B = "another federal job" and D =
  "other"; from 2020, B = "other" and D = "a job outside government". Codes are decoded per wave through
  `leave_intent_codes.csv`. The 2012 codebook lists five options with no codes for a four-code column, so
  2012 is excluded from leave-intent results rather than guessed.
- **Check-all-that-apply options** carry no parent question in the codebook and repeat across questions,
  so they are never trended.
- **"Do Not Know" is not a rating.** It is kept out of percent-positive denominators, as OPM does.
- **2020's COVID block** (V17/V18) prints item endings without their stems, so it is kept separate. OPM
  trends those items into the 2020 Performance Confidence Index; this warehouse does not, and says so.

## Measured

Measured on an Apple-silicon MacBook, DuckDB 2.0.0, dbt-core 1.12.7:

| Step | Time |
|---|---|
| Land all 13 waves (6,837,200 rows) after contract checks | 53.6 s |
| Re-land a wave whose file and contract are unchanged | 0.24 s |
| Draft one wave's contract (profile every column) | 2.1 s (was 44 s with one scan per column) |
| silver item responses, full build (539,108,211 rows) | 51-59 s |
| silver item responses, incremental run with nothing new | 3.0 s |
| `dbt build`, all 96 models, seeds and tests, full data | 40-43 s |
| `dbt build` in CI on the committed sample | 5 s |

## Run it

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
make test          # unit tests: crosswalk rules and data contracts
# CI path, no download needed: a real ~1,000-row-per-wave sample is committed in fixtures/sample
.venv/bin/python -m ingestion.load_duckdb --sample
DBT_PROFILES_DIR=transform .venv/bin/dbt build --project-dir transform --target ci --exclude tag:full_data
```

The full build needs OPM's public data files in `data/raw/` (downloaded from
[opm.gov/fevs/public-data-file](https://www.opm.gov/fevs/public-data-file/)), unzipped to `data/extracted/<year>/`, then
`make load build`.

## Privacy

Only OPM's public release files are used. Respondent IDs stop at the raw layer (a dbt test checks that no
later layer has them), every published result needs at least 10 respondents, and the planned public app
reads only gold aggregates.

## Status

Done: crosswalk, contracts, warehouse, tests, CI. Next: the People Analytics app, the analytics
assistant that cites gold metrics, and the Snowflake deployment.
