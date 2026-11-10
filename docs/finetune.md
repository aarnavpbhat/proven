# Fine-tuning a small local proposer

This note records an attempt to fine-tune a small open-weight model
(`mlx-community/Qwen2.5-3B-Instruct-4bit`, LoRA adapters trained with `mlx-lm`) to do the one
job Proven gives a model: propose. The code is in [`training/`](../training/README.md).

## Summary

- Trained on 1,000 closes from Proven's default synthetic world, the 3B model drafts lessons as
  well as the generator's own gold proposals on that world's test split: 92.5% of held claims
  decided on held-out phrasing and 82.3% on the paraphrase tier, against 88.3% and 74.0% for
  Claude Sonnet 5.5 on the same closes. No control FAIL and no unsafe PASS in any run.
- **That result is mostly memorisation.** A second model trained the same way, but with four
  cause families removed from its training data, drafted 1 to 2 lessons for those causes and
  left about 30% of their held claims decided, against about 95% (held-out phrasing) for the
  model that had seen them. The single-world model learned which bookkeeping words go with
  which of that world's eighteen causes. It did not show that it can supply such words for a
  cause it has not met.
- The untuned base model drafted no usable lesson at all, so the fine-tune is doing something;
  the ablation says what.
- The comparison that counts is therefore a different one: eleven "unseen" worlds, each with its
  own accounts, vendors, memo wording and causes, written by a different model from the 91
  worlds a second adapter is trained on. Its protocol was fixed before any model was scored.
  The ceiling and the Sonnet bar on it are measured (below). The fine-tuned models' rows are
  `TODO(main)`.
- Reinforcement learning against the checker's reward is implemented and has no result. One
  run was stopped after 4 of 40 steps.

## 1. The task, and what the proposer sees

Proven checks month-end variance commentary against the ledger. A **close** is one written
explanation plus the two periods' transactions. Each sentence becomes a **claim**, and the
deterministic checker gives each claim PASS, FAIL or REVIEW. The model proposes, the ledger
decides: a **proposer** never issues a verdict.

The proposer receives the explanation text and the ledger's chart of accounts and returns
JSON: for each sentence, the claim (the sentence quoted, the account, the figures, the stated
reason) and **search terms**, the words a bookkeeper would plausibly have written in the memo
or vendor field for that reason. The prompt is exactly the one `proven/openweight.py` sends
(`proven.llm.SYSTEM` and `proven.llm.payload(text, ledger)`).

A claim whose support rests only on the model's terms waits in REVIEW. A reviewer can confirm
"this stated reason goes with these terms" once, as a **lesson**; from then on the written
rules bind those words and no model runs at check time. So a proposer is scored by the lessons
it drafts. `python -m proven teach-sim` (`proven/teachsim.py`) plays a careful reviewer: it
teaches from the first half of a set of test closes, confirming only terms that matched the
ledger on explanations the generator labels correct, and then measures the second half with
the rules plus those lessons. Terms used in the tables:

- **Decided**: the share of held claims that end PASS or FAIL without a person.
- **Controls** are correct explanations (should PASS); **defects** are wrong ones (should not).
- **Control FAIL** (a correct explanation failed) and **unsafe PASS** (a wrong one passed) are
  the two kill criteria. Both must be 0.
- **Oracle**: the generator's gold proposals fed through the same loop. It is the ceiling for
  any proposer. Because the simulated reviewer reads the label, every figure here is an upper
  bound on a careful person, not a forecast.
- Phrasing tiers: **heldout** phrases are never in any training data; **paraphrase** phrases
  describe the cause without using the books' words, with disjoint train and test halves.

## 2. Data and leakage controls

Single-world set (`training/build_dataset.py`): 1,000 training rows, 500 in the `seen` tier and
500 in the train half of the paraphrase tier, plus 60 validation rows. Each row is one close;
the target is the generator's gold proposal list as JSON.

- Only train-split seeds are generated (`seed % 5 != 0`). `HELDOUT` and `PARAPHRASE_TEST`
  phrases are never drawn.
- `training/test_leakage.py` regenerates every row from the manifest byte for byte, and asserts
  that no held-out phrase, no test-half paraphrase and no test-split explanation (first 440
  test seeds, every tier) appears in any message, and that the prompt equals a captured
  `openweight` request.
- For the ablation set (`--exclude-keys`), every close mentioning a held-out cause is dropped,
  and the test asserts that none of those causes' phrases, and none of the ledger terms only
  those causes leave, appears anywhere.

