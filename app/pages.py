"""The app's six pages. Every number is read through app.data from the gold-layer export."""
import altair as alt
import pandas as pd
import streamlit as st

from app import assistant, data as d, ui

YEARS = list(range(2012, d.LATEST + 1))


# --- Overview ----------------------------------------------------------------------------------------

def overview() -> None:
    sat, _ = d.leaving_rate(d.LATEST, job_satisfied=True)
    ui.hero("Federal Employee Viewpoint Survey · 2012–2024",
            "What makes people love, hate, or leave their jobs?",
            f"{d.manifest()['respondents']:,} survey responses from U.S. federal employees across 13 years, "
            "weighted to represent the workforce. Every figure reconciles with OPM's own published results.")
    st.markdown(f'<div class="callout"><div class="big">{ui.pct(sat, 0)}</div><div><div class="eyebrow" '
                f'style="color:#F2C17A">The Workplace Happiness Paradox · {d.LATEST}</div><p>of employees who are '
                f'<b>satisfied with their job</b> still say they are considering leaving their organization within '
                f'a year. What separates them from the satisfied who stay?</p></div></div>', unsafe_allow_html=True)
    gaps = d.factor_gaps(d.LATEST)
    st.markdown("##### Among satisfied employees: share considering leaving, by their other answers")
    g = gaps.melt(id_vars=["label"], value_vars=["positive", "not_positive"], var_name="answer", value_name="rate")
    g["answer"] = g.answer.map({"positive": "Yes", "not_positive": "No"})
    st.altair_chart(alt.Chart(g).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("label:N", title=None, sort=gaps.label.tolist(), axis=alt.Axis(labelLimit=220, labelFontSize=12)),
        yOffset=alt.YOffset("answer:N", sort=["Yes", "No"]),
        x=alt.X("rate:Q", title=None, axis=alt.Axis(format="%", tickCount=5)),
        color=alt.Color("answer:N", scale=alt.Scale(domain=["Yes", "No"], range=[ui.POSITIVE, ui.LEAVING]),
                        title=None),
        tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip("answer:N", title="Answer"),
                 alt.Tooltip("rate:Q", format=".1%", title="Considering leaving")],
    ).properties(height=210), width="stretch")

    st.markdown(f"### The pulse of the federal workforce, {d.LATEST}")
    cards = ["engagement", "job_satisfaction", "supervisor_trust", "senior_leader_respect", "workload",
             "considering_leaving"]
    cols = st.columns(3, gap="small") + st.columns(3, gap="small")
    for col, mid in zip(cols, cards):
        m = d.METRICS[mid]
        s = d.series(mid).dropna(subset=["value"])
        with col:
            ui.kpi(m.label, d.value(mid, d.LATEST), d.value(mid, d.LATEST - 1), str(d.LATEST - 1),
                   m.higher_is_better, f"{int(s.wave.min())}–{int(s.wave.max())} trend", s[["wave", "value"]])
    ui.note("Percent positive = survey-weighted share answering 4 or 5 on a five-point scale, with "
            "“Do not know” left out (OPM's method). “Considering leaving” is a stated intention, not turnover.")

    st.markdown("### Thirteen years in one view")
    picks = ["engagement", "job_satisfaction", "leaders_lead", "supervisor_trust", "workload", "considering_leaving"]
    long = pd.concat([d.series(m).assign(metric=d.METRICS[m].label) for m in picks]).dropna(subset=["value"])
    events = pd.DataFrame({"wave": [2013, 2020], "short": ["Furloughs", "COVID-19"],
                           "label": ["2013: sequestration furloughs", "2020: COVID-19 pandemic"]})
    st.altair_chart(ui.trend_chart(long, "metric", height=360, y_title="Share", breaks=events),
                    width="stretch")
    ui.note("Dashed lines mark context years, not explanations: the survey cannot say what caused a change.")


# --- Paradox -----------------------------------------------------------------------------------------

