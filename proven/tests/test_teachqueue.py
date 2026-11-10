"""The teaching queue: ranking, stored runs, the console endpoints, and the teaching curve."""
import http.client
import json
import threading

import pytest

from proven import claims, teachqueue, teachsim
from proven.__main__ import main
from proven.evaluate import OracleExtractor
from proven.report import run
from proven.server import App, BadRequest, create_server
from proven.synth import generate_split


def waiting(key, arrival, driver, terms=("x1",)):
    return teachqueue.Waiting(key, arrival, f"quote {key}", driver, tuple(terms))


# ── ranking ──

def test_frequency_asks_first_for_the_lesson_that_reaches_most_waiting_claims():
    items = [waiting(1, 0, "the iOS project"),
             waiting(2, 1, "the second location"),
             waiting(3, 2, "the second location in September"),
             waiting(4, 3, "the second location", ("lease",)),
             waiting(5, 4, "the second location", ("lease",))]
    ranker = teachqueue.Ranker()
    first = ranker.rank(items, "frequency")[0]
    # "the second location" fires on four waiting reasons, including the "in September" one;
    # of its two proposals, the one the model made twice wins the tie.
    assert (first["trigger"], first["reach"], first["terms"]) == ("the second location", 4, ["lease"])
    assert [r["trigger"] for r in ranker.rank(items, "arrival")][0] == "the ios project"
    with pytest.raises(ValueError):
        ranker.rank(items, "random")


# ── stored runs and the queue ──

def oracle_runs(data_dir, n=22):
    stored = 0
    for scenario in generate_split("test", n, "heldout"):
        report = run(scenario.explanation, scenario.ledger, extractor=OracleExtractor(scenario))
        stored += teachqueue.record_run(data_dir, {"scenario_id": scenario.scenario_id}, report)
    return stored


def test_a_rules_run_is_never_stored_and_never_replaces_a_model_run(tmp_path):
    scenario = generate_split("test", 1, "heldout")[0]
    model = run(scenario.explanation, scenario.ledger, extractor=OracleExtractor(scenario))
    assert teachqueue.record_run(tmp_path, {"scenario_id": scenario.scenario_id}, model) > 0
    rules = run(scenario.explanation, scenario.ledger)
    assert teachqueue.record_run(tmp_path, {"scenario_id": scenario.scenario_id}, rules) == 0
    assert teachqueue.load_runs(tmp_path)[0]["claims"]


def test_queue_ranks_previews_and_empties_as_lessons_are_taught(tmp_path):
    assert oracle_runs(tmp_path) > 5
    app = App(tmp_path)
    queue = app.queue()
    assert queue["waiting"] > 5 and queue["items"]
    reach = [item["waiting"] for item in queue["items"]]
    assert reach == sorted(reach, reverse=True)
    top = queue["items"][0]
    assert top["impact"]["accepted"] and top["impact"]["tested"] and top["unlocks"] == top["waiting"]

    stored = app.pending(top["example"]["key"])
    assert stored["explanation"] and stored["scenario_id"].startswith("syn-")
    with pytest.raises(BadRequest):
        app.pending("nope")

    saved = app.record({
        "run_id": top["example"]["run_id"], "claim_id": "C1", "quote": top["example"]["quote"],
        "verdict": "REVIEW", "action": "accept_convention", "note": "These memos are this cause.",
        "explanation": stored["explanation"], "scenario_id": stored["scenario_id"],
        "learn": {"triggers": [top["example"]["driver"]], "terms": top["terms"], "confirm_pass": True}})
    assert saved["verdict_after"] == "PASS" and saved["impact"]["accepted"]
    after = app.queue()
    assert after["waiting"] == queue["waiting"] - top["waiting"]
    assert top["trigger"] not in {item["trigger"] for item in after["items"]}


def test_queue_and_pending_over_http(tmp_path):
    oracle_runs(tmp_path, 11)
    server = create_server("127.0.0.1", 0, tmp_path)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def call(method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=60)
        conn.request(method, path, body=json.dumps(body) if body is not None else None,
                     headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        data = json.loads(response.read())
        conn.close()
        return response.status, data

    try:
        status, queue = call("GET", "/api/queue")
        assert status == 200 and queue["items"]
        key = queue["items"][0]["example"]["key"]
        assert call("GET", f"/api/pending?key={key}")[1]["key"] == key
        status, report = call("POST", "/api/lexicon/check", {"triggers": ["trip"], "terms": ["flights"]})
        assert status == 200 and report["accepted"] is False and "known to be right" in report["refusal"]
        status, error = call("POST", "/api/lexicon/check", {"triggers": ["the"], "terms": ["flights"]})
        assert status == 400 and "common words" in error["error"]
        # A refused lesson comes back as 400 with the gate's report attached.
        scenario = generate_split("test", 1, "heldout")[0]
        status, refused = call("POST", "/api/resolutions", {
            "action": "accept_convention", "note": "Trips are flights, says a hurried reviewer.",
            "quote": scenario.labels[0].quote, "explanation": scenario.explanation,
            "scenario_id": scenario.scenario_id, "learn": {"triggers": ["trip"], "terms": ["flights"]}})
        assert status == 400 and refused["impact"]["accepted"] is False
        assert refused["error"] == refused["impact"]["refusal"]
    finally:
        server.shutdown()
        server.server_close()


# ── the teaching curve ──

def test_curve_counts_confirmations_and_keeps_the_kill_criteria():
    off = teachsim.curve(110, "heldout", order="frequency", checkpoints=(0, 5, 10))
    on = teachsim.curve(110, "heldout", order="frequency", checkpoints=(0, 5, 10), use_gate=True)
    labels = [r["label"] for r in off["rows"]]
    assert labels[:3] == ["0", "5", "10"] and labels[-1].endswith("all") or labels[-1].endswith("(all)")
    assert [r["confirmations"] for r in off["rows"][:3]] == [0, 5, 10]
    assert off["rows"][-1]["decided_share"] > off["rows"][0]["decided_share"]
    for result in (off, on):
        assert all(r["unsafe_passes"] == 0 and r["control_fails"] == 0 for r in result["rows"])
    # Careful lessons from gold terms: the gate refuses none of them, so it changes nothing.
    assert on["stats"]["refused_right"] == 0 and on["rows"] == off["rows"]
    assert claims.LEARNED == []


def test_arrival_order_reproduces_the_close_by_close_simulation():
    arrival = teachsim.curve(110, "heldout", order="arrival", checkpoints=(0,))
    plain = teachsim.simulate(110, "heldout", steps=(55,))["rows"][0]
    assert arrival["rows"][-1]["lessons"] == plain["lessons"]
    assert arrival["rows"][-1]["decided_share"] == plain["decided_share"]


def test_skewed_population_follows_its_weights():
    flat = teachsim.skewed_split(60, "heldout", 0.0)
    steep = teachsim.skewed_split(60, "heldout", 2.0)
    def top_share(scenarios):
        counts = {}
        for s in scenarios:
            phrase = s.labels[0].gold["reason_text"]
            counts[phrase] = counts.get(phrase, 0) + 1
        return max(counts.values()) / len(scenarios)
    assert len(flat) == len(steep) == 60 and top_share(steep) > 2 * top_share(flat)
    with pytest.raises(ValueError):
        teachsim.curve(22, "heldout", proposer=object(), skew=1.0)


def test_teach_sim_cli_prints_curves(capsys):
    assert main(["teach-sim", "--n", "44", "--order", "both", "--checkpoints", "0,5"]) == 0
    out = capsys.readouterr().out
    assert "order=arrival" in out and "order=frequency" in out and "confirmations" in out
