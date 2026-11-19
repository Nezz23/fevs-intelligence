"""The assistant answers from gold only, cites it, and declines what the survey cannot answer."""
import json

from app import data as d
from app.assistant import CAUSAL_NOTE, TURNOVER_NOTE, answer


def test_a_metric_question_gets_the_gold_value_and_its_source():
    a = answer("What was employee engagement in 2024?")
    assert "73.0%" in a.text
    assert a.citations[0].table == "gold.gld_index_scores"


def test_a_since_question_returns_the_trend_from_that_year_to_the_latest():
    a = answer("How has trust in supervisors changed since 2014?")
    assert "in 2014 →" in a.text and "in 2024" in a.text
    assert "Trust in supervisor" in a.text


def test_an_agency_question_uses_that_agencys_latest_published_year():
    a = answer("How does the Department of Veterans Affairs score on engagement?")
    assert "Department of Veterans Affairs in 2017" in a.text


def test_a_ranking_lists_agencies_highest_first():
    a = answer("Which agencies have the highest job satisfaction in 2024?")
    ranked = d.ranking("job_satisfaction", 2024).dropna(subset=["value"])
    assert f"1. {ranked.agency_name.iloc[0]}" in a.text


def test_turnover_questions_are_answered_as_intention_with_the_distinction_stated():
    a = answer("What is the turnover rate governmentwide in 2024?")
    assert "36.8%" in a.text
    assert a.caveats[0] == TURNOVER_NOTE


def test_why_questions_carry_the_no_causation_note():
    assert CAUSAL_NOTE in answer("Why are satisfied employees leaving?").caveats


def test_questions_about_individuals_are_declined():
    a = answer("Who said they hate their boss?")
    assert "can't answer about individual people" in a.text
    assert not a.citations


def test_burnout_maps_to_the_workload_item_and_says_it_is_not_a_burnout_scale():
    a = answer("Is burnout getting worse?")
    assert "Workload is reasonable" in a.text
    assert "no burnout scale" in a.text


def test_a_local_model_plan_is_used_when_it_validates():
    plan = json.dumps({"tool": "metric_value", "metric": "pay_satisfaction", "wave": 2023, "agency": "ALL"})
    a = answer("how do people feel about money", model="fake", ask=lambda m, p: plan)
    assert a.plan.planner == "local model (fake)"
    assert "Pay satisfaction governmentwide in 2023" in a.text


def test_an_invalid_local_model_plan_falls_back_to_the_rules():
    a = answer("What was employee engagement in 2024?", model="fake",
               ask=lambda m, p: json.dumps({"tool": "drop_table", "metric": "engagement"}))
    assert a.plan.planner == "rules"
    assert "73.0%" in a.text


def test_a_local_model_cannot_invent_a_metric():
    a = answer("What was employee engagement in 2024?", model="fake",
               ask=lambda m, p: json.dumps({"tool": "metric_value", "metric": "happiness_score_9000"}))
    assert a.plan.planner == "rules"


def test_years_the_local_model_omits_come_from_the_question():
    plan = json.dumps({"tool": "metric_trend", "metric": "engagement", "agency": "HS"})
    a = answer("How has engagement at Homeland Security changed since 2015?", model="fake", ask=lambda m, p: plan)
    assert "in 2015 →" in a.text