def paradox() -> None:
    ui.hero("Signature analysis", "The Workplace Happiness Paradox",
            "Being satisfied with your job does not mean you plan to stay. Each employee is placed in one of 16 "
            "profiles from four answers: job satisfaction, trust in their supervisor, respect for senior leaders, "
            "and whether their workload is reasonable. Then we ask how many in each profile are considering leaving.")
    wave = st.select_slider("Survey year", options=[w for w in YEARS if w >= 2013], value=d.LATEST,
                            help="2012 is excluded: its leave-intent codes cannot be matched to answer options.")
    st.markdown("#### Build a profile")
    short = {"job_satisfied": "Satisfied with job", "trusts_supervisor": "Trusts supervisor",
             "respects_senior_leaders": "Respects senior leaders", "workload_reasonable": "Workload reasonable"}
    choice = {}
    grid = st.columns(2) + st.columns(2)
    for col, k in zip(grid, d.FACTORS):
        with col:
            v = st.segmented_control(short[k], ["Yes", "No", "Any"], default="Yes" if k == "job_satisfied" else "Any",
                                     key=f"p_{k}")
            if v in ("Yes", "No"):
                choice[k] = v == "Yes"
    rate, share = d.leaving_rate(wave, **choice)
    overall, _ = d.leaving_rate(wave)
    a, b, cc = st.columns(3)
    a.metric("Leaving rate", ui.pct(rate),
             None if rate is None or overall is None else f"{(rate - overall) * 100:+.1f} pts",
             delta_color="inverse", help="Weighted share of people in this profile considering leaving, "
                                         "compared with everyone profiled.")
    b.metric("Workforce share", ui.pct(share), help="Weighted share of profiled employees in this profile.")
    cc.metric("All profiled", ui.pct(overall))

    st.markdown("#### All 16 profiles, ranked by intention to leave")
    p = d.paradox(wave).dropna(subset=["pct_considering_leaving"]).copy()
    p["profile"] = p.apply(lambda r: "".join("1" if r[k] else "0" for k in d.FACTORS), axis=1)
    p["selected"] = True
    for k, v in choice.items():
        p["selected"] &= p[k] == v
    order = p.sort_values("pct_considering_leaving").profile.tolist()
    y = alt.Y("profile:N", sort=order, axis=None)
    p["job"] = p.job_satisfied.map({True: "Satisfied with job", False: "Not satisfied with job"})
    fade = alt.condition("datum.selected", alt.value(1), alt.value(0.25))
    bars = alt.Chart(p).mark_bar(cornerRadiusEnd=4, height=18).encode(
        y=y,
        x=alt.X("pct_considering_leaving:Q", title=None,
                axis=alt.Axis(format="%", orient="top", values=[0, 0.2, 0.4, 0.6, 0.8]),
                scale=alt.Scale(domain=[-0.5, 0.9], nice=False)),
        color=alt.Color("job:N", scale=alt.Scale(domain=["Satisfied with job", "Not satisfied with job"],
                                                 range=[ui.POSITIVE, ui.LEAVING]), title=None,
                        legend=alt.Legend(orient="bottom")),
        opacity=fade,
        tooltip=[alt.Tooltip("job:N", title=""),
                 alt.Tooltip("pct_considering_leaving:Q", format=".1%", title="Considering leaving"),
                 alt.Tooltip("share_of_workforce:Q", format=".1%", title="Share of workforce"),
                 alt.Tooltip("respondents:Q", format=",", title="Respondents")])
    layers = [bars, bars.mark_text(align="left", dx=4, fontSize=11).encode(
        text=alt.Text("pct_considering_leaving:Q", format=".0%"), color=alt.value(ui.INK))]
    # The profile itself, drawn as a dot matrix in the left margin: one column per question.
    heads = {"job_satisfied": "Job", "trusts_supervisor": "Sup", "respects_senior_leaders": "Lead",
             "workload_reasonable": "Load"}
    for i, (k, head) in enumerate(heads.items()):
        at = -0.44 + 0.1 * i  # the dot columns sit left of zero on the same axis
        layers.append(alt.Chart(p).mark_text(fontSize=15).encode(
            y=y, x=alt.datum(at), text=alt.condition(f"datum.{k}", alt.value("●"), alt.value("○")),
            color=alt.condition(f"datum.{k}", alt.value(ui.INK), alt.value(ui.SLATE)), opacity=fade))
        layers.append(alt.Chart(pd.DataFrame({"t": [head]})).mark_text(fontSize=10, fontWeight=600,
                                                                       color=ui.MUTED).encode(
            x=alt.datum(at), y=alt.value(-6), text="t:N"))
    st.altair_chart(alt.layer(*layers).properties(height=440), width="stretch")
    ui.note("Columns: Job = satisfied with job · Sup = trusts supervisor · Lead = respects senior leaders · "
            "Load = workload reasonable. ● = answered 4 or 5 · ○ = did not. Highlighted rows match your profile.")

    st.markdown("#### The paradox over time")
    t = d.satisfied_but_leaving().melt(id_vars="wave", value_vars=["satisfied", "not_satisfied"],
                                       var_name="group", value_name="value")
    t["group"] = t.group.map({"satisfied": "Satisfied with job", "not_satisfied": "Not satisfied with job"})
    st.altair_chart(ui.trend_chart(t, "group", height=280, y_title="Considering leaving").encode(
        color=alt.Color("group:N", scale=alt.Scale(domain=["Satisfied with job", "Not satisfied with job"],
                                                   range=[ui.POSITIVE, ui.LEAVING]), title=None)),
        width="stretch")
    with st.expander("How to read this, and what it does not say"):
        st.markdown(
            "- Each profile's rate is a **survey-weighted** share of the people in it, using OPM's weight (POSTWT).\n"
            "- Only people who answered all four questions and gave a decodable leave answer are profiled.\n"
            "- **Associations, not causes.** People who trust their supervisor differ in many other ways too.\n"
            "- **Intention, not turnover.** The survey asks whether people are *considering* leaving.\n"
            "- The four questions were asked with the same wording in every year from 2013 to 2024.")
        st.dataframe(d.table("paradox_questions")[["feature", "item_code_2024", "why"]], hide_index=True,
                     width="stretch")


