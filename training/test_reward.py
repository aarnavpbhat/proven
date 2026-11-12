"""Tests for the RL environment (`reward.py`) and the model-free decisions of `rl.py`.

    PROVEN_ENV_FILE=/dev/null python -m pytest -q training/test_reward.py

Nothing here imports MLX or `rl.py` (which does); the helpers `rl.py` uses live in
`reward.py` for that reason.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import reward  # noqa: E402
from proven import learned, worlds  # noqa: E402
from proven.claims import ClaimProposal  # noqa: E402
from proven.evaluate import proposal_from_gold, score_claim  # noqa: E402
from proven.extract import RuleExtractor  # noqa: E402
from proven.report import run  # noqa: E402
from proven.synth import Scenario, generate, seeds  # noqa: E402
from proven.teachsim import MODEL_SUPPORT, teach  # noqa: E402

TRAIN_DIR, DEV_DIR = HERE / "worlds" / "train", HERE / "worlds" / "dev"
TRAIN_SEEDS = seeds("train", 2040)[2000:]
TEST_SEED = seeds("test", 1)[0]


@pytest.fixture(scope="module")
def train_worlds():
    """Three training worlds (loading all 91 takes half a minute)."""
    return [worlds.load(f, role="train") for f in sorted(TRAIN_DIR.glob("*.json"))[:3]]


@pytest.fixture(scope="module")
def dev_worlds():
    return reward.load_worlds(DEV_DIR)


# ── the reward as it was before runs were shared (commit 5fa6cbb), kept to compare ──

def _old_careless_lessons(scenario: Scenario, proposer) -> list[dict]:
    report = run(scenario.explanation, scenario.ledger, extractor=proposer)
    lessons: list[dict] = []
    for result in report["claims"]:
        if result["verdict"] != "REVIEW":
            continue
        if not any(f["code"] == MODEL_SUPPORT for f in result["findings"]):
            continue
        matched = (result["reconstruction"].get("driver") or {}).get("matched", [])
        terms = sorted({m["term"] for m in matched if m["origin"] == "model"})
        try:
            lessons.append(learned.make_entry([result["claim"]["driver"]], terms,
                                              quote=result["claim"]["quote"],
                                              action="simulated", note="careless"))
        except learned.LessonRefused:
            continue
    return lessons


def _old_score(scenario: Scenario, lessons: list[dict], extractor) -> list[dict]:
    with learned.lexicon(lessons):
        report = run(scenario.explanation, scenario.ledger, extractor=extractor)
    by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
    return [score_claim(label, by_quote.get(label.quote)) for label in scenario.labels]


def old_score_proposals(scenario: Scenario, proposals: list[ClaimProposal],
                        parsed: bool = True) -> reward.Outcome:
    proposer = reward.Fixed(proposals)
    lessons = teach([scenario], lambda _s: proposer)
    as_model = _old_score(scenario, lessons, proposer)
    as_rules = _old_score(scenario, lessons, RuleExtractor())
    careless = _old_careless_lessons(scenario, proposer)
    trapped = _old_score(scenario, lessons + careless, RuleExtractor()) if careless else as_rules
    n = len(scenario.labels)
    traps = sum(1 for label, s in zip(scenario.labels, trapped)
                if label.requirement != "PASS" and s["verdict"] == "PASS")
    total = sum(0.5 * m["reward"] + 0.5 * r["reward"] for m, r in zip(as_model, as_rules))
    value = (total - reward.TRAP_PENALTY * traps) / n if n else 0.0
    wrong = [i for i, label in enumerate(scenario.labels) if label.requirement != "PASS"]
    right = [i for i, label in enumerate(scenario.labels) if label.requirement == "PASS"]
    return reward.Outcome(
        reward=round(value, 4), parsed=parsed, lessons=len(lessons), labels=n,
        model_decided=sum(s["verdict"] in ("PASS", "FAIL") for s in as_model),
        rules_decided=sum(s["verdict"] in ("PASS", "FAIL") for s in as_rules),
        unsafe=sum(1 for i in wrong for s in (as_model[i], as_rules[i]) if s["verdict"] == "PASS"),
        control_fails=sum(1 for i in right for s in (as_model[i], as_rules[i])
                          if s["verdict"] == "FAIL"),
        traps=traps)


def _replies(scenario: Scenario) -> dict[str, list[ClaimProposal]]:
    """Replies a proposer might give: the gold one and ways of getting it wrong."""
    gold = [proposal_from_gold(label.gold) for label in scenario.labels]
    main = scenario.labels[0].gold
    borrowed = scenario.labels[-1].gold["search_terms"] if len(scenario.labels) > 1 else ["invoice"]
    vendor_words = sorted({w.lower() for t in scenario.ledger.transactions for w in t.vendor.split()
                           if len(w) > 3 and w.isalpha()})[:4]
    return {
        "gold": gold,
        "nothing": [],
        "no_terms": [proposal_from_gold({**label.gold, "search_terms": []}) for label in scenario.labels],
        "first_only": gold[:1],
        "one_term": [proposal_from_gold({**label.gold, "search_terms": label.gold["search_terms"][:1]})
                     for label in scenario.labels],
        "wrong_terms": [proposal_from_gold({**main, "search_terms": list(borrowed)})] + gold[1:],
        "vendor_terms": [proposal_from_gold({**label.gold, "search_terms": vendor_words})
                         for label in scenario.labels],
        "bad_quote": [proposal_from_gold({**main, "quote": main["quote"][:-9]})] + gold[1:],
    }


def _closes(train_worlds, dev_worlds) -> list[Scenario]:
    out = [reward.episode(s) for s in TRAIN_SEEDS[:24]]
    out += [reward.episode(s, "seen") for s in TRAIN_SEEDS[24:30]]
    for i, world in enumerate([*train_worlds, *dev_worlds]):
        out += [reward.episode(s, "paraphrase", world) for s in TRAIN_SEEDS[i:i + 6]]
    return out


def test_shared_runs_change_no_reward(train_worlds, dev_worlds):
    closes = _closes(train_worlds, dev_worlds)
    assert len(closes) >= 60 and len({c.world for c in closes}) == 8
    compared, differing = 0, set()
    for scenario in closes:
        expected = {name: old_score_proposals(scenario, reply).to_dict()
                    for name, reply in _replies(scenario).items()}
        # scored in a different order from the original, twice: the per-close cache of the
        # rules' runs must not make a reward depend on what was scored before it
        for names in (reversed(list(expected)), list(expected)):
            for name in names:
                got = reward.score_proposals(scenario, _replies(scenario)[name]).to_dict()
                assert got == expected[name], (scenario.scenario_id, name)
                compared += 1
        differing.add(len({o["reward"] for o in expected.values()}) > 1)
    assert compared >= 60 * 8 and True in differing


def test_score_reply_matches_the_original_on_text(train_worlds):
    import json
    for scenario in [reward.episode(TRAIN_SEEDS[0]), reward.episode(TRAIN_SEEDS[1], world=train_worlds[0])]:
        gold = [proposal_from_gold(label.gold) for label in scenario.labels]
        text = json.dumps({"claims": scenario.gold_claims()})
        assert reward.score_reply(scenario, text).reward == old_score_proposals(scenario, gold).reward
        garbled = reward.score_reply(scenario, '{"claims": [{"quote": "x"')
        assert not garbled.parsed
        assert garbled.reward == old_score_proposals(scenario, [], parsed=False).reward


def test_an_active_lexicon_does_not_change_the_answer_to_the_original(train_worlds):
    """The careless reviewer's look is shared with the teaching reviewer's only when no
    lexicon is active outside; with one, the original's separate run is made."""
    scenario = reward.episode(TRAIN_SEEDS[3], world=train_worlds[1])
    gold = [proposal_from_gold(label.gold) for label in scenario.labels]
    outside = [learned.make_entry([scenario.labels[0].gold["reason_text"]],
                                  scenario.labels[0].gold["search_terms"][:2])]
    with learned.lexicon(outside):
        expected = old_score_proposals(scenario, gold).to_dict()
        assert reward.score_proposals(scenario, gold).to_dict() == expected


