"""Recompute headline app numbers straight from OPM's raw CSV with pandas, bypassing dbt entirely.

If the warehouse and this independent path disagree, one of them is wrong. Skipped when the raw files
are not downloaded (as in CI, which runs on the sample)."""
from pathlib import Path

import pandas as pd
import pytest

from app import data as d

RAW = Path(__file__).resolve().parent.parent / "data" / "extracted" / "2024"
pytestmark = pytest.mark.skipif(not RAW.exists(), reason="OPM 2024 public data file not downloaded")


@pytest.fixture(scope="module")
def wave_2024():
    path = next(RAW.glob("*.csv"))
    return pd.read_csv(path, usecols=["POSTWT", "agency", "Q5", "Q52", "Q62", "Q70", "DLEAVING"], dtype=str)


def pct_positive(df, item, mask=None):
    rows = df if mask is None else df[mask]
    rated = rows[rows[item].isin(list("12345"))]
    w = rated.POSTWT.astype(float)
    return (w * rated[item].isin(["4", "5"])).sum() / w.sum()


def test_job_satisfaction_2024_matches_an_independent_pandas_computation(wave_2024):
    assert d.value("job_satisfaction", 2024) == pytest.approx(pct_positive(wave_2024, "Q70"), abs=1e-12)


def test_army_supervisor_trust_2024_matches(wave_2024):
    expected = pct_positive(wave_2024, "Q52", wave_2024.agency == "AR")
    assert d.value("supervisor_trust", 2024, "AR") == pytest.approx(expected, abs=1e-12)


def test_considering_leaving_2024_matches(wave_2024):
    df = wave_2024[wave_2024.DLEAVING.isin(list("ABCD"))]
    w = df.POSTWT.astype(float)
    assert d.value("considering_leaving", 2024) == pytest.approx((w * (df.DLEAVING != "A")).sum() / w.sum(), abs=1e-12)


def test_satisfied_but_leaving_2024_matches(wave_2024):
    df = wave_2024
    for item in ("Q5", "Q52", "Q62", "Q70"):
        df = df[df[item].isin(list("12345"))]
    df = df[df.DLEAVING.isin(list("ABCD")) & df.Q70.isin(["4", "5"])]
    w = df.POSTWT.astype(float)
    rate, _ = d.leaving_rate(2024, job_satisfied=True)
    assert rate == pytest.approx((w * (df.DLEAVING != "A")).sum() / w.sum(), abs=1e-12)
