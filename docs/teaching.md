# Teaching Proven safely, and in the right order

A claim whose stated reason is supported only by the model's search terms waits in REVIEW
(`SUPPORT_RESTS_ON_MODEL_TERMS`) until a reviewer confirms the phrase → terms mapping as a
lesson. This note covers three additions to that loop:

- a **safety gate** that replays every lesson before it is stored (`proven/gate.py`);
- a **teaching order**, with the reviewer's time counted in confirmations (`teachsim.curve`);
- a **teaching queue** in the console: what to confirm next across stored runs
  (`proven/teachqueue.py`, `GET /api/queue`, the "Teach next" card in Learned).

Every number below was produced offline on the merged `integration` code (the unread-content
guard included), and produced again, identical apart from timings, after merging the
independent-suite fixes (`integration` at e81f98a): rules extractor, the oracle, or Sonnet 5.5
proposals replayed from the proposal cache with no request sent (0 cache misses). The standard benchmark is unchanged
(`benchmark --phrasing seen`: 90.1% decided, 0 unsafe PASS, 0 control FAIL), and so is the
README's teach-sim table (36 lessons, 88.6% decided, 0 / 0).

## 1. The safety gate

### Method

A lesson is replayed, on top of the lessons already active, against two sets of claims whose
answer is known:

| Set | What | Size |
|---|---|---|
| Regression set (built in) | Every labelled claim of 880 **train-split** closes per phrasing, in seen, held-out and paraphrase phrasing: all 7 defect families (known wrong) and all control families (known right). Generated deterministically; the test split is never used. | 2,640 closes, 6,576 claims (1,680 wrong, 4,896 right) |
| Stored cases | Every resolution in the data directory recorded with its text and ledger. *Confirm defect* is known wrong; a teaching action (*Wrong evidence*, *Misread sentence*, *Accept convention*) whose claim ended PASS is known right. The console now sends the text and ledger with every decision, not only with lessons. | grows with use |

Only claims the lesson can change are replayed: those whose stated reason a trigger fires on,
or that contain one of its terms as a written word (a learned term vouches for that word in
`verify._weak_binding`). A test checks that a sample of untouched claims keeps its verdict.

**Refusal rule.** Compared with the lexicon without it, the lesson would

- PASS an explanation known to be wrong, or
- FAIL an explanation known to be right.

Everything else is reported, not refused: correct claims it newly passes, wrong ones it newly
fails, correct ones it un-passes, stored cases whose verdict changes, and how many known claims
it touched. A lesson that touches nothing is accepted and marked **not tested**; the console
says so in amber instead of calling it safe.

**Where it runs.** `POST /api/resolutions` with a lesson (a refusal is a 400 whose body carries
the whole `impact` report; an accepted lesson returns it too), `POST /api/lexicon/check` (a
dry run, nothing stored), every previewed row of `GET /api/queue`, and `teach-sim --gate on`.

**Latency.** Building the regression set takes about 3 s once per process (the console
starts it in a background thread at `serve`). After that a check takes 20–500 ms on a quiet
machine: median 277 ms over the 36 Sonnet lessons, 297 ms over the 36 oracle lessons, 182 ms
over 67 paraphrase lessons. On a second run while other jobs loaded the machine the medians
were 250–360 ms and the slowest check 704 ms.

### Deliberately bad lessons