Training (`training/lora-config.yaml`, `training/train.sh`): LoRA rank 16 on the last 16
layers (13.304M trainable parameters, 0.431% of the model), learning rate 1e-4 with cosine
decay, batch 2 with gradient accumulation 2, loss on the reply only, 500 iterations. Hardware
was one Apple M5 Pro laptop with 24 GB of memory, exactly one GPU job at a time (a lock
directory), with MLX memory capped by `training/memguard.py`. The run took 1593 seconds;
validation loss went from 0.810 at iteration 1 to 0.001 at iteration 500. A validation loss
that close to zero on templated data is itself a hint of memorisation.

## 3. Single-world results

Default world, test split, 220 closes: 110 taught from, 110 measured with the rules (265
claims: 195 controls and 70 defects). All rows are the fully taught line (110 closes). Untaught,
the held half sits at 11.3% decided.

| Phrasing | Proposer | Lessons | Decided | Reward | Controls passed | Control FAIL | Unsafe PASS | Defects caught |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| heldout | Qwen2.5-3B, untuned (`proven-qwen3b-base`) | 0 | 11.3% | 0.168 | 0/195 | 0 | 0 | 50/70 |
| heldout | Qwen2.5-3B, ablation (`proven-qwen3b-ablation`) | 29 | 76.6% | 0.824 | 157/195 | 0 | 0 | 65/70 |
| heldout | Qwen2.5-3B, single-world (`proven-qwen3b-sft`) | 37 | 92.5% | 0.987 | 195/195 | 0 | 0 | 70/70 |
| heldout | Claude Sonnet 5.5 | 36 | 88.3% | 0.942 | 184/195 | 0 | 0 | 70/70 |
| heldout | Oracle | 36 | 92.5% | 0.987 | 195/195 | 0 | 0 | 70/70 |
| paraphrase | Qwen2.5-3B, untuned | 0 | 11.3% | 0.165 | 0/195 | 0 | 0 | 50/70 |
| paraphrase | Qwen2.5-3B, ablation | 52 | 67.5% | 0.730 | 135/195 | 0 | 0 | 63/70 |
| paraphrase | Qwen2.5-3B, single-world | 63 | 82.3% | 0.878 | 170/195 | 0 | 0 | 68/70 |
| paraphrase | Claude Sonnet 5.5 | 59 | 74.0% | 0.793 | 152/195 | 0 | 0 | 64/70 |
| paraphrase | Oracle | 64 | 83.4% | 0.889 | 173/195 | 0 | 0 | 68/70 |

- The single-world model matches the oracle on held-out phrasing and is within about one point
  of it on the paraphrase tier. Section 4 explains why this should not be read as "a 3B model
  beats Sonnet".
- The untuned model extracted nothing the harness would admit: in the benchmark every one of
  its 283 claims was counted "not extracted" (mean reward -0.247), so there was nothing to teach
  from. Its 11.3% is the rules alone.
- With the default guard and no lessons (`python -m proven benchmark`, 110 closes), the
  single-world model decides 9.9% (held-out) and 10.2% (paraphrase) with 0 control FAIL and 0
  unsafe PASS. The guard, not the model, is what keeps these at zero.
- At 440 closes (220 taught, 220 measured) the bars are: Sonnet 88.6% held-out and 83.0%
  paraphrase; Opus 85.8% and Haiku 73.2% held-out; oracle 92.6% and 87.1%. The fine-tuned
  models were measured at 220 only.

## 4. The ablation: what the model actually learned

The ablation model had the same recipe and row count, but no training close mentioned any of
four cause families: `litigation`, `migration`, `offsite`, `d_and_o`. `training/by_cause.py`
splits the same teach-sim by cause. On the held half there are 64 claims about those four
causes and 201 about the rest.

| Model | Phrasing | Held-out causes: taught claims with a matching term | Lessons | Decided | Other causes: decided |
|---|---|---:|---:|---:|---:|
| single-world (saw the causes) | heldout | 55/59 | 8 | 61/64 (95.3%) | 184/201 (91.5%) |
| ablation (never saw them) | heldout | 16/59 | 1 | 19/64 (29.7%) | 184/201 (91.5%) |
| single-world | paraphrase | 54/59 | 12 | 50/64 (78.1%) | 168/201 (83.6%) |
| ablation | paraphrase | 14/59 | 2 | 18/64 (28.1%) | 161/201 (80.1%) |
| untuned (no lessons) | either | 0/59 | 0 | 11/64 (17.2%) | 19/201 (9.5%) |