# --- Trends ------------------------------------------------------------------------------------------

def trends() -> None:
    ui.hero("Historical trends", "Thirteen survey years, compared fairly",
            "Questions are linked across years by wording, not by number. Where OPM changed a question's wording, "
            "the year is marked so a change in words is not mistaken for a change in people.")
    tab1, tab2 = st.tabs(["Headline metrics", "Any survey question"])
    with tab1:
        labels = {m.label: m.id for m in d.METRICS.values()}
        picked = st.multiselect("Metrics", list(labels), default=["Employee engagement", "Global satisfaction",
                                                                  "Leaders Lead", "Supervisors"])
        agency = _agency_picker("trend_agency")
        if picked:
            frames = [d.series(labels[p], agency).assign(metric=p) for p in picked]
            long = pd.concat(frames).dropna(subset=["value"])
            if long.empty:
                st.info("No published values for this choice.")
            else:
                st.altair_chart(ui.trend_chart(long, "metric", height=380), width="stretch")
                notes = long[long.note != ""]
                if len(notes):
                    ui.note("Not directly comparable: " + "; ".join(
                        f"{r.metric} {int(r.wave)} ({r.note})" for _, r in notes.iterrows()))
            with st.expander("What each metric measures"):
                for p in picked:
                    st.markdown(f"**{p}.** {d.METRICS[labels[p]].blurb}")
    with tab2:
        q = d.rated_questions().sort_values("canonical_text")
        query = st.text_input("Search the questions", placeholder="e.g. telework, innovation, recognition, pay")
        if query:
            hits = d.search_questions(query, limit=30)
            q = q[q.question_id.isin(hits.question_id)] if len(hits) else q.head(0)
        if q.empty:
            st.info("No rated question matches that search.")
            return
        options = {f"{r.canonical_text}  ({r.first_wave}–{r.last_wave})": r.question_id for _, r in q.iterrows()}
        label = st.selectbox(f"{len(options)} questions", list(options))
        qid = options[label]
        agency = _agency_picker("q_agency")
        s = d.question_series(qid, agency)
        meta = d.table("questions").set_index("question_id").loc[qid]
        s = s.assign(value=s.pct_positive, note=s.wording_status.map(
            lambda w: "wording changed this year" if w == "reworded" else ""))
        breaks = s[s.wording_status == "reworded"][["wave"]].assign(label="Wording changed")
        shown = s.dropna(subset=["value"])
        if shown.empty:
            st.info("Every result for this choice is suppressed (fewer than 10 respondents) or not asked.")
        else:
            st.altair_chart(ui.trend_chart(shown, height=300, breaks=breaks), width="stretch")
        st.markdown(f'<span class="pill">{meta.scale_type} scale</span><span class="pill">asked in '
                    f'{meta.n_waves} of 13 years</span>', unsafe_allow_html=True)
        wording = d.table("crosswalk")
        wording = wording[wording.question_id == qid][["wave", "item_code", "item_text", "wording_status"]]
        with st.expander("Exact wording and item number each year"):
            st.dataframe(wording, hide_index=True, width="stretch")


