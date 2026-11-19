"""The app's look: type, color, cards and charts. Pages call these; no page writes its own CSS."""
from __future__ import annotations

import html

import altair as alt
import pandas as pd
import streamlit as st

INK = "#16213E"
MUTED = "#5B6478"
PAPER = "#F7F5F0"
CARD = "#FFFFFF"
LINE = "#E4E0D6"
POSITIVE = "#0F9D8A"
LEAVING = "#E0573A"
GOLD = "#E3A33B"
SLATE = "#8A93A6"
PALETTE = [INK, POSITIVE, LEAVING, GOLD, "#6C5CE7", "#2D9CDB", SLATE]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650&family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, p, li, label, input, textarea, button {{
  font-family: 'Inter', system-ui, sans-serif; }}
.stApp {{ background: {PAPER}; color: {INK}; }}
section[data-testid="stSidebar"] {{ background: {INK}; }}
section[data-testid="stSidebar"] * {{ color: #E9ECF5 !important; }}
section[data-testid="stSidebar"] a[aria-current="page"] {{ background: rgba(255,255,255,.10); border-radius: 8px; }}
.brand {{ font-family: 'Fraunces', Georgia, serif; font-size: 1.45rem; font-weight: 650; margin: 0 0 2px 0; }}
.brand-sub {{ font-size: .8rem; opacity: .75; margin-bottom: 14px; line-height: 1.4; }}
.block-container {{ padding-top: 3.6rem; max-width: 1220px; }}
h1, h2, h3 {{ font-family: 'Fraunces', Georgia, serif !important; color: {INK}; letter-spacing: -0.01em; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; font-weight: 600; color: {LEAVING}; }}
.hero h1 {{ font-size: 2.6rem; line-height: 1.08; margin: .25rem 0 .6rem 0; font-weight: 650; }}
.hero p {{ font-size: 1.06rem; color: {MUTED}; max-width: 760px; line-height: 1.55; }}
.kpi {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; padding: 16px 18px 8px 18px;
  margin-top: 10px; }}
.kpi .label {{ min-height: 2.3em; font-size: .74rem; font-weight: 600; color: {MUTED}; text-transform: uppercase; letter-spacing: .06em; }}
.kpi .value {{ white-space: nowrap; font-family: 'Fraunces', Georgia, serif; font-size: clamp(1.5rem, 2.4vw, 2.1rem); font-weight: 650; color: {INK};
  font-variant-numeric: tabular-nums; margin-top: 2px; }}
.kpi .delta {{ font-size: .82rem; font-weight: 600; }}
.kpi .delta.good {{ color: {POSITIVE}; }} .kpi .delta.bad {{ color: {LEAVING}; }} .kpi .delta.flat {{ color: {SLATE}; }}
.kpi .sub {{ font-size: .78rem; color: {MUTED}; margin-top: 4px; }}
.callout {{ background: {INK}; color: #F4F1EA; border-radius: 18px; padding: 24px 30px; display: flex; gap: 28px;
  align-items: center; margin: 6px 0 18px 0; }}
.callout .big {{ font-family: 'Fraunces', Georgia, serif; font-size: 4.2rem; font-weight: 650; color: {GOLD};
  line-height: 1; flex: none; }}
@media (max-width: 640px) {{ .callout {{ flex-direction: column; align-items: flex-start; gap: 10px; }} }}
.callout p {{ color: #DCE0EA; margin: .5rem 0 0 0; line-height: 1.5; }}
.note {{ font-size: .82rem; color: {MUTED}; border-left: 3px solid {GOLD}; padding: 4px 0 4px 12px; margin: 8px 0; }}
.pill {{ display: inline-block; font-size: .72rem; font-weight: 600; padding: 3px 10px; border-radius: 999px;
  background: #ECE8DE; color: {INK}; margin-right: 6px; }}
.cite {{ font-size: .78rem; color: {MUTED}; font-family: ui-monospace, 'SF Mono', monospace; }}
div[data-testid="stMetricValue"] {{ font-family: 'Fraunces', Georgia, serif; }}
</style>
"""


def setup() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    alt.theme.register("fevs", enable=True)(_altair_theme)


def _altair_theme() -> dict:
    return {"config": {
        "background": "transparent",
        "font": "Inter",
        "view": {"stroke": None},
        "axis": {"labelColor": MUTED, "titleColor": MUTED, "gridColor": "#ECE8DE", "domainColor": LINE,
                 "tickColor": LINE, "labelFontSize": 11, "titleFontSize": 11, "titleFontWeight": 500},
        "legend": {"labelColor": INK, "titleColor": MUTED, "labelFontSize": 12, "orient": "top"},
        "range": {"category": PALETTE},
        "title": {"font": "Fraunces", "color": INK, "fontSize": 16, "anchor": "start"},
    }}


def hero(eyebrow: str, title: str, text: str) -> None:
    st.markdown(f'<div class="hero"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{text}</p></div>',
                unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="note">{text}</div>', unsafe_allow_html=True)


def pct(v, digits: int = 1) -> str:
    return "—" if v is None or pd.isna(v) else f"{v * 100:.{digits}f}%"


def kpi(label: str, value: float | None, prev: float | None, prev_label: str, higher_is_better: bool,
        sub: str, spark: pd.DataFrame | None = None) -> None:
    if value is None or prev is None:
        delta_html = '<span class="delta flat">no comparison</span>'
    else:
        d = (value - prev) * 100
        good = (d > 0) == higher_is_better
        cls = "flat" if abs(d) < 0.05 else ("good" if good else "bad")
        arrow = "▲" if d > 0 else ("▼" if d < 0 else "■")
        delta_html = f'<span class="delta {cls}">{arrow} {abs(d):.1f} pts</span> <span class="sub">vs {prev_label}</span>'
    st.markdown(f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
                f'<div class="value">{pct(value)}</div>{delta_html}<div class="sub">{html.escape(sub)}</div></div>',
                unsafe_allow_html=True)
    if spark is not None and len(spark):
        color = POSITIVE if higher_is_better else LEAVING
        st.altair_chart(alt.Chart(spark).mark_area(line={"color": color, "strokeWidth": 2}, color=alt.Gradient(
            gradient="linear", stops=[alt.GradientStop(color=color, offset=0),
                                      alt.GradientStop(color="rgba(255,255,255,0)", offset=1)], x1=1, x2=1, y1=0, y2=1),
            opacity=0.25).encode(
            x=alt.X("wave:O", axis=None), y=alt.Y("value:Q", axis=None, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("wave:O", title="Year"), alt.Tooltip("value:Q", format=".1%", title=label)],
        ).properties(height=46), width="stretch")


def trend_chart(df: pd.DataFrame, color_field: str | None = None, height: int = 320, y_title: str = "Percent positive",
                breaks: pd.DataFrame | None = None) -> alt.Chart:
    """Lines over survey years; hollow points mark values not comparable with the rest of the line."""
    enc_color = alt.Color(f"{color_field}:N", title=None,
                          legend=alt.Legend(orient="bottom", columns=2, labelLimit=240, symbolType="circle")) \
        if color_field else alt.value(INK)
    base = alt.Chart(df).encode(x=alt.X("wave:O", title=None, axis=alt.Axis(labelAngle=0)),
                                y=alt.Y("value:Q", title=y_title, axis=alt.Axis(format="%"),
                                        scale=alt.Scale(zero=False)),
                                color=enc_color)
    tooltip = [alt.Tooltip("wave:O", title="Year"), alt.Tooltip("value:Q", format=".1%", title="Value")]
    if color_field:
        tooltip.insert(0, alt.Tooltip(f"{color_field}:N", title=""))
    if "note" in df:
        tooltip.append(alt.Tooltip("note:N", title="Note"))
    chart = base.mark_line(strokeWidth=2.5, interpolate="monotone") + base.mark_circle(size=55, opacity=1).encode(
        tooltip=tooltip)
    if breaks is not None and len(breaks):
        rules = alt.Chart(breaks).mark_rule(strokeDash=[4, 4], color=GOLD).encode(
            x="wave:O", tooltip=[alt.Tooltip("label:N", title="")])
        tags = alt.Chart(breaks).mark_text(align="left", dx=4, dy=2, baseline="top", color=GOLD, fontSize=10,
                                           fontWeight=600).encode(
            x="wave:O", y=alt.value(0), text=alt.Text("short:N") if "short" in breaks else alt.value(""))
        chart = chart + rules + tags
    return chart.properties(height=height)


def ranking_chart(df: pd.DataFrame, gw: float | None, higher_is_better: bool, label: str) -> alt.Chart:
    df = df.dropna(subset=["value"]).copy()
    df["vs"] = df.value.map(lambda v: "Above governmentwide" if gw is not None and v >= gw else "Below governmentwide")
    good, bad = (POSITIVE, LEAVING) if higher_is_better else (LEAVING, POSITIVE)
    order = df.agency_name.tolist()
    bars = alt.Chart(df).mark_circle(size=120, opacity=1).encode(
        y=alt.Y("agency_name:N", sort=order, title=None, axis=alt.Axis(labelLimit=330, labelOverlap=False)),
        x=alt.X("value:Q", title=label, axis=alt.Axis(format="%"), scale=alt.Scale(zero=False)),
        color=alt.Color("vs:N", scale=alt.Scale(domain=["Above governmentwide", "Below governmentwide"],
                                                range=[good, bad]), title=None),
        tooltip=[alt.Tooltip("agency_name:N", title="Agency"), alt.Tooltip("value:Q", format=".1%", title=label),
                 alt.Tooltip("respondents:Q", format=",", title="Respondents")])
    sticks = alt.Chart(df).mark_rule(color=LINE, strokeWidth=2).encode(
        y=alt.Y("agency_name:N", sort=order), x="value:Q", x2=alt.datum(gw if gw is not None else 0))
    layers = sticks + bars
    if gw is not None:
        layers += alt.Chart(pd.DataFrame({"gw": [gw]})).mark_rule(color=INK, strokeDash=[3, 3]).encode(
            x="gw:Q", tooltip=[alt.Tooltip("gw:Q", format=".1%", title="Governmentwide")])
    return layers.properties(height=max(260, 26 * len(df)))
