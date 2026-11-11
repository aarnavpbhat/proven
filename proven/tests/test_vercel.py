"""The Vercel entry point serves the same API as `python -m proven serve`."""
import http.client
import importlib.util
import json
import shlex
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "api" / "index.py"
CONFIG = ROOT / "vercel.json"

pytestmark = pytest.mark.skipif(not ENTRY.exists(), reason="no Vercel entry point in this checkout")


def load_handler():
    spec = importlib.util.spec_from_file_location("vercel_entry", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler


def test_entry_exports_a_request_handler_class():
    handler = load_handler()
    assert isinstance(handler, type) and issubclass(handler, BaseHTTPRequestHandler)


def test_entry_serves_the_api():
    server = HTTPServer(("127.0.0.1", 0), load_handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
        conn.request("GET", "/api/config")
        config = json.loads(conn.getresponse().read())
        assert config["network"]["allowed"] is False
        conn.request("POST", "/api/verify", body=json.dumps({
            "scenario_id": "showcase",
            "explanation": "Contractor costs increased $22K due to the website redesign."}),
            headers={"Content-Type": "application/json"})
        report = json.loads(conn.getresponse().read())
        assert report["claims"][0]["verdict"] == "FAIL"
    finally:
        server.shutdown()
        server.server_close()


def test_build_command_copies_exactly_the_files_the_page_loads(tmp_path):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    copied = {Path(p).name for p in shlex.split(config["buildCommand"]) if p.startswith("proven/web/")}
    html = (ROOT / "proven" / "web" / "index.html").read_text(encoding="utf-8")
    assert copied == {"index.html", "app.js", "style.css"}
    for asset in ("/app.js", "/style.css"):
        assert asset in html
    # Run the command in a plain shell, as Vercel's build image will, against a copy.
    web = tmp_path / "proven" / "web"
    web.mkdir(parents=True)
    for name in copied:
        (web / name).write_bytes((ROOT / "proven" / "web" / name).read_bytes())
    subprocess.run(config["buildCommand"], shell=True, cwd=tmp_path, check=True)
    assert {p.name for p in (tmp_path / config["outputDirectory"]).iterdir()} == copied
    assert config["rewrites"] == [{"source": "/api/(.*)", "destination": "/api/index"}]


def test_function_limits_and_security_headers():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    function = config["functions"]["api/index.py"]
    assert function["maxDuration"] <= 60 and "proven/tests/**" in function["excludeFiles"]
    headers = {h["key"]: h["value"] for rule in config["headers"] for h in rule["headers"]}
    assert headers == {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin"}
