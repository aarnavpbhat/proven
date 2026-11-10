# Fine-tuning a small local proposer

This note records an attempt to fine-tune a small open-weight model
(`mlx-community/Qwen2.5-3B-Instruct-4bit`, LoRA adapters trained with `mlx-lm`) to do the one
job Proven gives a model: propose. The code is in [`training/`](../training/README.md).

## Summary

- **No fine-tuned model here beats Claude Sonnet 5.5 on worlds it was not trained on.** On
  eleven unseen worlds (new industries, written by a different model, protocol fixed in
  advance) the best local model, a 3B model with LoRA adapters, leaves 54.4% of held claims
  decided on held-out phrasing and 40.7% on the paraphrase tier. Sonnet leaves 81.7% and 63.3%;
  the ceiling is 89.3% and 76.0%. The local model loses in all eleven worlds. No run of any
  proposer has a control FAIL or an unsafe PASS under the current lesson rules, which were
  tightened twice during this work because runs on new worlds did have them (section 9).
- **In the world it was trained on, the same base model scores at the ceiling, and that is
  memorisation.** On the unseen worlds that single-world model decides 20.9%. Trained on 1,000 closes of the default world it decides 92.5% and 82.3%
  against Sonnet's 88.3% and 73.2%. A copy trained with four cause families removed decided
  about 30% of those causes' claims against about 95% for the model that had seen them
  (section 4). The unseen-worlds benchmark was built because of that finding.
- **The first multi-world model lost for a reason that could be measured and partly fixed.**
  Its blind search terms found the true cause for 33% of claims where Sonnet's found 84%. The
  training targets named vendors and world-specific words that no request predicts, so the
  model had learned to invent ledger-looking words. Targets rebuilt as "guessable and true" (a
  blind teacher's guesses, kept only where the cause's own ledger lines contain them) doubled
  the rate on the dev worlds, 18.3% to 37.7%, and moved the unseen result from 44.8% to 54.4%.
- **What remains is knowledge, not format.** Asked for terms only, the untuned 3B base finds
  2.6% of causes and the untuned 7B base 32.7%, against Sonnet's 80.1%. A 7B fine-tune was
  attempted and failed numerically. Section 6 has the numbers.
- **A second suite, kept unopened, found two safety gaps in Proven itself.** Lessons drafted
  from Sonnet's proposals let 2 wrong explanations PASS, and lessons drafted from the local
  model's failed 2 correct ones and passed 1 wrong one. In both, a guessed word that matched
  the wrong lines was confirmed along with a right one. A lesson now keeps only the words its
  PASS needs, none that matched only routine lines, and must cover all of a vendor's new
  charges or none (section 9). Every table here uses those rules; they cost the bars 0.0 to
  0.8 points.
- **Constrained decoding** makes every reply admissible by construction (valid schema, copied
  fields are substrings of the explanation, accounts come from the chart) at 0.73 ms per
  decoding step (section 7).
- Not done: a 7B result, RL at any scale that would mean something, a real company's books.

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
| paraphrase | Claude Sonnet 5.5 | 58 | 73.2% | 0.784 | 150/195 | 0 | 0 | 64/70 |
| paraphrase | Oracle | 64 | 83.4% | 0.889 | 173/195 | 0 | 0 | 68/70 |

- All rows were re-scored under the lesson rule of section 9. Only Sonnet's paraphrase row
  moved (it was 59 lessons, 74.0%, 152/195).
- The single-world model matches the oracle on held-out phrasing and is within about one point
  of it on the paraphrase tier. Section 4 explains why this should not be read as "a 3B model
  beats Sonnet".
- The untuned model extracted nothing the harness would admit: in the benchmark every one of
  its 283 claims was counted "not extracted" (mean reward -0.247), so there was nothing to teach
  from. Its 11.3% is the rules alone.
