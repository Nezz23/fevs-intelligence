"""Every number the app and the assistant show comes from here, and here reads only the gold export.

Nothing in this module draws a screen or calls a model. Each metric is defined once in METRICS and
resolved to a gold table (an OPM index, a single question, or stated leave intent), so a chart, a KPI
card and an assistant answer about "supervisor trust in 2024" are the same row of the same table.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent / "data"
LATEST = 2024
GOVERNMENTWIDE = "ALL"


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    kind: str            # "index" (OPM index or subindex), "question" (one item), "leave" (stated intent)
    source: str          # subindex_name, 2024 item code, or leave-intent column
    theme: str
    higher_is_better: bool
    blurb: str
    synonyms: tuple[str, ...] = ()


METRICS: dict[str, Metric] = {m.id: m for m in [
    Metric("engagement", "Employee engagement", "index", "employee_engagement", "Engagement", True,
           "OPM's Employee Engagement Index: the conditions that foster engagement (15 items, 3 subindices).",
           ("engagement", "engaged", "eei")),
    Metric("global_satisfaction", "Global satisfaction", "index", "global_satisfaction", "Satisfaction", True,
           "OPM's Global Satisfaction Index: satisfaction with job, pay and organization, and recommending it.",
           ("global satisfaction", "gsi", "overall satisfaction")),
    Metric("job_satisfaction", "Job satisfaction", "question", "Q70", "Satisfaction", True,
           "\"Considering everything, how satisfied are you with your job?\"",
           ("job satisfaction", "satisfied with their job", "satisfied with my job", "satisfied", "satisfaction",
            "happy", "happiness", "love their job", "like their job")),
    Metric("pay_satisfaction", "Pay satisfaction", "question", "Q71", "Satisfaction", True,
           "\"Considering everything, how satisfied are you with your pay?\"", ("pay", "salary", "compensation")),
    Metric("recommend", "Would recommend their organization", "question", "Q46", "Satisfaction", True,
           "\"I recommend my organization as a good place to work.\"", ("recommend", "good place to work")),
    Metric("leaders_lead", "Leaders Lead", "index", "leaders_lead", "Leadership", True,
           "OPM's Leaders Lead subindex: how employees see senior leaders' integrity, motivation and communication.",
           ("leaders lead", "leadership", "senior leadership", "leaders")),
    Metric("senior_leader_respect", "Respect for senior leaders", "question", "Q62", "Leadership", True,
           "\"I have a high level of respect for my organization's senior leaders.\"",
           ("respect for senior leaders", "respect senior leaders", "senior leaders", "executives")),
    Metric("supervisor_trust", "Trust in supervisor", "question", "Q52", "Leadership", True,
           "\"I have trust and confidence in my supervisor.\"",
           ("trust", "supervisor trust", "trust in supervisor", "trust their supervisor", "manager trust")),
    Metric("supervisors", "Supervisors", "index", "supervisors", "Leadership", True,
           "OPM's Supervisors subindex: support, listening, respect and trust between employee and supervisor.",
           ("supervisors", "supervisor", "managers", "manager")),
    Metric("workload", "Workload is reasonable", "question", "Q5", "Workload & wellbeing", True,
           "\"My workload is reasonable.\" FEVS has no burnout scale; this is its direct workload item.",
           ("workload", "burnout", "overworked", "work load", "too much work", "stress")),
    Metric("work_life_support", "Supervisor supports work-life balance", "question", "Q49", "Workload & wellbeing", True,
           "\"My supervisor supports my need to balance work and other life issues.\"",
           ("work-life", "work life", "balance", "flexibility")),
    Metric("considering_leaving", "Considering leaving", "leave", "pct_considering_leaving", "Intention to leave", False,
           "Survey-weighted share who say they are considering leaving their organization within a year: a "
           "stated intention, not observed turnover.",
           ("leaving", "leave", "quit", "quitting", "turnover", "attrition", "intention to leave", "intent to leave",
            "retention", "stay")),
    Metric("leave_government", "Considering leaving government", "leave", "pct_to_leave_government",
           "Intention to leave", False,
           "Share considering leaving their organization to take a job outside the federal government.",
           ("leave government", "leaving government", "private sector", "outside government")),
]}


@lru_cache(maxsize=None)
def table(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


@lru_cache(maxsize=None)
def manifest() -> dict:
    return json.loads((DATA / "manifest.json").read_text())


@lru_cache(maxsize=None)
def question_id_2024(item_code: str) -> str:
    x = table("crosswalk")
    return x[(x.wave == LATEST) & (x.item_code == item_code)].question_id.iloc[0]


def agencies() -> pd.DataFrame:
    """Agencies with at least one published (unsuppressed) result, with the waves they appear in."""
    q = table("question_results")
    q = q[(q.org_level == "agency") & ~q.is_suppressed]
    out = q.groupby(["agency_code", "agency_name"], dropna=False).wave.agg(["min", "max", "nunique"]).reset_index()
    out.columns = ["agency_code", "agency_name", "first_wave", "last_wave", "n_waves"]
    out["agency_name"] = out.agency_name.fillna(out.agency_code)
    return out.sort_values("agency_name").reset_index(drop=True)


def agency_name(code: str) -> str:
    if code == GOVERNMENTWIDE:
        return "Governmentwide"
    a = agencies()
    hit = a[a.agency_code == code]
    return hit.agency_name.iloc[0] if len(hit) else code


def series(metric_id: str, agency_code: str = GOVERNMENTWIDE) -> pd.DataFrame:
    """One metric over every wave: wave, value (0-1), respondents, suppressed, comparable, note.

    `comparable` is False where a wave's value should not be read as part of the same trend: an index
    whose items were not all asked that year, or a question whose wording changed that year."""
    m = METRICS[metric_id]
    level = "governmentwide" if agency_code == GOVERNMENTWIDE else "agency"
    if m.kind == "index":
        t = table("index_scores")
        t = t[(t.subindex_name == m.source) & (t.org_level == level) & (t.agency_code == agency_code)]
        asked_all = t.items_asked == t.items_defined
        out = pd.DataFrame({"wave": t.wave, "value": t.score, "respondents": t.min_item_respondents,
                            "suppressed": t.score.isna() & asked_all,
                            "comparable": asked_all,
                            "note": [("" if a else f"only {i} of {d} items asked")
                                     for a, i, d in zip(asked_all, t.items_asked, t.items_defined)]})
    elif m.kind == "question":
        t = table("question_results")
        t = t[(t.question_id == question_id_2024(m.source)) & (t.org_level == level) & (t.agency_code == agency_code)]
        out = pd.DataFrame({"wave": t.wave, "value": t.pct_positive, "respondents": t.respondents,
                            "suppressed": t.is_suppressed, "comparable": t.wording_status != "reworded",
                            "note": t.wording_status.map(lambda s: "wording changed this year" if s == "reworded" else "")})
    else:
        t = table("leave_intent")
        t = t[(t.org_level == level) & (t.agency_code == agency_code)]
        out = pd.DataFrame({"wave": t.wave, "value": t[m.source], "respondents": t.respondents,
                            "suppressed": t.is_suppressed, "comparable": True, "note": ""})
    return out.sort_values("wave").reset_index(drop=True)


def value(metric_id: str, wave: int = LATEST, agency_code: str = GOVERNMENTWIDE) -> float | None:
    s = series(metric_id, agency_code)
    hit = s[s.wave == wave]
    return None if hit.empty or pd.isna(hit.value.iloc[0]) else float(hit.value.iloc[0])


def ranking(metric_id: str, wave: int = LATEST) -> pd.DataFrame:
    """Every agency's value for one metric and wave, best first, with the governmentwide value beside it.
    Suppressed agencies are kept, with no value, so the page can say they exist but are hidden."""
    rows = []
    for _, a in agencies().iterrows():
        s = series(metric_id, a.agency_code)
        hit = s[s.wave == wave]
        if not hit.empty:
            r = hit.iloc[0]
            rows.append({"agency_code": a.agency_code, "agency_name": a.agency_name, "value": r.value,
                         "respondents": r.respondents, "suppressed": bool(r.suppressed) or pd.isna(r.value)})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["governmentwide"] = value(metric_id, wave)
    better = METRICS[metric_id].higher_is_better
    return out.sort_values("value", ascending=not better, na_position="last").reset_index(drop=True)


# --- The Workplace Happiness Paradox ---------------------------------------------------------------

FACTORS = {"job_satisfied": "Satisfied with job", "trusts_supervisor": "Trusts supervisor",
           "respects_senior_leaders": "Respects senior leaders", "workload_reasonable": "Workload is reasonable"}


def paradox(wave: int = LATEST) -> pd.DataFrame:
    p = table("paradox")
    return p[p.wave == wave].reset_index(drop=True)


def leaving_rate(wave: int = LATEST, **conditions: bool) -> tuple[float | None, float]:
    """Weighted share considering leaving among people matching the conditions (e.g. job_satisfied=True),
    and that group's share of the profiled workforce."""
    p = paradox(wave)
    for k, v in conditions.items():
        p = p[p[k] == v]
    p = p[~p.is_suppressed]
    if p.empty or p.share_of_workforce.sum() == 0:
        return None, 0.0
    w = p.share_of_workforce
    return float((p.pct_considering_leaving * w).sum() / w.sum()), float(w.sum())


