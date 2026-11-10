"""The reply grammar accepts what the model was trained to write, and nothing inadmissible."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from constrain import END, MAX_TERMS, Grammar, Mask, Vocab, accounts_of  # noqa: E402
from proven import worlds  # noqa: E402
from proven.llm import payload  # noqa: E402
from proven.openweight import parse_reply, proposals_from  # noqa: E402
from proven.synth import generate_split  # noqa: E402

EOS = 0
# Single bytes plus the kind of multi-piece tokens a byte-level BPE vocabulary really has.
MERGED = [b'", "', b' [{"', b'"]}', b'{"', b'":', b' "",', b'",', b' "', b'"]', b']}', b'}, {"',
          b"claims", b"quote", b"account", b"search", b"_terms", b" rose", b" the", b"K", b"up",
          b'", "account": "', b'": "', b' ["', b"ing", b"tion", b" $", b'""', b'"}', b"\xe2\x80\x94"]
TOKENS: list = [None] + [bytes([b]) for b in range(256)] + MERGED
VOCAB = Vocab(TOKENS, EOS)


def grammar_for(scenario) -> Grammar:
    explanation, names = accounts_of(payload(scenario.explanation, scenario.ledger))
    return Grammar(explanation, names)


def gold(scenario) -> str:
    return json.dumps({"claims": scenario.gold_claims()}, ensure_ascii=False)


def closes():
    out = [s for ph in ("seen", "paraphrase", "heldout") for s in generate_split("train", 40, ph)]
    for world in worlds.suite("unseen")[:3]:
        out += generate_split("train", 15, "paraphrase", world=world)
    return out


def test_gold_replies_are_accepted():
    for scenario in closes():
        grammar = grammar_for(scenario)
        assert grammar.supported
        assert grammar.accepts(gold(scenario)), scenario.scenario_id


def test_empty_reply_is_accepted():
    grammar = grammar_for(generate_split("train", 1, "seen")[0])
    assert grammar.accepts('{"claims": []}')


def reject(scenario, mutate) -> bool:
    data = {"claims": scenario.gold_claims()}
    mutate(data["claims"][0])
    return not grammar_for(scenario).accepts(json.dumps(data, ensure_ascii=False))


def test_inadmissible_replies_are_rejected():
    scenario = generate_split("train", 1, "paraphrase")[0]
    assert reject(scenario, lambda c: c.update(quote=c["quote"][:-3] + "xyz"))
    assert reject(scenario, lambda c: c.update(quote=""))
    assert reject(scenario, lambda c: c.update(account="Imaginary Account"))
    assert reject(scenario, lambda c: c.update(direction="sideways"))
    assert reject(scenario, lambda c: c.update(change_text="$999.9K"))
    assert reject(scenario, lambda c: c.update(reason_text="a cause nobody wrote down"))
    assert reject(scenario, lambda c: c.update(search_terms=["t"] * (MAX_TERMS + 1)))
    assert reject(scenario, lambda c: c.update(search_terms=[""]))
    grammar = grammar_for(scenario)
    assert not grammar.accepts(gold(scenario) + " ")
    assert not grammar.accepts(json.dumps({"claims": scenario.gold_claims()}, indent=1))


def test_a_copied_field_cannot_cross_a_line():
    scenario = generate_split("train", 1, "seen")[0]
    lines = scenario.explanation.split("\n")
    assert reject(scenario, lambda c: c.update(quote=lines[0][-5:] + "\n" + lines[1][:5]))


def test_quotes_in_the_explanation_are_not_supported():
    assert not Grammar('He said "no".', ["Rent"]).supported
    assert Grammar("Plain text.", ["Rent"]).supported


def test_gold_tokenised_any_way_stays_inside_the_mask():
    """Greedy longest-match over a vocabulary with multi-piece tokens: every token of a
    gold reply must be in the allowed set at its position."""
    for scenario in closes()[::7]:
        grammar = grammar_for(scenario)
        mask, state, data = Mask(VOCAB, grammar), grammar.start, gold(scenario).encode("utf-8")
        i = 0
        while i < len(data):
            node, best, j = VOCAB.root, None, i
            while j < len(data) and data[j] in node[0]:
                node = node[0][data[j]]
                j += 1
                if node[1] >= 0:
                    best = (node[1], j)
            token, i = best
            assert token in mask.allowed(state), (scenario.scenario_id, TOKENS[token])
            state = grammar.feed(state, TOKENS[token])
        assert state == END
        assert mask.allowed(state) == [EOS]


def test_random_walks_through_the_mask_are_admissible():
    """Whatever the model samples, the finished reply parses and every copied field is a
    substring of the explanation."""
    rng = random.Random(7)
    done = 0
    for scenario in closes()[::9]:
        grammar = grammar_for(scenario)
        mask = Mask(VOCAB, grammar)
        explanation = scenario.explanation
        names = {a.name for a in scenario.ledger.accounts} | {"Total operating expenses", ""}
        for _ in range(3):
            state, out = grammar.start, b""
            for _step in range(6000):
                allowed = mask.allowed(state)
                assert allowed, state
                if state == END:
                    break
                # lean towards closing tokens so walks finish
                closing = [t for t in allowed if TOKENS[t] and TOKENS[t][:1] in (b'"', b"}", b"]", b",")]
                token = rng.choice(closing) if closing and rng.random() < 0.25 else rng.choice(allowed)
                out += TOKENS[token]
                state = grammar.feed(state, TOKENS[token])
                assert state is not None
            if state != END:
                continue
            done += 1
            data = json.loads(out.decode("utf-8", errors="replace"))
            proposals = proposals_from(parse_reply(out.decode("utf-8", errors="replace")))
            assert len(proposals) == len(data["claims"])
            for claim in data["claims"]:
                assert claim["quote"] and claim["quote"] in explanation
                assert claim["account"] in names
                assert claim["direction"] in ("up", "down", "")
                for field in ("change_text", "percent_text", "prior_text", "current_text", "reason_text"):
                    assert claim[field] in explanation
                assert len(claim["search_terms"]) <= MAX_TERMS
                assert all(claim["search_terms"])
    assert done >= 10