def _agency_picker(key: str) -> str:
    a = d.agencies()
    names = ["Governmentwide"] + a.agency_name.tolist()
    pick = st.selectbox("Organization", names, key=key)
    return d.GOVERNMENTWIDE if pick == "Governmentwide" else a[a.agency_name == pick].agency_code.iloc[0]


# --- Agencies ----------------------------------------------------------------------------------------

def agencies() -> None:
    ui.hero("Agency comparisons", "How agencies compare",
            "Every agency's results are survey-weighted. Agencies with fewer than 10 respondents for a result are "
            "suppressed, and OPM itself masks the smallest agencies in the public file.")
    labels = {m.label: m.id for m in d.METRICS.values()}
    c1, c2 = st.columns([2, 1])
    metric = labels[c1.selectbox("Metric", list(labels), index=list(labels).index("Employee engagement"))]
    wave = c2.selectbox("Year", YEARS[::-1])
    m = d.METRICS[metric]
    r = d.ranking(metric, wave)
    if r.empty or r.value.isna().all():
        st.info(f"No agency results for {m.label} in {wave}.")
        return
    gw = r.governmentwide.iloc[0]
    shown = r.dropna(subset=["value"])
    a, b, c = st.columns(3)
    a.metric("Governmentwide", ui.pct(gw))
    b.metric("Agencies with results", f"{len(shown)}")
    spread = (shown.value.max() - shown.value.min()) * 100
    c.metric("Gap, top to bottom", f"{spread:.1f} pts")
    st.altair_chart(ui.ranking_chart(shown, gw, m.higher_is_better, m.label), width="stretch")
    ui.note(f"{m.blurb} Small agencies have wider margins of error; differences of a few points are not meaningful.")

    st.markdown("### One agency against the government")
    a2 = d.agencies()
    pick = st.selectbox("Agency", a2.agency_name.tolist(),
                        index=a2.agency_name.tolist().index("Department of Veterans Affairs")
                        if "Department of Veterans Affairs" in a2.agency_name.tolist() else 0)
    code = a2[a2.agency_name == pick].agency_code.iloc[0]
    cols = st.columns(3)
    for col, mid in zip(cols, ["engagement", "job_satisfaction", "considering_leaving"]):
        both = pd.concat([d.series(mid, code).assign(who=pick), d.series(mid).assign(who="Governmentwide")])
        both = both.dropna(subset=["value"])
        with col:
            st.markdown(f"**{d.METRICS[mid].label}**")
            if both[both.who == pick].empty:
                st.caption("No published values.")
                continue
            st.altair_chart(ui.trend_chart(both, "who", height=220, y_title="").encode(
                color=alt.Color("who:N", scale=alt.Scale(domain=[pick, "Governmentwide"],
                                                         range=[ui.LEAVING, ui.SLATE]), title=None,
                                legend=alt.Legend(orient="bottom", columns=1, labelLimit=260))), width="stretch")
    present = a2[a2.agency_code == code].iloc[0]
    ui.note(f"{pick} appears in {present.n_waves} of 13 public files ({present.first_wave}–{present.last_wave}). "
            "Agencies are absent in years they did not take part or were masked by OPM.")


