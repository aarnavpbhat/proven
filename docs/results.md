# Results in detail: a model proposing, and what lessons buy

The headline tables are in the [README](../README.md#results). This page keeps the runs behind them.
The fine-tuning results are in [finetune.md](finetune.md) and the lesson rules in [teaching.md](teaching.md).

## With a model proposing

Same 440-close test split, held-out phrasing. The Claude rows replay cached answers from one
live run of `claude-sonnet-5-5` (`--extractor claude --model claude-sonnet-5-5`). The oracle
(`--extractor oracle`) feeds the generator's own gold proposals through the checker, so it is the
ceiling for any model.

| Proposer | Guard | Decided | Mean reward | Correct passed | Correct **failed** | **Unsafe PASS** |
|---|---|---:|---:|---:|---:|---:|
| Rules | default | 11.0% | 0.164 | 0 / 810 | 0 | 0 |
| Claude Sonnet | default | 11.0% | 0.180 | 0 / 810 | 0 | 0 |
| Oracle | default | 11.0% | 0.186 | 0 / 810 | 0 | 0 |
| Claude Sonnet | `--anchor-model-terms` | 38.1% | 0.431 | 283 / 810 | 0 | **12** |
| Oracle | `--anchor-model-terms` | 60.7% | 0.690 | 542 / 810 | 0 | 0 |

Three things follow.

- **A model's terms may not fail a claim either.** Before the guard covered FAIL, the same Sonnet
  run failed 68 correct explanations, every one on model-proposed terms that caught only one of
  a cause's two invoices. Those claims now go to REVIEW (`REASON_FOUND_ONLY_BY_MODEL_TERMS`).
- **Letting model terms anchor a PASS is unsafe with a real model.** The experimental
  `--anchor-model-terms` policy is clean on gold terms and produces 12 unsafe PASSes on Sonnet's:
  six where a vague reason ("the second location") drew a term that matched a neighbouring
  cause's invoices, six where the terms covered the change and hid a misbooked transaction. It is
  off by default and should stay off.
- **A model must not be able to remove what a sentence says.** A local 7B model sometimes returned
  a claim with the stated reason left out; the claim was then checked on its amount alone, and two
  wrong explanations passed. `admit()` now keeps any reason or figure the rules can read in the
  sentence when a proposal omits it. A proposal can add to the reading, never subtract from it.
- **The route across the gap is a person, once.** In the Sonnet run 710 of the 810 correct
  explanations sit in REVIEW only because their support rests on model terms. A reviewer who
  confirms such a term teaches it to the learned lexicon (`learned.py`, "Teach Proven" in the
  console); from then on the written words bind and the ledger decides.

## Local open-weight models, untuned

Local open-weight models, through Ollama on an M5 Pro, on 40 held-out closes (77 controls, 24
defects). No model run broke a kill criterion; what differs is how many usable lessons each
drafts from the same 40 closes, and what those lessons do on the next 40:

| Proposer | Decided, default guard | Control FAIL | Unsafe PASS | Lessons from 40 closes | Decided on the next 40 after teaching |
|---|---|---|---|---|---|
| llama3.1:8b | 10.9% | 0 | 0 | 1 | 10.6% |
| qwen2.5:7b | 10.9% | 0 | 0 | 4 | 17.3% |
| qwen2.5:14b | 10.9% | 0 | 0 | 7 | 22.1% |
| qwen3.5:9b (q4) | 9.9% | 0 | 0 | 7 | 24.0% |
| Claude Sonnet | 10.9% | 0 | 0 | 31 | 71.2% |

(Untaught, the next 40 closes sit at 9.6% decided. qwen3.5:9b failed to extract 3 of the 24
defective claims at all; those count as missed, not passed.) So the proposer's quality matters
after all, but as a drafter of lessons rather than as a judge: that is the place a stronger or
fine-tuned model would pay.

The first run of this simulation passed three wrong explanations. A correct lesson
("board coverage" → d&o) left the stray word "coverage" free to match an unrelated cyber-coverage
invoice, and together they covered a movement the stated reason only half explained. A lesson now
replaces its trigger's words instead of adding to them (`claims.anchored_terms`). It also keeps
only the ledger words its own claim's PASS needs (`learned.trim_terms`), after a guessed vendor
name, confirmed along with the right word, later carried two wrong explanations to PASS on a
new suite. A third rule refuses a lesson whose words cover only part of a vendor's new charges.
The rules, the incidents behind them and their cost are in
[docs/teaching.md](teaching.md#lessons-keep-only-the-words-their-cause-needs).

There is also a `paraphrase` tier (`--phrasing paraphrase`) whose train and test phrases are
disjoint from each other and from the held-out tier, and a hand-written close
(`proven/examples/`, a coffee roaster) whose answer key was committed before Proven ran on it.
No defective sentence in it passes; several correct ones go to REVIEW over one unmatched word.