This is a negative finding and it is stated as one. On causes it had not been trained on, the
ablation model proposed a term that matched the ledger for 16 of 59 taught claims, where the
model that had seen them managed 55 of 59. The rules alone already decide 11 of those 64 held
claims, so the ablation model's lessons added 8 claims on held-out phrasing and 7 on
paraphrase. On the causes both models saw, the two are identical on held-out phrasing.

In plain terms: the default world has eighteen causes and a fixed set of vendors and memo
wordings. A model trained on closes from that world can score at the ceiling by remembering
which memo words go with which cause. That is not the skill a reviewer needs, and a test in
the same world cannot tell the two apart. The single-world numbers in section 3 are best read
as "the model can learn the format and one world's vocabulary", nothing more.

## 5. The unseen-worlds benchmark

**How the worlds were made.** A world (`proven/worlds.py`) is a JSON file with its own chart
of accounts, vendors, memo wording and causes, plus plain phrases (the books' own words) and
oblique phrases (the cause described without any word the books use). A hosted model was
asked for one world per industry (`training/author_worlds.py`). A validator then dropped any
phrase or account that broke the generator's rules, and refused worlds left too thin.

| Set | Worlds | Written by | Used for |
|---|---:|---|---|
| Training | 91 | Claude Sonnet 5.5 (86) and Claude Haiku 5.5 (5), from `industries-train-*.txt` | training rows |
| Dev | 4 | Claude Sonnet 5.5, from `industries-dev.txt` | validation loss only |
| Unseen (measured) | 11 | Claude Opus 5.5, from the disjoint `industries-unseen.txt` | results below |

Twelve unseen industries were requested; one request was refused by the model, leaving eleven.
The measured worlds are committed in `proven/examples/worlds/unseen/`.

**Multi-world training set** (`training/build_worlds_dataset.py`): 3,027 rows, being 30 closes
from each of the 91 training worlds (a quarter plain, the rest oblique) plus 300 default-world
rows; 60 validation rows from the dev worlds. The builder refuses a path inside the measured
suites, and dropped 3 closes whose stated reason was word for word a phrase some measured
world uses. The multi-world adapter (`proven-qwen3b-worlds`) trains for 1,200 iterations
starting from the single-world adapter.

**Overlap audit** (`training/world_overlap.py`, an audit and not a filter). Across the 11
measured worlds there are 168 causes with 965 distinguishing memo words between them. Of those
words, 288 were never a target term in the training worlds, the dev worlds or the default
world. No cause has all of its terms new, and 28 causes have no new term at all. 4 vendor
names and 16 phrases also occur in the training material (for example "the conversion project"
and "the data migration"); 0 memo lines are shared. Single bookkeeping words such as "repair"
are expected to recur, since learning which words books use is the point. The unseen suite is
therefore new worlds, not new vocabulary throughout, and a result on it should be split by
whether a cause's terms were seen (`--json` lists them).

**Protocol, fixed before any model was scored on the suite.** In each world, 100 test-split
closes: 50 taught from and 50 measured with the rules. Each world is taught separately, so no
lesson crosses worlds. Both phrasing tiers are reported. Kill criteria: control FAIL = 0 and
unsafe PASS = 0. Across the 11 worlds the measured halves hold 998 controls and 363 defects.
Untaught, 10.5% of claims are decided.

Fully taught (50 closes per world):

| Proposer | Phrasing | Lessons | Decided | Reward | Controls passed | Control FAIL | Unsafe PASS | Defects caught | Worst..best world |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Oracle (ceiling) | heldout | 325 | 89.5% | 0.960 | 963/998 | 0 | 0 | 363/363 | 86.7%..92.5% |
| Claude Sonnet 5.5 | heldout | 306 | 82.3% | 0.881 | 871/998 | 0 | 0 | 349/363 | 68.0%..90.0% |
| Qwen2.5-3B, single-world | heldout | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) |
| Qwen2.5-3B, multi-world | heldout | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) |
| Oracle (ceiling) | paraphrase | 536 | 76.1% | 0.827 | 799/998 | 0 | 0 | 346/363 | 72.5%..81.4% |
| Claude Sonnet 5.5 | paraphrase | 444 | 63.5% | 0.697 | 644/998 | 0 | 0 | 326/363 | 54.3%..71.1% |
| Qwen2.5-3B, single-world | paraphrase | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) |
| Qwen2.5-3B, multi-world | paraphrase | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) | TODO(main) |

