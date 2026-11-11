"""The console's script is type-checked under `tsc --strict` (via JSDoc), and the page
references only assets the server serves."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "web"


@pytest.mark.skipif(shutil.which("tsc") is None, reason="TypeScript compiler not installed")
def test_app_js_type_checks_strictly():
    result = subprocess.run(["tsc", "-p", str(WEB / "tsconfig.json")], capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


def test_page_references_only_served_assets():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assets = set(re.findall(r'(?:src|href)="(/[^"]*)"', html))
    assert assets == {"/style.css", "/app.js"}


def test_user_text_is_never_written_as_html():
    script = (WEB / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script


def test_every_element_the_script_looks_up_exists_on_the_page():
    script = (WEB / "app.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    wanted = set(re.findall(r'byId\("([\w-]+)"\)', script))
    present = set(re.findall(r'\bid="([\w-]+)"', html))
    assert wanted and wanted <= present, sorted(wanted - present)
