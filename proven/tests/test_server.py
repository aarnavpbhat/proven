"""The HTTP API, end to end over loopback."""
import http.client
import json
import threading

import pytest

from proven.server import create_server
from proven.showcase import EXPLANATION


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    server = create_server("127.0.0.1", 0, tmp_path_factory.mktemp("data"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    def call(method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        payload = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, body=payload, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        raw = response.read()
        ctype = response.getheader("Content-Type", "")
        conn.close()
        return response.status, (json.loads(raw) if "json" in ctype else raw.decode())

    yield call
    server.shutdown()
    server.server_close()


def test_the_console_and_its_assets_are_served(api):
    status, html = api("GET", "/")
    assert status == 200 and "<title>" in html and "app.js" in html
    assert api("GET", "/app.js")[0] == 200 and api("GET", "/style.css")[0] == 200
    assert api("GET", "/../server.py")[0] == 404


def test_config_reports_network_off_and_the_closed_action_set(api):
    status, config = api("GET", "/api/config")
    assert status == 200 and config["network"]["allowed"] is False
    claude = next(e for e in config["extractors"] if e["id"] == "claude")
    assert claude["available"] is False and "network" in claude["reason"]
    assert {a["id"] for a in config["actions"]} >= {"confirm_defect", "out_of_scope"}


def test_scenarios_cover_the_showcase_and_every_family(api):
    _, data = api("GET", "/api/scenarios")
    ids = [s["id"] for s in data["scenarios"]]
    assert ids[:2] == ["showcase", "tidewater"] and len(ids) == 13
    status, scenario = api("GET", f"/api/scenario?id={ids[3]}")
    assert status == 200 and scenario["ground_truth"]["labels"]


def test_verify_a_scenario(api):
    status, report = api("POST", "/api/verify", {"scenario_id": "showcase", "explanation": EXPLANATION})
    assert status == 200 and report["coverage"]["verdicts"] == {"PASS": 4, "FAIL": 3, "REVIEW": 2}


def test_verify_an_uploaded_csv(api):
    _, csv_text = api("GET", "/api/ledger.csv?id=showcase")
    assert csv_text.startswith("id,date,account,vendor,memo,amount")
    status, report = api("POST", "/api/verify", {
        "ledger_csv": csv_text, "explanation": "Contractors rose $22K due to the website redesign."})
    assert status == 200 and report["claims"][0]["verdict"] == "FAIL"


def test_bad_requests_are_explained(api):
    assert api("POST", "/api/verify", {"scenario_id": "showcase", "explanation": " "})[0] == 400
    status, error = api("POST", "/api/verify", {"ledger_csv": "nope", "explanation": "x"})
    assert status == 400 and "CSV" in error["error"]
    status, error = api("POST", "/api/verify", {"scenario_id": "showcase", "explanation": "x",
                                                 "extractor": "claude"})
    assert status == 400 and "--allow-network" in error["error"]
    assert api("GET", "/api/scenario?id=../../etc")[0] == 400


def test_benchmark(api):
    status, result = api("POST", "/api/benchmark", {"split": "test", "n": 22, "phrasing": "seen"})
    assert status == 200 and result["defects"]["unsafe_passes"] == 0
    assert api("POST", "/api/benchmark", {"n": 99999})[0] == 400
    status, result = api("POST", "/api/benchmark", {"split": "train", "n": 22,
                                                     "phrasing": "paraphrase"})
    assert status == 200 and result["phrasing"] == "paraphrase"
    assert api("POST", "/api/benchmark", {"phrasing": "slang"})[0] == 400


def test_resolutions_need_a_closed_action_and_a_reason(api):
    assert api("POST", "/api/resolutions", {"action": "approve", "note": "looks fine to me"})[0] == 400
    assert api("POST", "/api/resolutions", {"action": "confirm_defect", "note": "ok"})[0] == 400
    status, saved = api("POST", "/api/resolutions", {
        "run_id": "r1", "claim_id": "C1", "verdict": "FAIL", "action": "confirm_defect",
        "note": "Narrative overstates legal by the misbooked invoice.", "seconds_on_claim": 42})
    assert status == 200 and saved["resolution"]["reduces_review"] is False
    _, listed = api("GET", "/api/resolutions")
    assert listed["resolutions"][-1]["seconds_on_claim"] == 42


def test_the_command_line_reports_its_version():
    import subprocess
    import sys
    from pathlib import Path

    from proven import __version__
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-m", "proven", "--version"], cwd=root,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and result.stdout.strip() == f"proven {__version__}"