Sonnet sits 7.2 points under the ceiling on held-out phrasing and 12.6 points under it on the
paraphrase tier, a wider gap than in the default world, and its weakest worlds
(`municipal-water-utility` at 68% on held-out, `quarry-and-aggregates-supplier` at 54% on
paraphrase) are well below its best. The single-world row is the
control for section 4: if memorisation is the whole story it should fall far below Sonnet
here. The multi-world row is the claim under test.

Multi-world training run (final validation loss, wall time): TODO(main).
Multi-world model on the default world's test split (does it give up the section 3 result?): TODO(main).

## 6. Constrained decoding: replies that are admissible by construction

A proposer's reply makes three promises that can be checked against the request alone: it is
the schema's JSON, every copied field (`quote`, the figures, `reason_text`) is text from the
explanation, and `account` is a name on the chart that was sent. A fine-tuned model keeps
them most of the time. `training/constrain.py` makes it keep them every time, by removing
from each next-token choice every token that would break one.

- **How.** The reply is described by a small automaton over its bytes. Inside a copied field
  the automaton's state is the set of positions in the explanation that the text so far could
  end at, so a byte is allowed only if it continues a real substring. The tokens allowed at a
  step are found by walking the vocabulary's byte trie in step with the automaton, which
  handles tokens that span several pieces of the layout (Qwen's vocabulary has `", "` and
  ` [{"` as single tokens) with no special cases. The mask is added to the logits, so it works
  for greedy decoding and for sampling alike.
- **What is guaranteed.** A finished reply parses, has at most 16 claims and 8 terms per
  claim, quotes a non-empty span of one line of the explanation, copies its figures and reason
  from the explanation, and names a chart account or none. `training/test_constrain.py` checks
  this with random walks through the mask, and checks that every gold reply stays inside it.
- **What is deliberately not constrained.** Search terms are the model's guess at ledger
  wording it is never shown (`proven.llm.payload` sends no transactions, vendors or memos).
  There is nothing on the model's side of that boundary to copy them from, so they stay free
  text. Constraining them to the ledger would leak the answer and was rejected.
- **Cost.** On the real tokenizer, 66 gold replies (16,621 decoding steps) stayed inside the
  mask at a mean of 0.73 ms per step for the mask itself. End to end the 3B model took about
  2.5 s per close constrained against 1.6 s unconstrained, in batches of 12.
- **Fallback.** An explanation or account name containing a double quote or a backslash would
  need JSON escapes inside copied text. Those requests are decoded unconstrained and counted.

The idea of masking logits so that only spans of the input can be produced follows the
LogitMatch decoding of "Strategies for Span Labeling with Large Language Models"
(arXiv 2601.16946) and copy-constrained generation (CopyGen); the schema half is ordinary
grammar-constrained decoding. What is specific here is that the constraint is exactly the
admission rule the checker applies afterwards, so the decoder and the verifier agree on what a
well-formed proposal is.

Result on the unseen suite: TODO(main).

## 7. Pooling sampled replies

`training/consensus.py` pools several replies to one close. Two ways were studied.

- **A blind vote** (`merge_votes`): the greedy reply plus K-1 sampled replies; claims are
  aligned by quote and each claim keeps the terms most replies proposed, up to a cap. It never
  looks at the ledger.
- **Ledger-aware selection** (`merge`): the same pool, but terms that find transactions in the
  ledger are preferred.

On simulated replies (a noise model over gold terms, 200 paraphrase closes, K = 4) pooling
gained 0.06 to 0.11 reward over one reply. Ledger-aware selection was within 0.012 of the
blind vote and, in every row, left more cases where a reviewer who confirms everything would
be shown a wrong claim as supported. It can also move a correct FAIL to REVIEW. It never
produced a PASS or FAIL by itself under the default policy, because support that rests on
model terms always waits in REVIEW. **It is kept as study code and is not used.** The blind
vote with a cap of three terms had no more such cases than a single reply.

Result with real model samples: TODO(main).

## 8. Reinforcement learning: status

`training/reward.py` scores one reply by what the checker and a simulated reviewer do with it,
including a careless reviewer who confirms everything (a reply whose terms would let a wrong
explanation PASS costs -1). `training/rl.py` is RLOO, which is REINFORCE with a leave-one-out
baseline: several replies are sampled per close, each reply's advantage is its reward minus
the mean of the others, and the step is plain SGD on a norm-clipped gradient. Only train-split
closes are scored, and only closes the greedy reply does not already solve are trained on.