# --- Assistant ---------------------------------------------------------------------------------------

EXAMPLES = ["What share of satisfied employees are considering leaving?",
            "How has trust in supervisors changed since 2014?",
            "Which agencies have the highest engagement in 2024?",
            "Is burnout getting worse?",
            "What is the turnover rate at NASA?",
            "What did employees say about telework?"]


def ask() -> None:
    ui.hero("AI analytics assistant", "Ask the data",
            "Answers come only from the validated gold tables, with the table and filters cited. A planner picks "
            "which metric to look up; templates write the numbers, so no model can invent one.")
    model = assistant.local_model()
    use_model = False
    if model:
        use_model = st.toggle(f"Plan with the local model ({model} via Ollama)", value=False,
                              help="Runs on this machine, free. Its plan is validated; numbers still come from gold.")
    st.markdown(f'<span class="pill">Planner: {"local model · " + model if use_model else "rule-based"}</span>'
                '<span class="pill">Source: gold layer only</span><span class="pill">Groups of 10+ only</span>',
                unsafe_allow_html=True)
    if "chat" not in st.session_state:
        st.session_state.chat = []
    cols = st.columns(3)
    clicked = None
    for i, ex in enumerate(EXAMPLES):
        if cols[i % 3].button(ex, key=f"ex{i}", width="stretch"):
            clicked = ex
    question = st.chat_input("Ask about engagement, satisfaction, leadership, workload or intention to leave…")
    question = question or clicked
    if question:
        st.session_state.chat.append((question, assistant.answer(question, model if use_model else None)))
    for q, a in st.session_state.chat[-6:]:
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant", avatar=":material/insights:"):
            st.markdown(a.text)
            if a.chart is not None and a.chart_kind == "trend" and len(a.chart.dropna(subset=["value"])) > 1:
                st.altair_chart(ui.trend_chart(a.chart.dropna(subset=["value"]), height=200, y_title=""),
                                width="stretch")
            for cav in a.caveats:
                ui.note(cav)
            if a.citations:
                st.markdown("".join(f'<div class="cite">source · {c.table} · {c.detail}</div>' for c in a.citations),
                            unsafe_allow_html=True)
            if a.plan:
                st.caption(f"Plan: {a.plan.tool}({', '.join(f'{k}={v}' for k, v in [('metric', a.plan.metric), ('wave', a.plan.wave), ('from', a.plan.wave_from), ('agency', a.plan.agency)] if v)}) · {a.plan.planner}")


# --- Methodology -------------------------------------------------------------------------------------