# ── episodes and worlds ──────────────────────────────────────────────────

def test_test_seeds_are_refused_in_every_world(train_worlds, dev_worlds):
    for world in (None, train_worlds[0], dev_worlds[0]):
        with pytest.raises(ValueError, match="test split"):
            reward.episode(TEST_SEED, "paraphrase", world)
        assert reward.episode(TRAIN_SEEDS[0], "paraphrase", world).split == "train"


def test_episode_comes_from_the_world_given(train_worlds):
    world = train_worlds[0]
    scenario = reward.episode(TRAIN_SEEDS[0], "paraphrase", world)
    assert scenario.world == world.name
    assert set(scenario.ledger.account_names) == {spec.name for spec in world.specs}
    assert reward.episode(TRAIN_SEEDS[0]).world == "default"
    assert reward.episode(TRAIN_SEEDS[0]).explanation == generate(TRAIN_SEEDS[0], phrasing="paraphrase").explanation


def test_measured_suites_are_refused(tmp_path):
    with pytest.raises(ValueError, match="measured"):
        reward.load_worlds(worlds.HERE / "unseen")
    with pytest.raises(ValueError, match="measured"):
        reward.load_worlds(worlds.HERE)
    with pytest.raises(ValueError, match="measured"):
        reward.load_worlds(worlds.HERE.parent)                  # a folder that holds them
    with pytest.raises(ValueError, match="measured"):
        reward.load_worlds(worlds.HERE / "unseen" / ".." / "unseen")
    link = tmp_path / "innocent"
    link.symlink_to(worlds.HERE / "unseen", target_is_directory=True)
    with pytest.raises(ValueError, match="measured"):
        reward.load_worlds(link)
    copied = tmp_path / "copied"
    copied.mkdir()
    source = sorted((worlds.HERE / "unseen").glob("*.json"))[0]
    (copied / "renamed.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError, match="measured world"):
        reward.load_worlds(copied)
    with pytest.raises(FileNotFoundError):
        reward.load_worlds(tmp_path / "copied" / "nothing-here")


def test_training_and_dev_worlds_are_not_measured_ones(dev_worlds):
    measured = reward.measured_slugs()
    assert len(measured) >= 4
    assert len(dev_worlds) == 4 and not {w.name for w in dev_worlds} & measured
    import json
    train_slugs = {json.loads(f.read_text(encoding="utf-8"))["slug"] for f in TRAIN_DIR.glob("*.json")}
    assert len(train_slugs) > 50
    assert not train_slugs & measured and not train_slugs & {w.name for w in dev_worlds}


def test_gold_beats_nothing_in_authored_worlds(train_worlds, dev_worlds):
    for world in [*train_worlds, *dev_worlds]:
        gold, nothing = [], []
        for seed in TRAIN_SEEDS[:12]:
            scenario = reward.episode(seed, "paraphrase", world)
            top = reward.score_proposals(scenario, reward.gold_proposals(scenario)).reward
            assert top == reward.ceiling(scenario)
            empty = reward.score_proposals(scenario, []).reward
            assert -2 <= empty <= top <= 1
            gold.append(top)
            nothing.append(empty)
        assert sum(gold) / len(gold) > sum(nothing) / len(nothing) + 0.5, world.name


def test_leaks_reads_the_stated_reason():
    scenario = reward.episode(TRAIN_SEEDS[0])
    reason = scenario.labels[-1].gold["reason_text"]
    assert reward.leaks(scenario, {reason.lower()})
    assert not reward.leaks(scenario, {"a phrase nobody wrote"})
    assert not reward.leaks(scenario, frozenset())


# ── which world an episode comes from ────────────────────────────────────

def test_round_robin_is_even_and_deterministic():
    names = [f"w{i}" for i in range(7)]
    first = [reward.pick_world(names, i, seed=3) for i in range(21)]
    assert first == [reward.pick_world(names, i, seed=3) for i in range(21)]
    assert sorted(first[:7]) == names                       # each world once per round
    assert first[:7] == first[7:14] == first[14:]           # the same order every round
    assert first[:7] != [reward.pick_world(names, i, seed=4) for i in range(7)]
    assert sorted(reward.world_order(91, 0)) == list(range(91))
    assert reward.world_order(91, 0) != tuple(range(91))
    assert reward.pick_world(None, 5) is None and reward.pick_world([], 5) is None


def test_training_episode_follows_the_cursor(train_worlds):
    pool = TRAIN_SEEDS[:10]
    for cursor in (0, 4, 13):
        scenario = reward.training_episode(pool, cursor, "paraphrase", train_worlds, seed=1)
        assert scenario.seed == pool[cursor % 10]
        assert scenario.world == reward.pick_world(train_worlds, cursor, 1).name
        again = reward.training_episode(pool, cursor, "paraphrase", train_worlds, seed=1)
        assert again.explanation == scenario.explanation
    assert reward.training_episode(pool, 2, "paraphrase").world == "default"
    stated = reward.training_episode(pool, 2, "paraphrase", train_worlds).labels[0].gold["reason_text"]
    assert reward.training_episode(pool, 2, "paraphrase", train_worlds, measured={stated.lower()}) is None


def test_validation_is_spread_evenly_over_dev_worlds(dev_worlds):
    closes, used = reward.validation_closes(TRAIN_SEEDS, 10, "paraphrase", dev_worlds)
    assert used == 10 and [c.seed for c in closes] == TRAIN_SEEDS[:10]
    counts = [sum(c.world == w.name for c in closes) for w in dev_worlds]
    assert sum(counts) == 10 and max(counts) - min(counts) <= 1
    assert all(c.split == "train" for c in closes)
    default, used = reward.validation_closes(TRAIN_SEEDS, 5, "paraphrase")
    assert used == 5 and [c.explanation for c in default] == [reward.episode(s).explanation
                                                              for s in TRAIN_SEEDS[:5]]


def test_validation_passes_over_a_leaking_close_and_keeps_the_spread(dev_worlds):
    plain, _ = reward.validation_closes(TRAIN_SEEDS, 6, "paraphrase", dev_worlds)
    banned = {plain[1].labels[0].gold["reason_text"].lower()}
    closes, used = reward.validation_closes(TRAIN_SEEDS, 6, "paraphrase", dev_worlds, banned)
    assert len(closes) == 6 and used > 6
    assert not any(reward.leaks(c, banned) for c in closes)
    assert [c.world for c in closes] == [dev_worlds[i % 4].name for i in range(6)]
    assert TRAIN_SEEDS[used] not in {c.seed for c in closes}       # the pool starts after them
    with pytest.raises(ValueError):
        reward.validation_closes(TRAIN_SEEDS[:3], 6, "paraphrase", dev_worlds)


# ── the loop's decisions ─────────────────────────────────────────────────

def test_headroom_needs_a_gap_to_the_gold_reward():
    assert not reward.has_headroom(0.5, 0.5, 0.95)          # capped: nothing to learn
    assert not reward.has_headroom(0.5, 0.51, 0.95)         # inside the margin
    assert reward.has_headroom(0.5, 0.75, 0.95)
    assert not reward.has_headroom(0.96, 1.0, 0.95)         # solved already
    assert reward.has_headroom(0.5, None, 0.95)             # gold reward not consulted
    assert not reward.has_headroom(0.95, None, 0.95)
    assert reward.has_headroom(0.5, 0.52, 0.95, margin=0.0)


def test_probe_stops_a_close_whose_samples_match_the_greedy_reply():
    assert not reward.worth_sampling(0.5, [0.5, 0.5])
    assert not reward.worth_sampling(0.5, [0.5 + 1e-9, 0.5])
    assert not reward.worth_sampling(0.5, [])
    assert reward.worth_sampling(0.5, [0.5, 0.25])          # a worse sample is signal too
    assert reward.worth_sampling(0.5, [1.0, 0.5])
    assert reward.worth_sampling(0.3333, [0.3334])          # rewards are rounded to 4 places


def test_leave_one_out_advantages():
    assert reward.loo_advantages([1.0, 0.0]) == [1.0, -1.0]
    adv = reward.loo_advantages([0.5, 0.5, 0.5, 0.5, 1.0])
    assert adv == pytest.approx([-0.125, -0.125, -0.125, -0.125, 0.5])
    rewards = [0.2, -1.0, 0.75, 0.75, 0.1]
    old = [r - (sum(rewards) - r) / (len(rewards) - 1) for r in rewards]     # rl.py's line
    assert reward.loo_advantages(rewards) == pytest.approx(old)
    assert sum(reward.loo_advantages(rewards)) == pytest.approx(0.0)
    assert reward.loo_advantages([0.4, 0.4, 0.4]) == pytest.approx([0.0, 0.0, 0.0])
    assert reward.loo_advantages([0.7]) == [0.0] and reward.loo_advantages([]) == []
    assert reward.has_signal([0.5, 0.25]) and not reward.has_signal([0.5, 0.5]) and not reward.has_signal([0.5])


def test_gradient_rows_leave_out_zero_advantages_only():
    assert reward.gradient_rows([0.5, -0.125, -0.125, -0.125, -0.125]) == [[0, 1], [2, 3], [4]]
    adv = reward.loo_advantages([1.0, 0.5, 0.0])            # the middle reply sits on its baseline
    assert adv[1] == 0.0 and reward.gradient_rows(adv) == [[0, 2]]
    assert reward.gradient_rows([0.0, 0.0]) == []
    assert reward.gradient_rows([0.1, 0.2, 0.3], width=1) == [[0], [1], [2]]
    # every reply with a nonzero advantage is in exactly one chunk
    adv = [0.3, 0.0, -0.1, -0.2, 0.0]
    assert sorted(i for chunk in reward.gradient_rows(adv) for i in chunk) == [0, 2, 3]


def test_default_max_tokens_covers_the_gold_reply(train_worlds, dev_worlds):
    """rl.py's default --max-tokens (448) against the longest gold reply at 4 chars a token."""
    longest = max(reward.reply_tokens_estimate(reward.episode(s, "paraphrase", w))
                  for w in [None, *train_worlds, *dev_worlds] for s in TRAIN_SEEDS)
    assert 200 < longest < 448 / 1.25
    source = (HERE / "rl.py").read_text(encoding="utf-8")
    assert '"--max-tokens", type=int, default=448' in source