- With the default guard and no lessons (`python -m proven benchmark`, 110 closes), the
  single-world model decides 9.9% (held-out) and 10.2% (paraphrase) with 0 control FAIL and 0
  unsafe PASS. The guard, not the model, is what keeps these at zero.
- At 440 closes (220 taught, 220 measured) Sonnet decides 88.2% on held-out phrasing and the
  oracle 92.6% and 87.1% (held-out, paraphrase). Sonnet's paraphrase figure (83.0%), Opus
  (85.8%) and Haiku (73.2%) at that size were measured under the earlier lesson rule and not
  re-run. The fine-tuned models were measured at 220 only.

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
| Dev | 4 | Claude Sonnet 5.5, from `industries-dev.txt` | validation loss, and every choice between checkpoints, targets and decoding policies |
| Unseen (measured) | 11 | Claude Opus 5.5, from the disjoint `industries-unseen.txt` | results below |
| Sealed (measured) | 9 | Claude Opus 5.5, from `industries-sealed.txt` | a second measurement nobody inspected, section 6 |

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

Fully taught (50 closes per world), under the lesson rule of section 9:

| Proposer | Phrasing | Lessons | Decided | Reward | Controls passed | Control FAIL | Unsafe PASS | Defects caught | Worst..best world |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Oracle (ceiling) | heldout | 325 | 89.3% | 0.960 | 963/998 | 0 | 0 | 363/363 | 86.4%..92.2% |
| Claude Sonnet 5.5 | heldout | 306 | 81.7% | 0.883 | 871/998 | 0 | 0 | 349/363 | 67.2%..90.0% |
| Qwen2.5-3B, single-world | heldout | 43 | 20.9% | 0.268 | 125/998 | 0 | 0 | 269/363 | 12.4%..29.2% |
| Qwen2.5-3B, multi-world, gold targets | heldout | 141 | 44.8% | 0.507 | 419/998 | 0 | 0 | 301/363 | 24.2%..63.4% |
| Qwen2.5-3B, multi-world, rebuilt targets | heldout | 185 | 54.4% | 0.603 | 528/998 | 0 | 0 | 321/363 | 31.7%..69.5% |
| Oracle (ceiling) | paraphrase | 536 | 76.0% | 0.827 | 799/998 | 0 | 0 | 346/363 | 72.5%..81.4% |
| Claude Sonnet 5.5 | paraphrase | 444 | 63.3% | 0.698 | 644/998 | 0 | 0 | 326/363 | 54.3%..71.1% |
| Qwen2.5-3B, single-world | paraphrase | 55 | 17.5% | 0.233 | 83/998 | 0 | 0 | 265/363 | 10.9%..22.8% |
| Qwen2.5-3B, multi-world, gold targets | paraphrase | 198 | 33.4% | 0.391 | 269/998 | 0 | 0 | 292/363 | 20.0%..41.6% |
| Qwen2.5-3B, multi-world, rebuilt targets | paraphrase | 251 | 40.7% | 0.468 | 364/998 | 0 | 0 | 299/363 | 16.7%..56.2% |

Sonnet sits 7.6 points under the ceiling on held-out phrasing and 12.7 points under it on the
paraphrase tier, a wider gap than in the default world, and its weakest worlds
(`municipal-water-utility` at 67% on held-out, `quarry-and-aggregates-supplier` at 54% on
paraphrase) are well below its best.

**The single-world model barely moves the needle here.** The model that scores at the ceiling
in its own world decides 20.9% and 17.5%, about ten points over no lessons at all (10.5%),
and returned no proposal for 69 of the 1,100 closes it was shown. That is the control section
4 asked for: what it had learned was one world.