def methodology() -> None:
    ui.hero("Methodology & data quality", "How every number is made, and what it cannot tell you",
            "The warehouse turns 13 differently shaped public files into one consistent set of metrics. These are "
            "the rules it follows and the checks that hold it to them.")
    man = d.manifest()
    rec = d.table("reconciliation")
    a, b, c, e = st.columns(4)
    a.metric("Survey responses", f"{man['respondents']:,}")
    b.metric("Item answers", f"{man['item_answers'] / 1e6:,.0f} M")
    c.metric("Questions linked across years", f"{len(d.table('questions'))}")
    e.metric("OPM figures matched", f"{(rec.status == 'match').sum()} of {(rec.status != 'not_scored').sum()}")

    t1, t2, t3, t4, t5 = st.tabs(["Reconciliation with OPM", "Survey method", "Question mapping",
                                  "Data quality traps", "Limitations"])
    with t1:
        st.markdown("Every governmentwide figure in OPM's *2024 Governmentwide Management Report*, beside ours. "
                    "A match means ours rounds to OPM's whole percent. A dbt test fails the build on any mismatch.")
        view = rec.assign(ours=rec.our_pct_positive.round(2), note=rec.note.fillna(""))[
            ["wave", "measure_type", "measure", "published_pct_positive", "ours", "status", "note"]]
        st.dataframe(view.sort_values(["measure_type", "measure", "wave"]), hide_index=True, width="stretch",
                     column_config={"published_pct_positive": st.column_config.NumberColumn("OPM published %"),
                                    "ours": st.column_config.NumberColumn("Ours %", format="%.2f")})
    with t2:
        st.markdown(
            "- **Source.** OPM's public release data files, 2012–2024: one row per respondent, answers coded 1–5.\n"
            "- **Weighting.** Every share uses POSTWT, OPM's post-stratification weight, so results represent the "
            "federal workforce rather than only the people who answered.\n"
            "- **Percent positive.** The weighted share answering 4 or 5. “Do not know / No basis to judge” is an "
            "answer but not a rating, so it is left out of the denominator, as OPM does.\n"
            "- **Indices.** OPM's 2024 definitions, scored as OPM scores them: the mean of each item's unrounded "
            "percent positive. A year gets an index score only if it asked every item.\n"
            "- **Privacy.** OPM's Rule of Ten: any group with fewer than 10 respondents is suppressed. Respondent IDs "
            "never leave the raw layer, and this app reads only aggregates.\n"
            "- **Intention to leave.** “Are you considering leaving your organization within the next year?” It is "
            "a stated intention, not observed turnover.")
    with t3:
        q = d.table("questions")
        cw = d.table("crosswalk")
        st.markdown(f"OPM renumbers and rewords questions between years. {len(cw):,} question-year pairs map to "
                    f"{len(q)} questions by **wording and answer scale**, never by item number. Each near-identical "
                    "wording has a reviewed decision below; the build stops on any wording nobody has reviewed.")
        st.dataframe(d.table("wording_decisions"), hide_index=True, width="stretch")
    with t4:
        st.markdown(
            "- **Leave-intent codes swapped meaning in 2020.** Through 2019, B = another federal job and D = other; "
            "from 2020, B = other and D = a job outside government. Codes are decoded per year.\n"
            "- **2012's leave codes cannot be decoded.** Its codebook lists five options for a four-code column, so "
            "2012 is left out of every leave-intent result.\n"
            "- **Same words, different answers.** The 2021 and 2023 telework questions share wording but not answer "
            "options, so they are kept apart.\n"
            "- **Questions that split.** One security item became separate cyber and physical items in 2022; neither "
            "continues the old trend.\n"
            "- **Contracts.** Each year's file is checked against a versioned contract (columns, answer codes, row "
            "count, checksum) before it loads.")
        st.dataframe(d.table("leave_codes")[["wave", "source_column", "code", "leave_intent", "verified"]],
                     hide_index=True, width="stretch", height=260)
    with t5:
        st.markdown(
            "- **Observational data.** Differences between groups are associations, not causes.\n"
            "- **Public file.** OPM collapses some demographics and masks small units, so agency counts are lower than "
            "in OPM's internal reports.\n"
            "- **Wording changes.** Marked years are kept in trends but should be read with care.\n"
            "- **No burnout scale.** FEVS has no validated burnout measure; “My workload is reasonable” is the closest "
            "direct item, and it is labeled as such.\n"
            "- **2020 COVID block.** Its items print without their stems, so OPM's 2020 Performance Confidence figures "
            "are not reproduced here.")
    st.caption(f"Data exported {man['exported_at']} from warehouse commit {man['git_commit']}.")


