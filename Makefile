# Run everything from the repository root. dbt reads its project and profile from transform/.
PY := .venv/bin/python
DBT := DBT_PROFILES_DIR=transform .venv/bin/dbt
DBT_ARGS := --project-dir transform

.PHONY: crosswalk contracts load build test export app

crosswalk:      ## rebuild the question crosswalk from the codebooks (fails on any unreviewed wording)
	$(PY) -m survey_items.crosswalk

contracts:      ## check every wave's file against its data contract
	$(PY) -m ingestion.contracts check

load:           ## land the waves in DuckDB (skips any wave whose file and contract are unchanged)
	$(PY) -m ingestion.load_duckdb

build:          ## seeds, models and every data test
	$(DBT) build $(DBT_ARGS)

test:           ## Python unit tests
	$(PY) -m pytest -q tests

export:         ## write the gold layer to app/data (the only data the app reads)
	$(PY) -m app.export_gold

app:            ## launch the People Analytics app at http://localhost:8501
	.venv/bin/streamlit run app/streamlit_app.py