**The multi-world model lost, in every world.** Trained on the generator's gold targets it
decided 44.8% of held claims against Sonnet's 81.7% on held-out phrasing and 33.4% against
63.3% on the paraphrase tier, and won 0 of 11 worlds on either. (Scored when the bars were
still 82.3% and 63.5%, the mean difference per world was -37.4 points, 95% bootstrap interval
-44.8 to -29.7, and -29.9 points, -33.3 to -25.7.) It kept both kill
criteria at zero and it copied sentences, accounts and figures correctly (2 of 1,086 closes
came back with no proposal). What it could not do is the one thing the benchmark isolates:
guess, blind, a word the books really use. Its training run also overfitted: validation loss
on the dev worlds was lowest at iteration 200 (0.395) and rose to 0.479 by iteration 1,200,
while training loss fell to about 0.04. Section 6 is the diagnosis and what was rebuilt.

**The rebuilt model also lost, by less.** With the targets of section 6 the same 3B base
decides 54.4% and 40.7%: 9.6 and 7.3 points more than the first model, both kill criteria at
zero, and still 27.3 points under Sonnet on held-out phrasing (95% interval -33.6 to -21.3)
and 22.7 under on paraphrase (-27.6 to -18.7), losing all 11 worlds on both tiers. No
fine-tuned model here beats the hosted bar on unseen worlds.

## 6. Why it lost, and what was rebuilt

**The measurement.** `training/hit_rate.py` asks the checker's own report one question about
every true explanation in the taught half of a suite: did the proposer's blind terms find the
cause (`SUPPORT_RESTS_ON_MODEL_TERMS`, the state a reviewer can confirm as a lesson)? It
needs no teaching run and is answered from the proposal cache.

| Proposer | Suite, phrasing | True claims | Cause found | Matched only routine lines | Matched nothing | No proposal |
|---|---|---:|---:|---:|---:|---:|
| Claude Sonnet 5.5 | unseen, heldout | 1,062 | 84.3% | 95 | 72 | 0 |
| Qwen2.5-3B, multi-world, gold targets | unseen, heldout | 1,062 | 33.1% | 230 | 473 | 8 |
| Claude Sonnet 5.5 | unseen, paraphrase | 1,062 | 76.5% | 115 | 135 | 0 |
| Qwen2.5-3B, multi-world, gold targets | unseen, paraphrase | 1,062 | 31.3% | 237 | 486 | 7 |

Teaching turns "cause found" into lessons almost one for one, so this table is the whole gap.

**The cause: targets no request predicts.** The generator's gold `search_terms` are the words
a cause really left in the books, most frequent first, and they include the vendor's name
when the vendor is new. For "a session on childhood adversity" the gold terms are `trauma`,
`informed`, `workshop`, `bridgeway`, `behavior`, `consulting`. Nothing in the request (the
sentence and the chart of accounts) predicts "Bridgeway". Trained on targets like that across
91 worlds, the model learned to emit ledger-looking words, not to reason from the sentence.
For that reason it proposed `childhood`, `adversity`, `conference`, `cascade`, `solutions`,
`trainers`: two words copied from the sentence (which an oblique phrase never shares with
the books), and "Cascade", a vendor-like word from its training worlds. Sonnet proposed
`adversity`, `trauma`, `ACEs`, `workshop`, `speaker`, `seminar`, `consultant`, `session`, and
two of those are in the books. The same pattern repeats across the suite: on average 6.0
single-word terms per claim from the model, of which one or two are invented proper nouns,
against 7.5 terms from Sonnet at 1.3 words each.

This diagnosis read the model's replies on the unseen suite, which is a use of measured data.
What follows was therefore designed from the mechanism, chosen on the dev worlds only, and
confirmed on a second measured suite that nobody had looked at (below).

**Rebuilt targets: guessable and true** (`training/teacher_terms.py`,
`build_worlds_dataset.py --teacher`). A hosted teacher (Sonnet) is shown exactly what a
proposer is shown, the account names and one stated reason, and guesses 8 terms. One request
holds at most one phrase per cause, so it cannot work out a cause's book wording from a
sibling phrase. 15,578 phrases of the 91 training and 4 dev worlds were labelled for $10.14.
Each training claim's terms are then, in order and up to 8:

1. the teacher's guesses that the cause's own vendor-and-memo lines really contain (guessable
   and true). 74% of labelled training claims have at least one;
2. the gold memo words that at least three training worlds use for some cause (`retrofit`,
   `overtime`, `pilot`: bookkeeping vocabulary a proposer can learn a prior over);
3. the teacher's other guesses, as filler.

A word found only in a vendor's name is never a target, a gold word one world alone uses is
left out unless fewer than three terms would remain, and a teacher guess that matches the
account's routine lines or restates the account is dropped. The ledger is used here to build
training labels for training worlds, as the gold labels always were. At inference nothing
changes: the proposer sees no transactions. `training/test_targets.py` pins the rules.

The same pass found six default-world rows in the first multi-world set whose reason ("the
data migration") is word for word a phrase three measured worlds also use; the builder's
phrase filter had only been applied to authored worlds. It now covers every row (18 closes
dropped), and the rebuilt set shares no reason with either measured suite.

**Result on the dev worlds** (held-out phrasing, 382 true claims in the taught halves; the
choice between models was made here and nowhere else):

| Proposer | Cause found |
|---|---:|
| Claude Sonnet 5.5 | 80.1% |
| Qwen2.5-3B, gold targets (the model that lost) | 18.3% |
| Qwen2.5-3B, rebuilt targets, 1,200 iterations | 37.7% |
| Qwen2.5-3B, untuned, asked for terms only | 2.6% |
| Qwen2.5-7B, untuned, asked for terms only | 32.7% |
| Qwen2.5-7B, untuned, vote of 4 samples, 8 terms | 38.5% |
| Qwen2.5-7B, untuned, all terms of 4 samples (no cap) | 45.3% |
| Qwen2.5-7B, rebuilt targets | no model: training failed (below) |

The rebuilt targets doubled the 3B model's rate, and its validation loss now falls for the
whole run (0.424, 0.407, 0.401, 0.397 at iterations 300 to 1,200) where the gold-target run's
rose after iteration 200: the new targets are learnable, the old ones were partly noise. The
replies also changed character: 8 terms per claim, synonyms and document names where there
had been invented vendors. They are still worse guesses than Sonnet's. For "the accident at
the loading area" the 3B model offers `tow`, `transmission`, `rebuild`, `brake`; Sonnet offers
`collision`, `body shop`, `insurance claim`, `towing`; the books say `dock collision bodywork
claim`. The last three rows (`training/term_probe.py`, the teacher's prompt, no training)
show why: this is a test of how much a model knows about how businesses describe what they
buy. The untuned 3B model knows almost nothing useful, the untuned 7B model about as much as
the tuned 3B, and pooling every term from four 7B samples with no cap still finds 45%.
(In the full teaching run on these dev worlds the rebuilt 3B model decides 55.2% of held
claims, Sonnet 83.0% and the oracle 90.7%.)

**Back in the default world** the rebuilt model decides 89.1% (held-out, 35 lessons, 186/195
controls) and 77.4% (paraphrase, 59 lessons, 158/195) on the 220-close test of section 3,
0 control FAIL and 0 unsafe PASS. That is above Sonnet there (88.3% and 73.2%) and below the
single-world model (92.5% and 82.3%), with 94 of its 3,176 training rows from that world: it
gave up some of the memorised score and kept most of it.

**The 7B attempt failed.** Fine-tuning `Qwen2.5-7B-Instruct-4bit` on the rebuilt set was tried
three times. At learning rates 1e-4 and 4e-5 the loss became NaN between iterations 40 and
50. With the gradient norm clipped at 1.0 (`training/lora_clip.py`) it stayed finite but rose
from 0.45 to 0.55 and stayed there until the run was stopped at iteration 170. About 40
minutes of the night went to it and there is no 7B adapter. The cause was not found.

**A second measured suite, unopened.** Because the diagnosis read unseen-suite replies, nine
more worlds were authored (Opus, `industries-sealed.txt`, industries disjoint from every other
list; 14 requested, 9 kept after one refusal, one invalid file and three skipped at the
budget) after the rebuilt targets were designed and before any model trained on them was
scored anywhere. Nobody read their contents; the only use made of them before the final
scoring was Sonnet's bar, which exposed the safety gap of section 9, and whose root-causing
was delegated with instructions to report the mechanism and nothing else. Their measured
halves hold 820 controls and 297 defects.

| Proposer | Suite, phrasing | Lessons | Decided | Controls passed | Control FAIL | Unsafe PASS | Worst..best world |
|---|---|---:|---:|---:|---:|---:|---|
| Oracle (ceiling) | sealed, heldout | 273 | 88.9% | 787/820 | 0 | 0 | 86.7%..91.7% |
| Claude Sonnet 5.5 | sealed, heldout | 255 | 80.5% | 700/820 | 0 | 0 | 74.4%..89.2% |
| Qwen2.5-3B, rebuilt targets | sealed, heldout | 163 | 57.8% | 481/820 | 0 | 0 | 38.3%..68.0% |
| Oracle (ceiling) | sealed, paraphrase | 449 | 76.1% | 655/820 | 0 | 0 | 72.5%..84.9% |
| Claude Sonnet 5.5 | sealed, paraphrase | 374 | 62.2% | 517/820 | 0 | 0 | 54.2%..73.0% |
| Qwen2.5-3B, rebuilt targets | sealed, paraphrase | 238 | 44.0% | 335/820 | 0 | 0 | 27.5%..55.3% |

The sealed suite agrees with the unseen one. The local model is 22.7 points under Sonnet on
held-out phrasing (95% interval -29.6 to -16.4) and 18.1 under on paraphrase (-23.7 to -12.6),
and loses all 9 worlds on both tiers. Its zeros in this table are not a blind result: when it
was first scored here, under the two-rule version of section 9, its lessons failed 2 correct
explanations on each tier and passed 1 wrong one on the paraphrase tier. Section 9 has what
that was and the third rule it led to; the decided shares moved by 0.2 and 0.3 points.

## 7. Constrained decoding: replies that are admissible by construction

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

CD_RESULT

## 8. Pooling sampled replies

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

K4_RESULT

## 9. Two safety gaps the second suite exposed, and the fixes

The first score on the sealed suite was Sonnet's, and it broke a kill criterion: 2 unsafe
PASSes on held-out phrasing (0 on the unseen suite, 0 for the oracle on both).

Both came from one lesson. For a true explanation about clearing a clogged well, Sonnet's
blind terms included the right word, `descaling`, and a plausible wrong one, `drilling`.
`drilling` is in the name of the contractor who bills that account every month. In the
teaching close it matched only the contractor's flat monthly line (+$689 of a $26,748
change); the pass rested on `descaling` alone. The simulated reviewer confirmed every term
that had matched anything, as `teachsim` then did and as the console's teaching queue
suggested. Once learned, a term is anchored: in two later closes where the same contractor's
*other* job was what really moved, `drilling` matched those lines, covered 99% of the
change, and carried a PASS for an explanation that named the wrong cause.

The safety gate did not catch it, and could not have: it replays a lesson against a
regression set drawn from the default world, where neither word occurs, and reported the
lesson untested, which it treats as acceptable. Across both measured suites and tiers, 7 of
Sonnet's 1,379 lessons held a term that also matched the account's other cause. The unseen
suite's zero was luck: none of its measured halves happened to contain the wrong-cause
sentence that would have triggered one.

**Fix** (`learned.trim_terms`, commit `0798d4e`; rules 1 and 2), applied wherever a lesson is confirmed:
the simulator, the console's teaching queue and teach endpoint, the hand-written suite and
the training reward. When a lesson makes its claim PASS, two rules are applied to that close:

1. a word whose every match is a routine line (same vendor and memo in both periods) that
   moved by less than materiality is dropped: it found the bill that recurs, not what moved;
2. every remaining word the PASS does not need is dropped, least-moved first.

The console refuses a lesson that would be narrowed and says which words to teach instead.
A lesson that turns a claim into a FAIL is left alone (showing that the flights bill was
flat is a legitimate way to refute "fewer customer visits").

| Suite, proposer, phrasing | Decided before | Decided after | Unsafe PASS before | after |
|---|---:|---:|---:|---:|
| sealed, Sonnet, heldout | 80.9% | 80.5% | 2 | 0 |
| sealed, Sonnet, paraphrase | 62.5% | 62.2% | 0 | 0 |
| unseen, Sonnet, heldout | 82.3% | 81.7% | 0 | 0 |
| unseen, Sonnet, paraphrase | 63.5% | 63.3% | 0 | 0 |
| unseen, oracle, heldout | 89.5% | 89.3% | 0 | 0 |
| default world, Sonnet, paraphrase | 74.0% | 73.2% | 0 | 0 |

Other cells are unchanged (sealed oracle, default-world oracle, default-world Sonnet
heldout), control FAIL is 0 everywhere, and `benchmark --phrasing seen` is unchanged at
90.1%. The lost decisions are wrong explanations that move from FAIL to REVIEW, except in the
default-world paraphrase cell, where 2 controls are lost because a lesson that depended on a
routine-only word is no longer taught. **Every table in this note uses the current rules**; the
unseen suite's original bars (82.3% and 63.5% for Sonnet, 89.5% and 76.1% for the oracle)
were fixed under the old one and are given here so the change is visible. The bars moved
down, by 0.1 to 0.6 points, not up.

**A second gap, from the weaker proposer.** Scoring the local model on the sealed suite under
those two rules gave 2 control FAILs on each tier and 1 unsafe PASS on the paraphrase tier
(and, looking back, 1 control FAIL at the 10- and 25-close steps of its unseen run, and the 1
control FAIL in Sonnet's dev-worlds run that had been put down to something else). All of
them come from one kind of lesson. It is taught from a hedged sentence ("primarily due to
X"), where the stated cause is 60 to 70% of the movement and the account's other cause also
moved. One proposed word matches one of the stated cause's two new charges; another matches
part of the other cause. Neither clears the hedged threshold of 50% alone, together they do,
the claim passes and both words are needed, so rule 2 keeps them. Later a plain "because of
X" about the same cause, which needs 75%, matches the one charge, reaches 49 to 60% and FAILs
as a partial explanation. And an explanation whose second charge was booked to another
account passes, because the one charge the lesson knows explains all of what is left in the
account and the lesson's words do not find the misbooked one.

3. (commit `814b2d5`) a lesson whose words cover only part of a vendor's new charges in a
   period (material, not routine) is refused, and rule 2 may not drop a word if that would
   leave such a part.

With all three rules every proposer cached here (the oracle, Sonnet, and three local models)
has 0 control FAIL and 0 unsafe PASS at every teaching step (0, 10, 25 and 50 closes) on the
unseen, sealed and dev suites, and at every step of the default world. The third rule moved
the local model's sealed results from 58.0% to 57.8% and from 44.3% to 44.0%, Sonnet's dev
result from 83.0% to 82.8%, and nothing else. `benchmark --phrasing seen` is unchanged.

What this does not establish. The three rules were written from breaches these suites
showed, the last one on the sealed suite itself, so the zeros above are the rules fitting
what they were written for, not an independent test. They are heuristics about what a
teaching close can show; other ways for a lesson to bind the wrong charges may exist that
these suites do not exercise. Rule 3 reads "a vendor's new charges in a period" as one job,
which is how these synthetic books are built and is only roughly true of real ones (where it
errs it refuses a lesson, and the claim stays with a person). The gate still cannot test
vocabulary its regression set has never seen, so "untested" should not be read as "safe".
Lessons already stored are not re-checked when loaded. And the simulated reviewer still reads
the label; a person can confirm a wrong explanation.

## 10. An idea that was tried and rejected: recalling confirmed words

A cause is described many ways and a lesson binds one of them. `training/recall_experiment.py`
lets the teaching loop add the words of lessons already confirmed for the same account to a
proposer's guesses, as guesses (the claim still waits for the reviewer, the lesson is still
trimmed). On the dev worlds, held-out phrasing:

| Proposer | Recall | Lessons | Decided | Control FAIL | Unsafe PASS | Wrong explanations shown as supported |
|---|---|---:|---:|---:|---:|---:|
| Qwen2.5-3B, rebuilt targets | no | 58 | 55.2% | 0 | 0 | 5 |
| Qwen2.5-3B, rebuilt targets | yes | 75 | 70.2% | **3** | **2** | 24 |
| Claude Sonnet 5.5 | no | 103 | 83.0% | 1 | 0 | 7 |
| Claude Sonnet 5.5 | yes | 113 | 89.3% | 0 | 0 | 50 |
| Oracle | no / yes | 110 | 90.7% | 0 | 0 | 5 / 49 |

It closes much of the gap between proposers, which says the gap is about finding each cause
once. It also breaks both kill criteria with the weaker proposer and multiplies the wrong
explanations a reviewer is shown as "supported" by five to ten. It is not in the product and
no result in this note uses it. (This table was measured before the third rule of section 9, which removes Sonnet's one
control FAIL without recall. The experiment was not repeated.)

## 11. Reinforcement learning: status

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

RL_RESULT

## 12. What went wrong

- A bug in the GPU lock let two jobs overlap for about ten minutes. It is fixed.
- An earlier crash of the laptop lost some local runs. The spend log restarts after it.
- In the first world-authoring attempt, the hosted model's thinking tokens used up the whole
  output allowance. That attempt cost $5.79 and produced 4 usable worlds before it was fixed.
- The first multi-world model was trained on targets it could not predict and lost by 37
  points (sections 5 and 6). Its training set also held six default-world rows whose reason a
  measured world uses word for word; the phrase filter had skipped default-world rows.
- The diagnosis of that loss read replies on the unseen suite. The sealed suite exists because
  of it.
- Three 7B training runs failed (section 6).
- Sonnet's lessons passed two wrong explanations on the sealed suite before the rule of
  section 9; the unseen suite had not shown it only because the triggering sentence was absent.
- A waiting loop in a job script was given a ten-minute limit by mistake and was restarted;
  nothing was lost. One script quoted a list of names as a single word and printed an empty
  row, which was re-run by hand.

## 13. Limits

- **The worlds are synthetic and from related model families.** Training worlds were written by
  Sonnet and Haiku, measured worlds by Opus. A different model and disjoint industries are a
  weaker separation than a different company's real books.
- **Sentences come from templates.** A world changes the accounts, vendors, memos and phrases,
  not the sentence frames or the ledger generator. A proposer can still learn the frames.
- **Vocabulary overlaps** (section 5): 28 of 168 measured causes have no term new to training.
- **The hand-written suite is tiny**, and no fine-tuned model has been run on it. No real
  company's commentary has been checked.
- **The safety gate cannot test words its regression set has never seen** (section 9).
- **One seed, one base model, one recipe.** No run was repeated, so no variance is known, and
  differences of a point or two between rows mean little. Measured halves are 110 closes in
  the default world and 50 per world in the unseen and sealed suites.
- **The reviewer is simulated** and reads the answer key. Every "decided" figure is an upper
  bound on a careful reviewer.

## 14. How to reproduce

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

Worlds, the teacher labels, the multi-world sets and the audit:

```sh
$PY training/author_worlds.py --role train --model claude-sonnet-5-5 \
    --industries training/industries-train-a.txt --out training/worlds/train --usd-budget 8
$PY training/author_worlds.py --role measure --model claude-opus-5-5 \
    --industries training/industries-unseen.txt --out proven/examples/worlds/unseen --usd-budget 8
$PY training/author_worlds.py --role measure --model claude-opus-5-5 \
    --industries training/industries-sealed.txt --out proven/examples/worlds/sealed --usd-budget 1.5
$PY training/teacher_terms.py --worlds training/worlds/train training/worlds/dev \
    --out $FT/teacher --usd-budget 14
$PY training/build_worlds_dataset.py --out $FT/data/worlds --worlds training/worlds/train \
    --dev training/worlds/dev --per-world 30 --default 300 --valid 60      # gold targets
$PY training/build_worlds_dataset.py --out $FT/data/worlds2 --worlds training/worlds/train \
    --dev training/worlds/dev --per-world 34 --default 100 --valid 60 --teacher $FT/teacher
$PY training/world_overlap.py --train training/worlds/train training/worlds/dev --json unseen-overlap.json
```

The sealed-suite authoring run spent $3.38 against its $1.50 cap, because requests already in
flight are not cancelled when the cap is reached.

Training. The gold-target run resumed from the single-world adapter; the rebuilt-target run
starts from the base model. `run-config.yaml` is a copy of `lora-config.yaml` set to 1,200
iterations:

```sh
$MLX_PY training/memguard.py mlx_lm.lora --config $FT/adapters/qwen3b-worlds/run-config.yaml \
    --model $BASE --data $FT/data/worlds --adapter-path $FT/adapters/qwen3b-worlds \
    --resume-adapter-file $FT/adapters/qwen3b-sft/adapters.safetensors
$MLX_PY training/memguard.py mlx_lm.lora --config $FT/adapters/qwen3b-worlds2/run-config.yaml \
    --model $BASE --data $FT/data/worlds2 --adapter-path $FT/adapters/qwen3b-worlds2
```

Measurement. A proposer is only ever shown the taught half of each split, so `--taught-only`
is enough for the teaching simulation. Dev worlds are a suite under `training/worlds`:

```sh
$MLX_PY training/batch_propose.py --model $BASE --adapter $FT/adapters/qwen3b-worlds2 \
    --name proven-qwen3b-worlds2 --suite unseen --taught-only [--constrain] [--samples 4 --temp 0.8 --max-terms 8]
$PY -m proven teach-sim --extractor openweight --model proven-qwen3b-worlds2 --worlds unseen \
    --phrasing heldout --json $FT/results/unseen-proven-qwen3b-worlds2-heldout.json
$PY training/compare_worlds.py --results $FT/results --suite unseen \
    --models oracle claude-sonnet-5-5 proven-qwen3b-worlds2 --against claude-sonnet-5-5
$PY training/hit_rate.py --suite unseen --models claude-sonnet-5-5 proven-qwen3b-worlds2
PROVEN_WORLDS_DIR=training/worlds $PY training/hit_rate.py --suite dev --phrasings heldout \
    --models claude-sonnet-5-5 proven-qwen3b-worlds2
PROVEN_WORLDS_DIR=training/worlds $MLX_PY training/term_probe.py \
    --model mlx-community/Qwen2.5-7B-Instruct-4bit --claims-from proven-qwen3b-worlds2 --samples 4
PROVEN_WORLDS_DIR=training/worlds $PY training/recall_experiment.py --suite dev --phrasings heldout \
    --models proven-qwen3b-worlds2 claude-sonnet-5-5 oracle
```

RL (section 11):

```sh
$MLX_PY training/rl.py --model $BASE --init $FT/adapters/qwen3b-worlds2 --out $FT/adapters/qwen3b-worlds2-rl \
    --worlds training/worlds/train --dev-worlds training/worlds/dev \
    --steps 30 --batch 2 --samples 4 --temp 1.0 --screen 8 --valid 32 --eval-every 10
```

Hosted spend for everything in this note was about $66 of a $100 cap: world authoring,
the Sonnet bars on three suites, and $10.14 of teacher labels.
