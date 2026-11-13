"""The terms-only training rows and the two-stage vote: blind, well-formed, nothing measured."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from build_terms_dataset import rows_of  # noqa: E402
from build_worlds_dataset import tokens  # noqa: E402
from teacher_terms import SYSTEM  # noqa: E402
from two_stage import claims_of, vote  # noqa: E402
from proven.synth import DEFAULT  # noqa: E402


def test_each_row_is_one_reason_and_a_term_list_with_no_vendor():
    rows, stats = rows_of(DEFAULT, {}, None, set(), 8)
    assert rows and stats["rows"] == len(rows)
    vendors = {e.vendor.lower() for s in DEFAULT.specs for e in s.events}
    for row in rows:
        system, user, answer = (m["content"] for m in row["messages"])
        assert system == SYSTEM and user.count('1. [') == 1
        terms = json.loads(answer)["1"]
        assert 3 <= len(terms) <= 8 and all(isinstance(t, str) and t for t in terms)
        assert not any(v in user.lower() for v in vendors)      # the question names no vendor
    for spec in DEFAULT.specs:
        assert f"- {spec.name}" in rows[0]["messages"][1]["content"]


def test_a_measured_phrase_is_dropped_and_oblique_only_keeps_the_training_paraphrases():
    spec, event = DEFAULT.specs[0], DEFAULT.specs[0].events[0]
    phrase = event.phrases[0]
    rows, stats = rows_of(DEFAULT, {}, None, {phrase.lower()}, 8)
    assert stats["dropped"] >= 1
    assert not any(f'"{phrase}"' in r["messages"][1]["content"] for r in rows)
    oblique, _ = rows_of(DEFAULT, {}, None, set(), 8, oblique_only=True)
    allowed = {p for key in DEFAULT.paraphrase_train for p in DEFAULT.paraphrase_train[key]}
    for row in oblique:
        said = row["messages"][1]["content"].split('] "', 1)[1].split('"\n', 1)[0]
        assert said in allowed
    assert len(oblique) < len(rows_of(DEFAULT, {}, None, set(), 8)[0])


def test_a_true_teacher_guess_leads_the_answer():
    spec = DEFAULT.specs[0]
    event = spec.events[1]
    phrase = DEFAULT.paraphrase_train[event.key][0]
    rows, stats = rows_of(DEFAULT, {f"{spec.name}\t{phrase}": ["settlement", "zzz-not-there"]}, None, set(), 8)
    row = next(r for r in rows if f'[{spec.name}] "{phrase}"' in r["messages"][1]["content"])
    terms = json.loads(row["messages"][2]["content"])["1"]
    assert terms[0] == "settlement" and stats["hit"] >= 1
    assert not tokens(" ".join(terms)) & (tokens(event.vendor) - tokens(spec.name))


def test_vote_orders_by_agreement_then_greedy_order_and_caps():
    assert vote([["a", "b", "c"], ["c", "d"], ["c", "b", "b"]], 3) == ["c", "b", "a"]
    assert vote([["a", "b"]], 8) == ["a", "b"]
    assert vote([], 8) == []
    assert vote([["a", "b", "c"], ["c", "d"], ["c", "b"]], 8, min_votes=2) == ["c", "b"]
    assert vote([["a", "b"], ["c"]], 8, min_votes=2) == ["a", "b", "c"]   # nothing agreed: all stand


def test_claims_of_reads_a_reply_or_gives_nothing():
    reply = json.dumps({"claims": [{"account": "X", "reason_text": "r", "search_terms": ["t"]}, "junk"]})
    assert claims_of(reply) == [{"account": "X", "reason_text": "r", "search_terms": ["t"]}]
    assert claims_of("not json at all") == []
