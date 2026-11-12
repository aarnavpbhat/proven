"""Reviewer-taught lexicon entries: validation, the showcase round trip, removal, replay."""
import http.client
import json
import threading

import pytest

from proven import claims, learned, showcase
from proven.__main__ import main
from proven.evaluate import evaluate
from proven.server import App, BadRequest, create_server

TRAVEL = "Travel fell $12K, reflecting fewer customer visits."


def travel(report: dict) -> dict:
    return next(c for c in report["claims"] if c["claim"]["quote"] == TRAVEL)


def verify_showcase(app: App) -> dict:
    return app.verify({"scenario_id": "showcase", "explanation": showcase.EXPLANATION})


def teach(app: App, terms, *, action="fix_evidence", confirm_pass=False,
          triggers=("fewer customer visits",)):
    return app.record({
        "run_id": "r1", "claim_id": "C7", "quote": TRAVEL, "verdict": "REVIEW", "action": action,
        "note": "Customer visits show up as flights and hotels; they rose.",
        "explanation": showcase.EXPLANATION, "scenario_id": "showcase",
        "learn": {"triggers": list(triggers), "terms": list(terms), "confirm_pass": confirm_pass}})


# ── validation ──

@pytest.mark.parametrize("triggers, terms, why", [
    (["fewer customer visits"], ["ab"], "shorter than 3"),
    (["fewer customer visits"], ["expense"], "common word"),
    (["fewer customer visits"], ["the", "flights"], "common word"),
    ([], ["flights"], "at least one trigger"),
    (["  "], ["flights"], "at least one trigger"),
    (["fewer customer visits"], [], "at least one ledger word"),
    (["to"], ["flights"], "shorter than 3"),
    (["the"], ["flights"], "common words"),
    (["fewer customer visits"], ["fl.*ts"], "not a plain word"),
    (["fewer customer visits"], ["(flights|hotel)"], "not a plain word"),
    (["fewer customer visits"], ["x" * 61], "longer than"),
    ("flights", ["flights"], "must be a list"),
    (["fewer customer visits"], [5], "must be text"),
    ([f"visit{i}s" for i in range(9)], ["flights"], "at most"),
])
def test_unsafe_lessons_are_refused_with_a_reason(triggers, terms, why):
    with pytest.raises(learned.LessonRefused, match=why):
        learned.validate(triggers, terms)


def test_a_good_lesson_is_normalised():
    assert learned.validate(["  Fewer   Customer Visits "], ["Flights", "flights", "Hotel"]) == (
        ("fewer customer visits",), ("flights", "hotel"))


def test_nothing_is_loaded_implicitly(tmp_path):
    learned.append(tmp_path, learned.make_entry(["fewer customer visits"], ["flights"]))
    assert claims.LEARNED == []
    learned.apply(tmp_path)
    assert len(claims.LEARNED) == 1


def test_a_corrupt_or_unsafe_stored_line_is_skipped(tmp_path):
    (tmp_path / "lexicon.jsonl").write_text(
        'not json\n{"id": "x", "triggers": ["customer visit"], "terms": ["a"]}\n')
    assert learned.load(tmp_path) == []


# ── the showcase round trip ──

def test_teaching_the_right_words_decides_the_travel_claim_and_removal_restores_it(tmp_path):
    app = App(tmp_path)
    before = travel(verify_showcase(app))
    assert before["verdict"] == "REVIEW"
    assert [f["code"] for f in before["findings"]] == ["REASON_NOT_FOUND"]

    saved = teach(app, ["flights", "hotel"])
    assert (saved["verdict_before"], saved["verdict_after"]) == ("REVIEW", "FAIL")
    lesson = saved["lesson"]
    assert lesson["provenance"]["quote"] == TRAVEL and "flights" in lesson["provenance"]["note"]
    assert app.config()["learned"]["active"] == 1

    report = verify_showcase(app)
    after = travel(report)
    assert after["verdict"] == "FAIL"
    assert [f["code"] for f in after["findings"]] == ["WRONG_CAUSE"]
    assert {t["text"] for t in after["claim"]["terms"] if t["origin"] == "learned"} == {"flights", "hotel"}
    # Right given the ledger: flights and hotels *rose* ($7,300 -> $7,350) while Travel fell by
    # $12,000; the fall is September's $12,400 offsite not recurring. The sentence's reason is wrong.
    driver = after["reconstruction"]["driver"]
    assert driver["change"] == 50 and abs(driver["share"]) < 0.01
    # Only that claim moved.
    assert report["coverage"]["verdicts"] == {"PASS": 4, "FAIL": 4, "REVIEW": 1}

    app.forget(lesson["id"])
    assert app.config()["learned"]["active"] == 0 and learned.load(tmp_path) == []
    assert travel(verify_showcase(app))["verdict"] == "REVIEW"
    with pytest.raises(BadRequest, match="no learned entry"):
        app.forget(lesson["id"])


def test_a_lesson_that_would_make_a_pass_needs_explicit_confirmation(tmp_path):
    app = App(tmp_path)
    # Offsite does explain the $12K fall, but not "customer visits": a careless lesson would
    # turn a REVIEW into a PASS for the wrong reason.
    with pytest.raises(BadRequest, match="confirm_pass"):
        teach(app, ["offsite"])
    assert learned.load(tmp_path) == [] and not (tmp_path / "resolutions.jsonl").exists()
    saved = teach(app, ["offsite"], confirm_pass=True)
    assert saved["verdict_after"] == "PASS"


