"""The analytics assistant: answers questions about FEVS from gold-layer metrics only, and cites them.

How an answer is made:
1. A planner turns the question into one call to a fixed set of tools (a metric's value or trend, an
   agency ranking, the paradox, a question search). The default planner is rule-based. If a local model
   is running (Ollama), it can plan instead; its plan is validated against the same tools, and any plan
   that does not validate falls back to the rules.
2. The tool reads app.data, which reads only the gold export.
3. The answer text is written from the tool's result by templates in this file. No model ever writes a
   number, so every number on screen is a cited row of a gold table.

It declines what the data cannot answer: individual respondents, causes, and actual turnover.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field

import pandas as pd

from app import data as d

TOOLS = ("metric_value", "metric_trend", "agency_ranking", "paradox", "search_questions", "help")


@dataclass
class Plan:
    tool: str
    metric: str | None = None
    wave: int | None = None
    wave_from: int | None = None
    agency: str = d.GOVERNMENTWIDE
    order: str = "top"
    text: str = ""
    planner: str = "rules"


@dataclass
class Citation:
    table: str
    detail: str


@dataclass
class Answer:
    text: str
    citations: list[Citation] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    chart: pd.DataFrame | None = None
    chart_kind: str | None = None   # "trend" or "ranking"
    plan: Plan | None = None


# --- Guardrails ---------------------------------------------------------------------------------------

INDIVIDUAL = re.compile(r"\b(who (is|are|said)|which (employee|person|people|respondent)s?\b(?! in)|"
                        r"individual|respondent id|name of|specific employee|identify)\b", re.I)
CAUSAL = re.compile(r"\b(why|cause[sd]?|because|drives?|driver|effect of|impact of|leads? to)\b", re.I)
TURNOVER = re.compile(r"\b(turnover|attrition|actually (left|leave|quit)|quit rate|separations?)\b", re.I)

CAUSAL_NOTE = ("FEVS is an observational survey, so these figures show associations, not causes. "
               "People who differ on one answer differ on many things at once.")
TURNOVER_NOTE = ("FEVS measures intention to leave (what people say they are considering), not actual "
                 "turnover. Many who consider leaving stay, and some who leave never said so.")


# --- Rule-based planner -------------------------------------------------------------------------------

def _find_metric(q: str) -> str | None:
    """The metric whose longest synonym appears in the question (longest wins: 'pay' vs 'satisfied')."""
    best, best_len = None, 0
    for m in d.METRICS.values():
        for s in (m.label.lower(), *m.synonyms):
            if re.search(rf"\b{re.escape(s)}s?\b", q) and len(s) > best_len:
                best, best_len = m.id, len(s)
    return best


AGENCY_ALIASES = {"va": "VA", "veterans": "VA", "nasa": "NN", "army": "AR", "navy": "NV", "air force": "AF",
                  "irs": "TR", "treasury": "TR", "dhs": "HS", "homeland": "HS", "hhs": "HE", "epa": "EP",
                  "state department": "ST", "department of state": "ST", "doj": "DJ", "justice": "DJ",
                  "usda": "AG", "agriculture": "AG", "commerce": "CM", "education": "ED", "energy": "DN",
                  "interior": "IN", "labor": "DL", "transportation": "TD", "dot": "TD", "hud": "HU",
                  "housing and urban": "HU", "gsa": "GS", "opm": "OM", "ssa": "SZ", "social security": "SZ",
                  "sba": "SB", "small business": "SB", "nsf": "NF", "nrc": "NU", "sec": "SE", "ftc": "FT",
                  "fcc": "FC", "usaid": "AM", "defense": "DD", "dod": "DD", "pentagon": "DD"}


def _find_agency(q: str) -> str | None:
    known = set(d.agencies().agency_code)
    for alias, code in sorted(AGENCY_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(alias)}\b", q) and code in known:
            return code
    for _, a in d.agencies().iterrows():
        name = str(a.agency_name).lower()
        core = re.sub(r"^(united states |u\.s\. )?(department of (the )?)?", "", name)
        if len(core) > 4 and core in q:
            return a.agency_code
    return None


def plan_with_rules(question: str) -> Plan:
    q = question.lower().strip()
    years = [int(y) for y in re.findall(r"\b(20(?:1[2-9]|2[0-4]))\b", q)]
    metric = _find_metric(q)
    agency = _find_agency(q) or d.GOVERNMENTWIDE
    if re.search(r"paradox|satisfied but|happy but|satisfied .*(still )?(leav|quit)|"
                 r"love .* leave|what (makes|keeps)|keeps? people", q):
        return Plan("paradox", wave=years[-1] if years else d.LATEST, text=q)
    if re.search(r"\b(which|what|rank|ranking|top|bottom|best|worst|highest|lowest|most|least|compare)\b.*"
                 r"\bagenc(y|ies)\b|\bagenc(y|ies)\b.*\b(rank|best|worst|highest|lowest|top|bottom)\b", q):
        order = "bottom" if re.search(r"\b(worst|lowest|bottom|least)\b", q) else "top"
        if metric and not d.METRICS[metric].higher_is_better and re.search(r"\b(most|highest)\b", q):
            order = "top"
        return Plan("agency_ranking", metric=metric or "engagement", wave=years[-1] if years else d.LATEST,
                    order=order, text=q)
    if metric:
        trend = re.search(r"trend|over time|since|changed?|history|histor|years|over the|getting|worse|better|"
                          r"improv|declin|ris(e|ing)|fall(ing)?|drop|grow", q)
        if len(years) >= 2 or trend:
            since = len(years) == 1 and re.search(rf"\b(since|from|after|starting)\s+(in\s+)?{years[0]}", q)
            return Plan("metric_trend", metric=metric, agency=agency,
                        wave_from=min(years) if len(years) >= 2 or since else None,
                        wave=max(years) if len(years) >= 2 or (years and not since) else None, text=q)
        return Plan("metric_value", metric=metric, agency=agency, wave=years[-1] if years else None, text=q)
    if re.search(r"\b(question|asked|ask|item|wording)\b", q) or len(d.search_questions(q)):
        return Plan("search_questions", text=q)
    return Plan("help", text=q)


# --- Optional local-model planner ---------------------------------------------------------------------

OLLAMA = "http://localhost:11434"


def local_model() -> str | None:
    """The first model a local Ollama server offers, or None. Free and on this machine; never a paid API."""
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=0.5) as r:
            models = [m["name"] for m in json.load(r).get("models", [])]
        return models[0] if models else None
    except OSError:
        return None


def plan_with_model(question: str, model: str, ask=None) -> Plan:
    """Ask a local model to choose a tool and its arguments; validate the choice, else use the rules."""
    metrics = {m.id: m.label for m in d.METRICS.values()}
    prompt = (
        "Choose ONE tool for this question about the US federal employee survey (FEVS). Reply with JSON only: "
        '{"tool": ..., "metric": ..., "wave": ..., "wave_from": ..., "agency": ..., "order": ...}.\n'
        f"tools: {list(TOOLS)}\nmetrics: {json.dumps(metrics)}\n"
        f"waves: 2012-{d.LATEST}. agency: a two-letter code or ALL. order: top or bottom.\n"
        f"question: {question}")
    ask = ask or _ollama
    try:
        raw = json.loads(ask(model, prompt))
    except (OSError, ValueError, TypeError):
        return plan_with_rules(question)
    rules = plan_with_rules(question)
    tool = raw.get("tool")
    if tool not in TOOLS:
        return rules
    metric = raw.get("metric") if raw.get("metric") in d.METRICS else None
    if tool in ("metric_value", "metric_trend", "agency_ranking") and not metric:
        return rules
    agency = raw.get("agency") or d.GOVERNMENTWIDE
    if agency != d.GOVERNMENTWIDE and agency not in set(d.agencies().agency_code):
        agency = rules.agency
    def year(v):
        return v if isinstance(v, int) and 2012 <= v <= d.LATEST else None
    # Years and agency the model left out are taken from the rule-based reading of the same question.
    wave = year(raw.get("wave")) or rules.wave or (d.LATEST if tool in ("agency_ranking", "paradox") else None)
    if agency == d.GOVERNMENTWIDE and rules.agency != d.GOVERNMENTWIDE:
        agency = rules.agency
    return Plan(tool, metric=metric, wave=wave,
                wave_from=year(raw.get("wave_from")) or rules.wave_from, agency=agency,
                order="bottom" if raw.get("order") == "bottom" else "top", text=question.lower(),
                planner=f"local model ({model})")


def _ollama(model: str, prompt: str) -> str:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json",
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["response"]


# --- Tools and answer templates ---------------------------------------------------------------------

def pct(v: float | None) -> str:
    return "suppressed" if v is None or pd.isna(v) else f"{v * 100:.1f}%"


def _where(agency: str) -> str:
    return "governmentwide" if agency == d.GOVERNMENTWIDE else f"at {d.agency_name(agency)}"


def _table_for(metric: str) -> str:
    kind = d.METRICS[metric].kind
    return {"index": "gold.gld_index_scores", "question": "gold.gld_question_results",
            "leave": "gold.gld_leave_intent"}[kind]


def _metric_value(p: Plan) -> Answer:
    m = d.METRICS[p.metric]
    s = d.series(p.metric, p.agency)
    latest_note = []
    if p.wave is None:
        # No year asked: the latest year this metric was published for this group.
        published = s.dropna(subset=["value"])
        p.wave = int(published.wave.max()) if len(published) else d.LATEST
        if p.wave != d.LATEST:
            latest_note = [f"{p.wave} is the latest year with a published value {_where(p.agency)}."]
    hit = s[s.wave == p.wave]
    if hit.empty:
        waves = ", ".join(str(w) for w in s.wave) or "no year"
        return Answer(f"{m.label} {_where(p.agency)} is not available for {p.wave}. It is available for: {waves}.",
                      citations=[Citation(_table_for(p.metric), f"{m.label}, {_where(p.agency)}")])
    r = hit.iloc[0]
    if r.suppressed or pd.isna(r.value):
        return Answer(f"{m.label} {_where(p.agency)} in {p.wave} is suppressed: fewer than "
                      f"{d.manifest()['min_cell_respondents']} people answered (OPM's Rule of Ten).",
                      citations=[Citation(_table_for(p.metric), f"{m.label}, {p.wave}, {_where(p.agency)}")])
    prev = s[s.wave == p.wave - 1]
    change = ""
    if not prev.empty and not pd.isna(prev.value.iloc[0]):
        delta = (r.value - prev.value.iloc[0]) * 100
        change = f", {'up' if delta > 0 else 'down'} {abs(delta):.1f} points from {p.wave - 1}" if abs(delta) >= 0.05 \
            else f", unchanged from {p.wave - 1}"
    what = m.blurb if m.kind == "leave" else f"That is the survey-weighted share who answered positively. {m.blurb}"
    text = f"**{m.label} {_where(p.agency)} in {p.wave}: {pct(r.value)}**{change}. {what}"
    if m.kind != "leave" and p.agency != d.GOVERNMENTWIDE:
        gw = d.value(p.metric, p.wave)
        if gw is not None:
            text += f" Governmentwide it was {pct(gw)}."
    caveats = latest_note + ([r.note] if r.note else [])
    n = "" if pd.isna(r.respondents) else f", {int(r.respondents):,} respondents"
    return Answer(text, [Citation(_table_for(p.metric), f"{m.label}, {p.wave}, {_where(p.agency)}{n}")],
                  caveats, chart=s, chart_kind="trend", plan=p)


def _metric_trend(p: Plan) -> Answer:
    m = d.METRICS[p.metric]
    s = d.series(p.metric, p.agency).dropna(subset=["value"])
    if p.wave_from:
        s = s[s.wave >= p.wave_from]
    if p.wave:
        s = s[s.wave <= p.wave]
    if s.empty:
        return Answer(f"No published values for {m.label} {_where(p.agency)} in that range.", plan=p)
    first, last = s.iloc[0], s.iloc[-1]
    hi, lo = s.loc[s.value.idxmax()], s.loc[s.value.idxmin()]
    delta = (last.value - first.value) * 100
    text = (f"**{m.label} {_where(p.agency)}: {pct(first.value)} in {int(first.wave)} → {pct(last.value)} in "
            f"{int(last.wave)}** ({'+' if delta >= 0 else '−'}{abs(delta):.1f} points). "
            f"Highest {pct(hi.value)} ({int(hi.wave)}), lowest {pct(lo.value)} ({int(lo.wave)}). {m.blurb}")
    caveats = [f"{int(r.wave)}: {r.note}" for _, r in s.iterrows() if r.note]
    if m.kind == "leave":
        caveats.append("2012 is excluded: its leave-intent codes cannot be matched to its answer options.")
    return Answer(text, [Citation(_table_for(p.metric), f"{m.label}, {int(first.wave)}-{int(last.wave)}, "
                                                          f"{_where(p.agency)}")],
                  caveats, chart=s, chart_kind="trend", plan=p)


def _agency_ranking(p: Plan) -> Answer:
    m = d.METRICS[p.metric]
    r = d.ranking(p.metric, p.wave)
    shown = r.dropna(subset=["value"])
    if shown.empty:
        return Answer(f"No agency results for {m.label} in {p.wave}.", plan=p)
    pick = shown.head(5) if p.order == "top" else shown.tail(5).iloc[::-1]
    word = ("highest" if p.order == "top" else "lowest") if m.higher_is_better else \
           ("highest" if p.order == "top" else "lowest")
    if not m.higher_is_better:
        pick = shown.sort_values("value", ascending=p.order != "top").head(5)
    lines = "\n".join(f"{i + 1}. {row.agency_name}: {pct(row.value)} ({int(row.respondents):,} respondents)"
                      if not pd.isna(row.respondents) else f"{i + 1}. {row.agency_name}: {pct(row.value)}"
                      for i, (_, row) in enumerate(pick.iterrows()))
    text = (f"**{m.label}, {p.wave}: the {word} of {len(shown)} agencies with published results** "
            f"(governmentwide {pct(r.governmentwide.iloc[0])}):\n\n{lines}")
    caveats = ["Small agencies have wider margins of error; a few points apart is not a meaningful difference."]
    hidden = int(r.suppressed.sum())
    if hidden:
        caveats.append(f"{hidden} agencies are suppressed (fewer than 10 respondents).")
    return Answer(text, [Citation(_table_for(p.metric), f"{m.label}, {p.wave}, by agency")], caveats,
                  chart=shown, chart_kind="ranking", plan=p)


def _paradox(p: Plan) -> Answer:
    sat, share = d.leaving_rate(p.wave, job_satisfied=True)
    unsat, _ = d.leaving_rate(p.wave, job_satisfied=False)
    best, _ = d.leaving_rate(p.wave, job_satisfied=True, trusts_supervisor=True, respects_senior_leaders=True,
                             workload_reasonable=True)
    worst, _ = d.leaving_rate(p.wave, job_satisfied=True, trusts_supervisor=False, respects_senior_leaders=False,
                              workload_reasonable=False)
    gaps = d.factor_gaps(p.wave)
    top = gaps.iloc[0]
    text = (f"**In {p.wave}, {pct(sat)} of people satisfied with their job still said they were considering "
            f"leaving** (vs {pct(unsat)} of those not satisfied). Satisfied people made up {pct(share)} of those "
            f"profiled. Among the satisfied, the rate was {pct(best)} when they also trusted their supervisor, "
            f"respected senior leaders and found their workload reasonable, and {pct(worst)} when none of the "
            f"three held. The largest single gap was for **{top.label.lower()}**: {pct(top.positive)} vs "
            f"{pct(top.not_positive)}.")
    return Answer(text, [Citation("gold.gld_workplace_paradox", f"{p.wave}, 16 respondent profiles")],
                  [CAUSAL_NOTE], plan=p)


def _search(p: Plan) -> Answer:
    hits = d.search_questions(p.text)
    if hits.empty:
        return _help(p)
    lines = []
    for _, h in hits.iterrows():
        s = d.question_series(h.question_id)
        last = s.dropna(subset=["pct_positive"]).tail(1)
        val = f": {pct(last.pct_positive.iloc[0])} positive in {int(last.wave.iloc[0])}" if len(last) else ""
        lines.append(f"- “{h.canonical_text}” (asked {h.n_waves}×, {h.first_wave}–{h.last_wave}){val}")
    return Answer("**Closest survey questions, governmentwide:**\n\n" + "\n".join(lines),
                  [Citation("gold.gld_question_results", "governmentwide, latest wave each question was asked")],
                  plan=p)


def _help(p: Plan) -> Answer:
    labels = ", ".join(m.label.lower() for m in d.METRICS.values())
    return Answer("I answer from the warehouse's validated gold tables only. Ask about a metric (" + labels +
                  ") for a year, a trend, an agency, or an agency ranking; about the Workplace Happiness Paradox; "
                  "or what employees were asked about a topic.", plan=p)


RUN = {"metric_value": _metric_value, "metric_trend": _metric_trend, "agency_ranking": _agency_ranking,
       "paradox": _paradox, "search_questions": _search, "help": _help}


def answer(question: str, model: str | None = None, ask=None) -> Answer:
    if INDIVIDUAL.search(question):
        return Answer("I can't answer about individual people. The warehouse publishes only survey-weighted "
                      "results for groups of at least 10 respondents, and no respondent-level data reaches this app.",
                      caveats=["Privacy: OPM's Rule of Ten applies to every published result."])
    plan = plan_with_model(question, model, ask) if model else plan_with_rules(question)
    result = RUN[plan.tool](plan)
    result.plan = plan
    if TURNOVER.search(question):
        result.caveats.insert(0, TURNOVER_NOTE)
    if CAUSAL.search(question) and CAUSAL_NOTE not in result.caveats:
        result.caveats.append(CAUSAL_NOTE)
    return result
