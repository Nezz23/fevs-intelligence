"""The app: every page renders from the gold export, and what it shows matches the validated gold numbers."""
import pytest

from app import data as d

testing = pytest.importorskip("streamlit.testing.v1")


def run_page(name: str, **state):
    def script(page_name: str):
        from app import pages, ui
        ui.setup()
        getattr(pages, page_name)()
    at = testing.AppTest.from_function(script, args=(name,), default_timeout=60)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


@pytest.mark.parametrize("page", ["overview", "paradox", "trends", "agencies", "ask", "methodology"])
def test_every_page_renders_without_an_error(page):
    assert not run_page(page).exception


def test_overview_headline_is_the_2024_satisfied_but_leaving_share():
    page = " ".join(m.value for m in run_page("overview").markdown)
    assert "24%" in page  # 23.8% rounded, as the callout shows it


def test_the_engagement_card_shows_opms_published_2024_score():
    page = " ".join(m.value for m in run_page("overview").markdown)
    assert "73.0%" in page


def test_the_paradox_page_reports_the_satisfied_profile_rate():
    at = run_page("paradox")
    assert at.metric[0].value == "23.8%"


def test_methodology_page_shows_every_scored_opm_figure_matched():
    at = run_page("methodology")
    assert any(m.value == "67 of 67" for m in at.metric)


def test_asking_a_question_answers_from_gold_with_a_citation():
    at = run_page("ask")
    at.chat_input[0].set_value("What was employee engagement in 2024?").run()
    page = " ".join(m.value for m in at.markdown)
    assert "73.0%" in page
    assert "gold.gld_index_scores" in page