def test_only_teaching_actions_may_carry_a_lesson(tmp_path):
    app = App(tmp_path)
    for action in ("confirm_defect", "out_of_scope", "insufficient_evidence"):
        with pytest.raises(BadRequest, match="only Wrong evidence"):
            teach(app, ["flights"], action=action)
    assert learned.load(tmp_path) == []


def test_a_refused_lesson_records_nothing(tmp_path):
    app = App(tmp_path)
    with pytest.raises(BadRequest, match="will not learn"):
        teach(app, ["expense"])
    assert not (tmp_path / "resolutions.jsonl").exists() and not (tmp_path / "lexicon.jsonl").exists()


def test_the_same_lesson_is_not_learned_twice(tmp_path):
    app = App(tmp_path)
    teach(app, ["flights", "hotel"])
    with pytest.raises(BadRequest, match="already learned"):
        teach(app, ["hotel", "flights"])


# ── replay ──

def test_replay_passes_then_fails_when_a_lesson_is_removed(tmp_path, capsys):
    app = App(tmp_path)
    saved = teach(app, ["flights", "hotel"])
    case = saved["resolution"]["case"]
    assert case["scenario_id"] == "showcase" and case["verdict_after"] == "FAIL" \
        and case["verdict_before"] == "REVIEW" and case["quote"] == TRAVEL

    assert [r["ok"] for r in learned.replay(tmp_path)] == [True]
    assert main(["replay", "--data-dir", str(tmp_path)]) == 0

    learned.remove(tmp_path, saved["lesson"]["id"])
    results = learned.replay(tmp_path)
    assert [(r["ok"], r["actual"], r["lesson_active"]) for r in results] == [(False, "REVIEW", False)]
    assert main(["replay", "--data-dir", str(tmp_path)]) == 1
    assert "CHANGED" in capsys.readouterr().out


def test_replay_of_an_empty_directory_passes(tmp_path):
    assert main(["replay", "--data-dir", str(tmp_path)]) == 0


# ── the benchmark never sees lessons ──

def test_benchmark_numbers_are_identical_with_a_lexicon_file_on_disk(tmp_path):
    plain = evaluate("test", 44, phrasing="heldout")
    # A broad lesson that would change many closes if it were ever applied.
    learned.append(tmp_path, learned.make_entry(
        ["ip case", "cutover", "developer event", "promotion", "ios project", "protection"],
        ["litigation", "migration", "summit", "campaign", "mobile app", "liability", "workers"]))
    assert (tmp_path / "lexicon.jsonl").exists()
    with learned.lexicon(learned.load(tmp_path)):      # control: applied on purpose, it does matter
        assert evaluate("test", 44, phrasing="heldout") != plain
    assert evaluate("test", 44, phrasing="heldout") == plain
    assert claims.LEARNED == []
    # Even a running console with that lesson active keeps the benchmark on the built-in lexicon.
    app = App(tmp_path)
    assert app.config()["learned"]["active"] == 1
    assert app.benchmark({"split": "test", "n": 44, "phrasing": "heldout"}) == plain


# ── over HTTP ──

def test_http_surface(tmp_path):
    server = create_server("127.0.0.1", 0, tmp_path)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    def call(method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
        conn.request(method, path, body=json.dumps(body) if body is not None else None,
                     headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        data = json.loads(response.read())
        conn.close()
        return response.status, data

    base = {"note": "Flights and hotels are the proxy.", "quote": TRAVEL,
            "explanation": showcase.EXPLANATION, "scenario_id": "showcase"}
    try:
        assert call("GET", "/api/lexicon") == (200, {"entries": []})
        status, error = call("POST", "/api/resolutions", {
            "action": "confirm_defect", "note": "The sentence is simply wrong.",
            "learn": {"triggers": ["x y z"], "terms": ["flights"]}})
        assert status == 400 and "only Wrong evidence" in error["error"]
        status, error = call("POST", "/api/resolutions", {
            **base, "action": "fix_evidence", "learn": {"triggers": ["fewer customer visits"], "terms": ["it"]}})
        assert status == 400 and "will not learn" in error["error"]
        status, saved = call("POST", "/api/resolutions", {
            **base, "action": "fix_evidence",
            "learn": {"triggers": ["fewer customer visits"], "terms": ["flights", "hotel"]}})
        assert status == 200 and saved["verdict_after"] == "FAIL" and saved["lesson"]["id"]
        assert call("GET", "/api/config")[1]["learned"] == {"active": 1}
        assert call("GET", "/api/lexicon")[1]["entries"][0]["id"] == saved["lesson"]["id"]
        assert travel(call("POST", "/api/verify", {
            "scenario_id": "showcase", "explanation": showcase.EXPLANATION})[1])["verdict"] == "FAIL"
        assert call("DELETE", f"/api/lexicon?id={saved['lesson']['id']}")[0] == 200
        assert call("POST", "/api/lexicon/remove", {"id": "nope"})[0] == 400
        assert call("GET", "/api/config")[1]["learned"] == {"active": 0}
        assert travel(call("POST", "/api/verify", {
            "scenario_id": "showcase", "explanation": showcase.EXPLANATION})[1])["verdict"] == "REVIEW"
    finally:
        server.shutdown()
        server.server_close()