| Lesson | Kind of mistake | Gate | Wrong explanations that would newly PASS | Right ones that would newly FAIL |
|---|---|---|---:|---:|
| "the second location" → build-out, progress billing | a vague reason bound to a neighbouring cause's invoices | **refused** | 6 | 1 |
| "the second location" → build-out | the same, as a careless reviewer confirmed it in the simulation | **refused** | 6 | 1 |
| "the new breach policy in september" → policy | a generic word shared by two causes | **refused** | 4 | 4 |
| "the senior leadership hire" → placement fee | right cause, only half its invoices | **refused** | 5 | 48 |
| "coverage" → premium | overbroad trigger, overbroad term | **refused** | 8 | 44 |
| "trip" → flights | overbroad trigger | **refused** | 3 | 117 |
| "senior" → placement | overbroad trigger | **refused** | 9 | 102 |
| "protection" → premium | overbroad trigger | **refused** | 7 | 125 |
| "the large experiment our ml team ran" → ec2, aws | right account, the other cause's words | **refused** | 0 | 3 |
| "protecting our directors" → d&o, liability | right lesson plus one overbroad word | **refused** | 2 | 27 |
| "protecting our directors" → d&o | the same without that word | accepted (45 correct claims newly pass) | 0 | 0 |
| "board coverage" → d&o | right | accepted (47) | 0 | 0 |
| "the second location" → lease, austin | right | accepted (42) | 0 | 0 |
| "the project" → services | wrong, but nothing known uses it | accepted, **not tested** | 0 | 0 |

The refusal reads, for example: *"Proven will not learn this: it would make 6 explanations
known to be wrong pass and it would fail 1 explanation known to be right. For example, “Rent and
facilities increased approximately $32K (168%) compared with September, driven by the second
location.” (synthetic regression close syn-00479, partial) would go from FAIL to PASS. The
trigger probably covers more than this cause, or the ledger words also match another cause's
transactions; narrow the trigger…"*

Stored cases bite too: on the showcase, the careless lesson "fewer customer visits" → offsite
(the offsite explains the fall, customer visits do not) is untested by the regression set and
accepted on its own; once a reviewer has recorded *Confirm defect* on that sentence, the gate
refuses it (`test_a_confirmed_defect_becomes_a_case_no_lesson_may_pass`).

### False refusals

Lessons a careful reviewer (one who reads the label) confirms on correct explanations:

