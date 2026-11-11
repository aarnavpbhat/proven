"""A private copy of the real reviewer console for the video capture (scripts/capture-console.ts).

It is `proven.server` from the repo, unchanged, with three additions made here, not in the repo:
  1. its state lives in video/.scratch/console-data (never the repo's .proven/), fresh on every start;
  2. the Claude extractor replays Claude Sonnet 5.5's cached proposals (video/.scratch/pydata/cache, produced by
     scripts/py/walkthrough_data.py). Nothing is sent: a proposal that is not cached raises, and the network
     guard stays installed, so any outbound connection is refused before a byte leaves;
  3. the Close menu also lists the two held-out test-split closes the walkthrough uses (seed 0, Brightfield
     Health; seed 1155, Cobalt Freight; held-out phrasing), exactly as proven.synth.generate builds them.

Run (read-only against the repo; cwd inside video/.scratch):
  python -B scripts/py/console_replay.py [--port 8766] [--check]
"""
from __future__ import annotations

import os

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO = Path(os.environ.get("PROVEN_REPO", Path(__file__).resolve().parents[3]))
VIDEO = REPO / "video"
DATA = VIDEO / ".scratch" / "console-data"
CACHE_SRC = VIDEO / ".scratch" / "pydata" / "cache" / "claude-claude-sonnet-5-5.jsonl"
SONNET = "claude-sonnet-5-5"

sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO))
os.environ["PROVEN_CLAUDE_MODEL"] = SONNET

from proven import learned, netguard, server  # noqa: E402
from proven.cache import CachedExtractor  # noqa: E402
from proven.extract import RuleExtractor  # noqa: E402
from proven.llm import ClaudeExtractor  # noqa: E402
from proven.synth import generate  # noqa: E402

EXTRA = {"brightfield": 0, "cobalt": 1155}


class ReplayOnly:
    """Has the real Claude extractor's identity (so the cache key matches) but never sends anything."""

    def __init__(self, model: str) -> None:
        real = ClaudeExtractor(model=model)
        self.name, self.version, self.model, self.fingerprint = real.name, real.version, real.model, real.fingerprint
        self.transmissions: list[dict] = []
        self.budget = None

    def propose(self, text, ledger):  # noqa: ANN001
        raise RuntimeError("replay only: this explanation has no cached Sonnet proposal, and nothing is sent")


def build(name: str = "rules", *, model: str | None = None, budget=None, cache_dir: str | None = None):  # noqa: ANN001
    if name == "rules":
        return RuleExtractor()
    if name == "claude":
        return CachedExtractor(ReplayOnly(model or SONNET), str(DATA / "cache"))
    raise server.BadRequest(f"{name} is not available in this capture copy")


_scenarios, _load = server.scenarios, server.load_scenario


def scenarios() -> list[dict]:
    out = _scenarios()
    for sid, seed in EXTRA.items():
        s = generate(seed, phrasing="heldout")
        out.insert(1 + list(EXTRA).index(sid), {"id": sid, "kind": "showcase", "title": f"{s.ledger.entity} — October 2026 close"})
    return out


def load_scenario(scenario_id: str) -> dict:
    if scenario_id in EXTRA:
        s = generate(EXTRA[scenario_id], phrasing="heldout")
        return {"id": scenario_id, "title": f"{s.ledger.entity} — October 2026 close",
                "explanation": s.explanation, "ledger": s.ledger, "ground_truth": None}
    return _load(scenario_id)


server.scenarios = scenarios
server.load_scenario = load_scenario

_config = server.App.config


def config(self):  # noqa: ANN001
    info = _config(self)
    # The open-weight option is left out of the menu (no local model runs during the capture), and the top bar
    # reports the truth for this process: the network guard is installed, outbound connections are refused.
    info["extractors"] = [x for x in info["extractors"] if x["id"] != "openweight"]
    for x in info["extractors"]:
        if x["id"] == "claude":
            x.update(available=True, reason="", default_model=SONNET)
    info["network"] = {"allowed": False, "guard_installed": True}
    return info


server.App.config = config


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--check", action="store_true", help="only check that the walkthrough's proposals are cached")
    args = ap.parse_args()

    if DATA.exists():
        shutil.rmtree(DATA)
    (DATA / "cache").mkdir(parents=True)
    shutil.copy(CACHE_SRC, DATA / "cache" / CACHE_SRC.name)

    netguard.install()                      # outbound connections refused for the whole process
    netguard.network_allowed = lambda: True  # lets the replaying extractor be chosen; it never connects

    if args.check:
        from proven.report import run
        ex = build("claude")
        for sid in EXTRA:
            sc = load_scenario(sid)
            rep = run(sc["explanation"], sc["ledger"], extractor=ex if sid == "brightfield" else RuleExtractor())
            print(sid, sc["title"], [(c["claim"]["claim_id"], c["verdict"]) for c in rep["claims"]],
                  "hits", ex.hits, "misses", ex.misses)
        return

    httpd = server.create_server("127.0.0.1", args.port, DATA, warm_gate=True, build=build,
                                 probe=lambda: (False, "not used in this capture", []))
    print(f"capture console at http://127.0.0.1:{args.port}/ (state in {DATA}; lessons {learned.path(DATA)})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
