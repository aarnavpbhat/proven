import os
from pathlib import Path
REPO_ROOT = Path(os.environ.get("PROVEN_REPO", Path(__file__).resolve().parents[3]))
import json, sys
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "training"))
from pathlib import Path
from proven import worlds
from proven.synth import generate, seeds
import build_worlds_dataset as B
w = worlds.load(Path(REPO_ROOT / "training/worlds/dev/commercial-laundry-service.json"), role="train")
teacher = json.load(open(REPO_ROOT / ".proven/ft/teacher/commercial-laundry-service.json"))
idx = B.cause_index(w)
want = "the batch that came back the wrong shade"
for seed in seeds("train", 3000):
    s = generate(seed, phrasing="paraphrase", world=w)
    for c in s.gold_claims():
        if c["reason_text"].lower() == want:
            spec, ev = idx[want]
            g = teacher[f"{spec.name}\t{c['reason_text']}"]
            out, hits = B.targets(spec, ev, c["search_terms"], g, s.ledger, 8)
            print("quote:", c["quote"]); print("gold:", c["search_terms"]); print("guesses:", g); print("targets:", out, "hits", hits)
            print("vendor-only:", B.tokens(ev.vendor) - set().union(*(B.tokens(m) for m in ev.memos)))
            sys.exit()