| Lessons from | Lessons | Refused by the gate |
|---|---:|---:|
| Sonnet, held-out (the README's 36, in teaching order) | 36 | **1** ("board coverage" → d&o, liability) |
| Oracle, held-out | 36 | 0 |
| Oracle, paraphrase | 67 | 0 |

So 1 of 139 (0.7%); 1 of 36 (2.8%) on real model terms. That one lesson is right for its own
phrase, but its term "liability" also vouches for the written word "liability" everywhere, so
correct paraphrase sentences about "liability cover for our board members" bind to the
general-liability retainer and FAIL (27 of them), and 2 wrong explanations PASS. The held-out
measurement never sees that side effect, which is why the simulation counts it as a false
refusal. With the gate on, the arrival-order simulation still teaches 36 lessons (d&o is taught
from a later claim) and ends at **88.4% decided instead of 88.6%**, 0 / 0 either way.

The side effect itself (a learned term vouches for a single written word in every sentence) is
a property of `verify._weak_binding`, which this stream did not change.

## 2. A careless reviewer, with and without the gate

`teach-sim --careless P`: the simulated reviewer works down the queue (frequency order); asked
about a claim on a **wrong** explanation, it confirms the model's matched terms anyway with
probability P (otherwise it records *Confirm defect*, which becomes a stored case). Sonnet
proposals, held-out phrasing, teaching on the first 220 test closes, measured with the rules on
the other 220 (402 correct claims, 140 wrong ones). P = 1 is deterministic; P = 0.5 and 0.25 are
5 seeds each (totals over the seeds).

| Queue | P | Gate | Lessons from wrong explanations stored | **Unsafe PASS** | **Control FAIL** | Decided |
|---|---|---|---|---:|---:|---:|
| model support only (the console's queue) | 1 | off | 4 | **4** | **14** | 91.3% |
| | 1 | on | 1 (4 refused) | **0** | **0** | 88.2% |
| | 0.5 | off | 13 over 5 seeds | **13** | **28** | 89.6% mean |
| | 0.5 | on | 3 (12 refused) | **0** | **0** | 88.2% |
| | 0.25 | off | 7 | **7** | **14** | 88.9% |
| | 0.25 | on | 3 (5 refused) | **0** | **0** | 88.2% |
| any REVIEW claim with model matches (harder) | 1 | off | 8 | **4** | **14** | 91.7% |
| | 1 | on | 4 (8 refused) | **0** | **0** | 88.4% |
| | 0.5 | off | 26 | **5** | **70** | 91.4% mean |
| | 0.5 | on | 12 (19 refused) | **0** | **0** | 88.4% |
| | 0.25 | off | 13 | **2** | **56** | 90.8% |
| | 0.25 | on | 4 (12 refused) | **0** | **0** | 88.4% |

**Headline: a reviewer who confirms every wrong explanation the queue shows them causes 4 unsafe
PASSes and 14 failed correct explanations on untaught closes without the gate, and 0 and 0 with
it.** Over every careless run (22 with the gate, 22 without) the gate held both kill criteria at
zero; without it 17 of the 22 runs broke at least one. The decided share without the gate is
higher only because it includes the wrong FAILs.

The careless lessons the gate let through did no measured harm (0 / 0). In the harder queue the
gate also refused the one right lesson "protecting our directors" → d&o, liability in every run
(the false refusal above); the narrower d&o lesson was taught instead.

The queue offers a careless reviewer few chances: in the console's queue only 6–8 of the waiting
claims in the teaching pool are on wrong explanations, because a wrong explanation rarely sits in
REVIEW on model support alone. The "any model match" queue is the stress variant.

## 3. Teaching order, counted in confirmations

`teach-sim --order arrival|frequency|both`. The queue holds every waiting claim of the teaching
pool; after each lesson it is re-ranked. **Frequency** asks first for the lesson whose trigger
fires on the most waiting claims (ties: the terms the model proposed most often for that phrase,
then arrival). **Hindsight** ranks by the measured half itself; it is not a policy, only the bound
on what any order of the same lessons could reach. Decided share on the untaught half, with the
number of questions put to the reviewer (`asks`, including declines) where it differs:

| Proposer, phrasing | Order | 0 | 5 | 10 | 20 | 40 | all |
|---|---|---:|---:|---:|---:|---:|---:|
| Sonnet, held-out | arrival | 11.1% | 20.8% | 32.3% | 56.5% (21 asks) | — | 88.6% (36 lessons, 44 asks) |
| | frequency | 11.1% | 18.8% | 31.4% | 54.6% (22) | — | 88.2% (34, 40) |
| | *hindsight bound* | 11.1% | 26.2% | 39.5% | 64.2% | — | 88.2% |
| Oracle, held-out | arrival | 11.1% | 20.7% | 32.1% | 58.3% | — | 92.6% (36, 39) |
| | frequency | 11.1% | 22.1% | 32.1% | 55.0% | — | 92.6% |
| | *hindsight bound* | 11.1% | 26.0% | 39.5% | 64.6% | — | 92.6% |
| Oracle, paraphrase | arrival | 11.1% | 15.5% | 20.3% | 32.7% | 56.8% | 87.1% (67, 70) |
| | frequency | 11.1% | 16.1% | 21.2% | 32.5% | 53.3% | 87.1% |
| | *hindsight bound* | 11.1% | 20.1% | 27.3% | 41.7% | 65.5% | 87.1% |

Every row: 0 unsafe PASS, 0 control FAIL, with the gate on and off.

**On the benchmark's own closes, frequency order buys nothing over arrival** (within ±2 points,
sometimes worse). The reason is the generator: it draws each cause and each phrase uniformly, so
a phrase's count in 220 teaching closes (about 5) is mostly noise as a predictor of its count in
the other 220. The hindsight bound shows the headroom any ordering has here: about 5–8 points
at 5–20 confirmations.

Real commentary repeats a few phrases far more than the rest. `--skew S` draws the closes so the
main sentence's phrase follows a Zipf law with exponent S (oracle only, since Sonnet answers are
cached only for the plain split; distractor sentences stay uniform, which dilutes the skew):

