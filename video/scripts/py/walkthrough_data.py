import os
from pathlib import Path
REPO_ROOT = Path(os.environ.get("PROVEN_REPO", Path(__file__).resolve().parents[3]))
"""Find a real teach example: Sonnet (cached) proposes, a REVIEW claim is taught, the next close is
decided by the rules alone. Read-only against the repo; run with -B and cwd in .scratch."""
import json
import sys

sys.path.insert(0, str(REPO_ROOT))

from proven import learned, gate  # noqa: E402
from proven.extract import RuleExtractor  # noqa: E402
from proven.extractors import build  # noqa: E402
from proven.report import run  # noqa: E402
from proven.synth import generate_split  # noqa: E402
from proven import showcase  # noqa: E402

CACHE = str(REPO_ROOT / "video/.scratch/pydata/cache")
sonnet = build("claude", model="claude-sonnet-5-5", cache_dir=CACHE)
rules = RuleExtractor()

out = {}
# 1. the showcase with rules
sc = run(showcase.EXPLANATION, showcase.ledger() if callable(getattr(showcase, "ledger", None)) else showcase.LEDGER)
out["showcase"] = sc

scen = generate_split("test", 440, "heldout")
pool, held = scen[:220], scen[220:]
found = None
for s in pool:
    rep = run(s.explanation, s.ledger, extractor=sonnet)
    if sonnet.misses:
        print("cache miss; stop", file=sys.stderr)
        break
    labels = {l.quote: l for l in s.labels}
    for r in rep["claims"]:
        lab = labels.get(r["claim"]["quote"])
        if not lab or lab.requirement != "PASS" or r["verdict"] != "REVIEW":
            continue
        if not any(f["code"] == "SUPPORT_RESTS_ON_MODEL_TERMS" for f in r["findings"]):
            continue
        matched = (r["reconstruction"].get("driver") or {}).get("matched", [])
        terms = sorted({m["term"] for m in matched if m["origin"] == "model"})
        try:
            entry = learned.make_entry([r["claim"]["driver"]], terms, quote=r["claim"]["quote"])
        except learned.LessonRefused:
            continue
        with learned.lexicon([entry]):
            after = run(s.explanation, s.ledger, extractor=sonnet)
        if not any(a["verdict"] == "PASS" for a in after["claims"] if a["claim"]["quote"] == r["claim"]["quote"]):
            continue
        # a held close whose rules-only verdict flips REVIEW -> PASS on this lesson
        for h in held:
            before_h = run(h.explanation, h.ledger, extractor=rules)
            with learned.lexicon([entry]):
                after_h = run(h.explanation, h.ledger, extractor=rules)
            flips = [(b, a) for b, a in zip(before_h["claims"], after_h["claims"])
                     if b["claim"]["quote"] == a["claim"]["quote"] and b["verdict"] == "REVIEW" and a["verdict"] == "PASS"]
            if flips:
                found = dict(seed=s.seed, teach_close=rep, teach_after=after, claim=r, entry=entry,
                             held_seed=h.seed, held_before=before_h, held_after=after_h,
                             teach_text=s.explanation, held_text=h.explanation)
                break
        if found:
            break
    if found:
        break

if found:
    imp = gate.impact(found["entry"], [])
    found["gate"] = imp
    out["teach"] = found
json.dump(out, open(REPO_ROOT / "video/.scratch/walkthrough.json", "w"), indent=1, default=str)
print("found" if found else "none")