def satisfied_but_leaving() -> pd.DataFrame:
    """Per wave: leaving rate among job-satisfied and among not-satisfied people."""
    rows = []
    for wave in sorted(table("paradox").wave.unique()):
        sat, sat_share = leaving_rate(int(wave), job_satisfied=True)
        unsat, _ = leaving_rate(int(wave), job_satisfied=False)
        rows.append({"wave": int(wave), "satisfied": sat, "not_satisfied": unsat, "satisfied_share": sat_share})
    return pd.DataFrame(rows)


def factor_gaps(wave: int = LATEST) -> pd.DataFrame:
    """Among job-satisfied people: the leaving rate when each other factor is positive vs not."""
    rows = []
    for k in ("trusts_supervisor", "respects_senior_leaders", "workload_reasonable"):
        yes, _ = leaving_rate(wave, job_satisfied=True, **{k: True})
        no, _ = leaving_rate(wave, job_satisfied=True, **{k: False})
        rows.append({"factor": k, "label": FACTORS[k], "positive": yes, "not_positive": no,
                     "gap": None if yes is None or no is None else no - yes})
    return pd.DataFrame(rows).sort_values("gap", ascending=False).reset_index(drop=True)


# --- Questions ---------------------------------------------------------------------------------------

def rated_questions() -> pd.DataFrame:
    """Questions with a percent-positive scale, with the waves they were asked in."""
    q = table("questions")
    q = q[q.scale_type.isin(["agreement", "satisfaction", "quality", "frequency"])].copy()
    q["wording_breaks"] = q.wording_breaks.fillna("")
    return q.reset_index(drop=True)


