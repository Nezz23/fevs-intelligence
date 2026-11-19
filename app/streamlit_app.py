"""FEVS Intelligence: what makes people love, hate, or leave their jobs?

Every number is read through app.data from the gold-layer export (survey-weighted aggregates, groups of
10 or more). Run from the repository root:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from app import data as d, ui  # noqa: E402
from app.pages import agencies, ask, methodology, overview, paradox, trends  # noqa: E402

st.set_page_config(page_title="FEVS Intelligence", page_icon="◆", layout="wide")
ui.setup()

# --- Navigation --------------------------------------------------------------------------------------

pages = [st.Page(overview, title="Overview", icon=":material/insights:", url_path="overview", default=True),
         st.Page(paradox, title="Happiness Paradox", icon=":material/psychology:", url_path="paradox"),
         st.Page(trends, title="Trends", icon=":material/show_chart:", url_path="trends"),
         st.Page(agencies, title="Agencies", icon=":material/account_balance:", url_path="agencies"),
         st.Page(ask, title="Ask the data", icon=":material/forum:", url_path="ask"),
         st.Page(methodology, title="Methodology", icon=":material/fact_check:", url_path="methodology")]
nav = st.navigation(pages, position="hidden")
with st.sidebar:
    st.markdown('<div class="brand">◆ FEVS Intelligence</div><div class="brand-sub">People Analytics on 13 years '
                'of the Federal Employee Viewpoint Survey</div>', unsafe_allow_html=True)
    for page in pages:
        st.page_link(page)
    st.markdown(f'<div style="font-size:.74rem;opacity:.7;margin-top:22px;line-height:1.5">Source: OPM FEVS public '
                f'data files, 2012–2024.<br>Survey-weighted · groups of 10+ only.<br>'
                f'Gold export {d.manifest()["git_commit"]}</div>', unsafe_allow_html=True)
nav.run()
