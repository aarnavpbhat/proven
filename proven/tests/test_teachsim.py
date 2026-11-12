"""The simulated reviewer loop, and the rule that a lesson replaces its trigger's words."""
from proven import claims, learned, teachsim
from proven.extract import RuleExtractor
from proven.report import run
from proven.synth import generate


def test_lesson_trigger_words_are_not_searched_on_their_own():
    scenario = generate(0)
    entry = learned.make_entry(["board coverage"], ["d&o"])
    with learned.lexicon([entry]):
        terms = claims.anchored_terms("board coverage and the offsite", None, scenario.ledger)
    texts = {t.text: t.origin for t in terms}
    assert texts["d&o"] == "learned"
    assert "coverage" not in texts and "board" not in texts
    assert texts["offsite"] == "quote"          # words outside the trigger are still searched


def test_trigger_word_that_is_also_a_lesson_term_is_kept():
    scenario = generate(0)
    entry = learned.make_entry(["cyber cover"], ["cyber"])
    with learned.lexicon([entry]):
        terms = claims.anchored_terms("cyber cover", None, scenario.ledger)
    assert [t.text for t in terms] == ["cyber"]


def test_correct_lesson_does_not_pass_a_partial_explanation():
    """Seed 1355: "board coverage" explains about half the movement; cyber coverage the rest."""
    scenario = generate(1355, phrasing="heldout")
    label = next(l for l in scenario.labels if l.family == "partial")
    entry = learned.make_entry(["board coverage"], ["d&o", "liability"])
    with learned.lexicon([entry]):
        report = run(scenario.explanation, scenario.ledger, extractor=RuleExtractor())
    result = next(c for c in report["claims"] if c["claim"]["quote"] == label.quote)
    assert result["verdict"] != "PASS"


def test_simulated_lessons_raise_coverage_without_breaking_a_kill_criterion():
    result = teachsim.simulate(n=110, phrasing="heldout", steps=(0, 55))
    before, after = result["rows"]
    assert before["lessons"] == 0 and after["lessons"] > 0
    assert after["controls_passed"] > before["controls_passed"]
    for row in result["rows"]:
        assert row["unsafe_passes"] == 0 and row["control_fails"] == 0
    assert claims.LEARNED == []                 # nothing leaks out of the simulation