def question_series(question_id: str, agency_code: str = GOVERNMENTWIDE) -> pd.DataFrame:
    t = table("question_results")
    level = "governmentwide" if agency_code == GOVERNMENTWIDE else "agency"
    t = t[(t.question_id == question_id) & (t.org_level == level) & (t.agency_code == agency_code)]
    return t.sort_values("wave").reset_index(drop=True)


def search_questions(text: str, limit: int = 5) -> pd.DataFrame:
    """Rated questions whose wording shares the most words with the text."""
    words = {w for w in _words(text) if len(w) > 2} - STOP
    q = rated_questions()
    if not words:
        return q.head(0)
    q["score"] = q.canonical_text.map(lambda t: len(words & _words(t)))
    q = q[q.score > 0].sort_values(["score", "n_waves"], ascending=False)
    return q.head(limit).reset_index(drop=True)


STOP = {"the", "and", "for", "with", "are", "you", "your", "what", "how", "about", "does", "did", "who", "they",
        "their", "employees", "employee", "feel", "say", "think", "question", "questions", "survey", "fevs",
        "federal", "work", "most", "many", "much", "this", "that", "there", "was", "were", "has", "have"}


def _words(text: str) -> set[str]:
    import re
    return set(re.findall(r"[a-z]+", text.lower()))
