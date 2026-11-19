"""The question crosswalk: one canonical question per wording and scale, and no silent merges."""
import csv
from pathlib import Path

import pytest

from survey_items.crosswalk import CrosswalkError, build

ITEMS = Path(__file__).resolve().parent.parent / "survey_items"
AGREE = {"1": "Strongly Disagree", "2": "Disagree", "3": "Neither", "4": "Agree", "5": "Strongly Agree",
         "X": "Do Not Know"}
FREQ = {"1": "3 or more days a week", "2": "2 or fewer days a week"}
SITUATION = {"1": "I telework", "2": "I do not telework"}


def item(wave, code, text, responses=AGREE):
    return {"wave": wave, "item_code": code, "item_text": text, "is_redacted": False, "responses": responses}


def question_of(crosswalk, wave, code):
    return next(r["question_id"] for r in crosswalk if (r["wave"], r["item_code"]) == (wave, code))


def published(name):
    with open(ITEMS / name, newline="") as f:
        return list(csv.DictReader(f))


def test_a_renumbered_item_with_the_same_wording_is_one_question():
    _, cw = build([item(2012, "Q69", "Satisfied with your job?"), item(2024, "Q70", "Satisfied with your job?")], {})
    assert question_of(cw, 2012, "Q69") == question_of(cw, 2024, "Q70")


def test_a_reused_code_with_new_wording_is_a_new_question():
    _, cw = build([item(2012, "Q5", "I like the kind of work I do."),
                   item(2020, "Q5", "My talents are used well in the workplace.")], {})
    assert question_of(cw, 2012, "Q5") != question_of(cw, 2020, "Q5")


def test_same_wording_with_different_answer_options_is_two_questions():
    _, cw = build([item(2021, "Q46", "Describe your teleworking schedule", FREQ),
                   item(2023, "Q91", "Describe your teleworking schedule", SITUATION)], {})
    assert question_of(cw, 2021, "Q46") != question_of(cw, 2023, "Q91")


def test_a_wave_without_answer_labels_inherits_the_next_waves_scale():
    _, cw = build([item(2012, "Q1", "I have enough information.", {}), item(2014, "Q1", "I have enough information.")], {})
    assert [r["scale_source"] for r in cw] == ["inherited", "codebook"]


def test_an_unreviewed_near_duplicate_wording_stops_the_build():
    with pytest.raises(CrosswalkError, match="unreviewed near-duplicate"):
        build([item(2012, "Q49", "My supervisor/team leader treats me with respect."),
               item(2014, "Q49", "My supervisor treats me with respect.")], {})


def test_a_reviewed_rewording_joins_the_trend_and_marks_a_break():
    a, b = "my supervisor team leader treats me with respect", "my supervisor treats me with respect"
    qs, cw = build([item(2012, "Q49", "My supervisor/team leader treats me with respect."),
                    item(2014, "Q49", "My supervisor treats me with respect.")],
                   {frozenset((a, b)): ("reworded", "OPM dropped team leader")})
    assert len(qs) == 1
    assert qs[0]["wording_breaks"] == "2014"
    assert [r["wording_status"] for r in cw] == ["first", "reworded"]


def test_a_decision_about_wording_that_no_wave_has_stops_the_build():
    with pytest.raises(CrosswalkError, match="not in any wave"):
        build([item(2012, "Q1", "Some question.")], {frozenset(("gone a", "gone b")): ("different", "x")})


def test_the_same_checkbox_option_under_two_questions_is_not_merged():
    box = {"1": "Alternative Work Schedules"}
    _, cw = build([item(2020, "Q59_01", "Alternative Work Schedules", box),
                   item(2020, "V21_04", "Alternative Work Schedules", box)], {})
    assert question_of(cw, 2020, "Q59_01") != question_of(cw, 2020, "V21_04")


def test_published_crosswalk_maps_every_item_wave_exactly_once():
    rows = published("question_crosswalk.csv")
    keys = [(r["wave"], r["item_code"]) for r in rows]
    assert len(rows) == 1070
    assert len(keys) == len(set(keys))
    assert all(r["question_id"] for r in rows if r["wording_status"] != "redacted")


def test_published_crosswalk_trends_job_satisfaction_across_all_13_waves():
    rows = published("question_crosswalk.csv")
    ids = {r["question_id"] for r in rows if (r["wave"], r["item_code"]) in {("2012", "Q69"), ("2024", "Q70")}}
    assert len(ids) == 1
    assert sum(r["question_id"] in ids for r in rows) == 13


def test_published_catalog_keeps_the_2022_security_split_out_of_the_old_trend():
    qs = {q["canonical_text"]: q for q in published("question_catalog.csv")}
    old = qs["My organization has prepared employees for potential security threats."]
    assert old["last_wave"] == "2019"