What happened: an earlier version that used Adam collapsed the policy in two steps. The
current version was started from the single-world adapter with 40 steps planned. Its step-0
validation reward was 0.8394 on 32 closes. It was stopped by hand after 4 steps, because each
step took about 9 minutes and it was optimising the wrong target (the memorised world). No
validation was run after step 0. **No RL result is claimed.**

Multi-world RL result: TODO(main).

## 9. What went wrong

- A bug in the GPU lock let two jobs overlap for about ten minutes. It is fixed.
- An earlier crash of the laptop lost some local runs. The spend log restarts after it.
- In the first world-authoring attempt, the hosted model's thinking tokens used up the whole
  output allowance. That attempt cost $5.79 and produced 4 usable worlds before it was fixed.
- The single-world model's run on the unseen suite was started and has no result file yet.

## 10. Limits

- **The worlds are synthetic and from related model families.** Training worlds were written by
  Sonnet and Haiku, measured worlds by Opus. A different model and disjoint industries are a
  weaker separation than a different company's real books.
- **Sentences come from templates.** A world changes the accounts, vendors, memos and phrases,
  not the sentence frames or the ledger generator. A proposer can still learn the frames.
- **Vocabulary overlaps** (section 5): 28 of 168 measured causes have no term new to training.
- **The hand-written suite is tiny**, and no fine-tuned model has been run on it. No real
  company's commentary has been checked.
- **One seed, one base model, one recipe.** No run was repeated, so no variance is known, and
  differences of a point or two between rows mean little. Measured halves are 110 closes in
  the default world and 50 per world in the unseen suite.
- **The reviewer is simulated** and reads the answer key. Every "decided" figure is an upper
  bound on a careful reviewer.

## 11. How to reproduce

Setup, and the commands for the single-world model, the ablation and the untuned base
(`build_dataset.py`, `train.sh` with 500 iterations, `serve.sh`, `eval.sh`), are in
[`training/README.md`](../training/README.md). Run one GPU job at a time. Below, `$PY` is the
project's Python, `$MLX_PY` the mlx-lm environment's, `$FT` a scratch directory outside the
repo, and `BASE=mlx-community/Qwen2.5-3B-Instruct-4bit`.

Bars. The oracle is offline; the Claude rows need the proposal cache or a live run (the run
behind section 5 logged $14.69, so set the budget above that):

```sh
$PY -m proven teach-sim --extractor oracle --phrasing heldout --n 220
$PY -m proven teach-sim --extractor oracle --worlds unseen --phrasing heldout
$PY training/warm_worlds.py --extractor claude --model claude-sonnet-5-5 --suite unseen \
    --phrasings heldout paraphrase --n 100 --workers 4 --allow-network --usd-budget <usd>
$PY -m proven teach-sim --extractor claude --model claude-sonnet-5-5 --worlds unseen --phrasing heldout
```

Worlds, the multi-world set and the audit:

```sh
$PY training/author_worlds.py --role train --model claude-sonnet-5-5 \
    --industries training/industries-train-a.txt --out training/worlds/train --usd-budget 8
$PY training/author_worlds.py --role measure --model claude-opus-5-5 \
    --industries training/industries-unseen.txt --out proven/examples/worlds/unseen --usd-budget 8
$PY training/build_worlds_dataset.py --out $FT/data/worlds --worlds training/worlds/train \
    --dev training/worlds/dev --per-world 30 --default 300 --valid 60
$PY training/world_overlap.py --train training/worlds/train training/worlds/dev --json unseen-overlap.json
```

Multi-world training and measurement. `train.sh` has no resume option, so this run called
`mlx_lm.lora` directly, with `run-config.yaml` a copy of `lora-config.yaml` set to 1,200
iterations:

```sh
$MLX_PY training/memguard.py mlx_lm.lora --config $FT/adapters/qwen3b-worlds/run-config.yaml \
    --model $BASE --data $FT/data/worlds --adapter-path $FT/adapters/qwen3b-worlds \
    --resume-adapter-file $FT/adapters/qwen3b-sft/adapters.safetensors
$MLX_PY training/batch_propose.py --model $BASE --adapter $FT/adapters/qwen3b-worlds \
    --name proven-qwen3b-worlds --suite unseen --n 100
$PY -m proven teach-sim --extractor openweight --model proven-qwen3b-worlds --worlds unseen --phrasing heldout
```

RL, as started (not run to completion; see section 8):

```sh
$MLX_PY training/rl.py --model $BASE --init $FT/adapters/qwen3b-sft --out $FT/adapters/qwen3b-rl \
    --steps 40 --batch 2 --samples 4 --temp 1.0 --valid 32 --eval-every 10
```