| Skew | Order | 0 | 5 | 10 | 20 | all |
|---|---|---:|---:|---:|---:|---:|
| 1 | arrival | 11.3% | 25.5% | 32.6% | 60.4% | 93.7% |
| | frequency | 11.3% | **29.3%** | **41.9%** | **63.1%** | 93.7% |
| | *hindsight bound* | 11.3% | 34.5% | 48.7% | 70.5% | 93.7% |
| 2 | arrival | 10.1% | 23.9% | 32.4% | 62.9% | 90.0% |
| | frequency | 10.1% | **34.8%** | **44.9%** | **66.3%** | 90.0% |
| | *hindsight bound* | 10.1% | 37.7% | 48.2% | 69.6% | 90.0% |

When phrases repeat, frequency order closes most of the gap to the bound: at skew 2, 5
confirmations decide 34.8% instead of 23.9%, against a bound of 37.7%. The console's queue uses
frequency order.

Commands (offline):

```bash
python -m proven teach-sim --extractor claude --model claude-sonnet-5-5 --phrasing heldout --n 440 --order both --gate both
python -m proven teach-sim --extractor claude --model claude-sonnet-5-5 --phrasing heldout --n 440 --careless 1
python -m proven teach-sim --extractor claude --model claude-sonnet-5-5 --phrasing heldout --n 440 --careless 0.5 --seed 3 --any-model-match
python -m proven teach-sim --order both --skew 2          # oracle
python -m proven teach-sim --order hindsight              # the bound
```

## 4. The teaching queue in the console

- When the console verifies with a model extractor and claims wait on its words, the run's
  inputs and those claims are appended to `<data_dir>/pending.jsonl`. A later model run of the
  same text on the same ledger replaces it; a rules run never does (re-opening a queued close
  re-checks it with the rules).
- `GET /api/queue` groups the waiting claims across stored runs by the lesson that would settle
  them (the stated reason → the model's matched terms), ranks them by frequency, and for the
  first 8 rows adds the gate's preview and how many of the reached claims the rules would then
  decide. A claim leaves the queue when a stored lesson fires on its reason or a resolution was
  recorded for it.
- **Learned → Teach next** lists the rows: the phrase, the proposed terms, the number of waiting
  claims, how many would be decided, the number of runs, and the gate's verdict in words (green
  *Gate: safe* with what it replayed, red *Gate refuses* with the reason, amber *Not tested*).
  **Open** loads the stored run into Review, selects the claim, and fills the Teach form in the
  detail pane with the phrase and terms; the form re-runs the gate (*Check with the safety
  gate*) and shows "This claim: REVIEW → PASS". Confirming still needs a written reason and the
  PASS checkbox; one click opens the form, it does not confirm.

Checked in a browser (Playwright, Chromium) on a scratch data directory seeded with 60 cached
Sonnet runs (107 waiting claims), port 8771, after the merge with the redesigned console: light
and dark themes, 1440 px and 390 px wide (no horizontal scroll); opening a row, recording a
safe lesson (queue 107 → 98 waiting, the claim turns PASS, the notice carries the gate's
summary), and recording a refused lesson (refusal shown in the form, nothing stored).

## 5. Limits

- **The regression set is synthetic and shares an author with the generator and the checker.**
  It catches a bad lesson only if some known claim uses its phrase or words. In the simulation
  that is nearly always true: the held-out tier uses the same phrases in the train and test
  splits, so the gate has seen every phrase the careless reviewer can confirm. A real reviewer's
  novel phrase passes untested (and is labelled so) unless the data directory's own decisions
  cover it. The careless-reviewer result is therefore an upper bound on what the gate buys in
  real use.
- **The simulated reviewer reads the label.** "Careless" is a coin flip on wrong explanations,
  not a model of how people actually err.
- **Refusal is all-or-nothing on the replayed sets.** A lesson that is right for its phrase but
  carries one overbroad word is refused whole; the reason names an example, and the reviewer has
  to narrow it.
- The teaching curves use one ordering of one split; the Sonnet numbers come from one cached run.
- Frequency order helps only when phrases repeat; on the uniform benchmark it does not.
- The queue is stored per data directory and per machine (on the hosted demo, under `/tmp`).
