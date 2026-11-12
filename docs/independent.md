# The independent suite: Proven on closes its generator did not write

Every earlier number for Proven comes from `proven/synth.py`, a template generator written by
the same team as the checker. This suite replaces the generator with eight hand-designed
companies, written blind to the checker's code, and scores Proven against an answer key that
was committed before Proven first ran on any of it.

```bash
python -m proven benchmark --suite independent                                   # rules
python -m proven benchmark --suite independent --extractor claude \
    --model claude-sonnet-5-5 --allow-network --usd-budget 1                     # Sonnet proposer
python -m proven teach-sim --suite independent --extractor claude --model claude-sonnet-5-5
python benchmarks/independent/check_key.py                                       # the key's arithmetic
```

## Results first

There are three code states. They differ only in `claims.py` and `verify.py`; the suite,
key and Sonnet answers are the same in all three.

1. **Before the guard** (blind): the code the suite was written against (`cfd9c91`).
2. **Guarded** (blind): with the unread-content guard (`f597068`, "withhold PASS when part of
   the sentence went unread"). It was committed at 17:06 on 9 November, before the suite
   existed (`1e33dd3`, 17:20), so it was not tuned on it.
3. **After fixes, no longer blind** (`495f82d`): three general fixes for the control FAILs this
   suite exposed (§3). They were made *after seeing the set*, so these numbers can no longer
   count as an independent measurement.

| Extractor | Code | Decided | Controls passed | **Control FAIL** | Defects caught (FAIL) | Flagged | **Unsafe PASS** | Not extracted |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Rules | before the guard | 81.6% | 44/57 | **2** | 13/30 | 18/30 | **12** | 5 |
| Rules | guarded | 17.2% | 0/57 | **2** | 13/30 | 30/30 | **0** | 5 |
| Rules | after fixes, no longer blind | 14.9% | 0/57 | **0** | 13/30 | 30/30 | **0** | 5 |
| Sonnet, default guard | before the guard | 42.5% | 16/57 | **3** | 18/30 | 30/30 | **0** | 2 |
| Sonnet, default guard | guarded | 29.9% | 5/57 | **3** | 18/30 | 30/30 | **0** | 2 |
| Sonnet, default guard | after fixes, no longer blind | 26.4% | 5/57 | **0** | 18/30 | 30/30 | **0** | 2 |
| Sonnet, `--anchor-model-terms` | before the guard | 57.5% | 29/57 | **3** | 18/30 | 30/30 | **0** | 2 |
| Sonnet, `--anchor-model-terms` | guarded | 41.4% | 15/57 | **3** | 18/30 | 30/30 | **0** | 2 |
| Sonnet, `--anchor-model-terms` | after fixes, no longer blind | 37.9% | 15/57 | **0** | 18/30 | 30/30 | **0** | 2 |

The Sonnet rows replay one live run of `claude-sonnet-5-5` (8 requests, $0.1543). Every later
run was served from the cache with the network refused.

**The trade-off now.** On guarded code, no wrong explanation passes, in any configuration.
The price is that **the rules pass none of the 57 correct explanations**: they decide only by
failing (13 FAILs, all on wrong explanations), and 52 of the 57 correct ones go to a person.
With Sonnet proposing, 5 of the 57 pass. The fixes in §3 removed the three control FAILs
without changing any defect verdict. They also lowered "decided", because each removed FAIL
became a REVIEW.

### What sends each correct explanation to REVIEW (after fixes)

This counts the primary cause per control: the first advisory finding, or else the gap the
unread-content guard withheld the PASS for. "Cause stated" means the key's sentence asserts a
cause; "no cause" covers totals and "flat at" sentences, which assert none.

| Primary cause | Rules (52 in REVIEW) | Sonnet, default guard (50) |
|---|---:|---:|
| Guard: no stated reason was read, though the sentence states one | **34** | 0 |
| Guard: no stated reason was read, and the sentence states none (totals, "flat at") | 7 | 7 |
| Guard: a figure in the sentence was not checked | 4 | 0 |
| Guard: words outside the reason were not read | 1 | 3 |
| Guard: negation or contrast in the reason ("no repeat of …") | 0 | 1 |
| Guard: the sentence names two accounts | 0 | 1 |
| `WEAK_REASON_MATCH` (some written words of the reason match no memo) | 4 | **33** |
| `REASON_NOT_FOUND` | 2 | 1 |
| `REASON_FOUND_ONLY_BY_MODEL_TERMS` | 0 | 2 |
| Account mapped only by the model ("Total costs" is not an alias) | 0 | 2 |

Two blocks dominate.

- **For the rules, the guard's "no stated reason was read" (41).** In 34 of those, the
  sentence does state a cause, introduced by a word the rules do not treat as a connector
  ("on our", "for", "as", ", the", ", mostly", a colon). Before the guard, those same claims
  passed on their figures alone, which is how 12 wrong ones passed. In the other 7, no cause
  is stated at all ("Total opex was $857K, up 10%."; "Occupancy was flat at $41.3K."). The
  guard makes such a sentence impossible to PASS, by design, since there is nothing to bind.
  The README never says so, and on real commentary those sentences are common.
- **For Sonnet, `WEAK_REASON_MATCH` (33).** Sonnet supplies the reason span. The written words
  then bind to transactions, but at least one word of the cause matches no memo ("the crane
  pick at Mercy Ridge" against a memo that says "Job 2417"; "workers' comp audit true-up"
  against "WC final audit"). Real memos abbreviate and use job numbers, so nearly every
  correct cause leaves at least one unmatched word.

`--anchor-model-terms` lets specific model terms complete those bindings: 10 more controls
pass, with no new unsafe PASS on this set (§2d).

## 1. How the set was written

**Order of work, as the git history shows it.** The author read only `README.md`,
`proven/ledger.py`, `proven/examples/` (Tidewater) and `proven/__main__.py`. Then, without
running Proven and without reading `extract.py`, `claims.py`, `verify.py`, `synth.py` or any
lexicon, the author:

1. wrote `benchmarks/independent/build_ledgers.py`, a builder that imports nothing from `proven`.
   For each company it declares the chart of accounts and the aliases its finance team uses.
   It sets out recurring costs on the real calendar (semi-monthly and biweekly payroll runs,
   rent, subscriptions, usage bills), card and supplier noise from a fixed seed, and events
   typed in one by one;
2. printed each trial balance with `benchmarks/independent/tb.py` (CSV sums only) and wrote the
   commentary the way a controller reads a TB;
3. wrote each `key.json` by hand: verbatim quote, account, truth (CORRECT or WRONG plus defect
   type), a one-line why with the numbers, the evidence transaction ids, and the ideal and
   acceptable verdicts;
4. wrote `benchmarks/independent/check_key.py`, an independent checker (CSV sums, no `proven`
   import). For every label it recomputes the account's movement and the net movement of the
   cited transactions, and asserts that the label follows from them (rules in its docstring).
   It reported 0 errors. A mutation test (12 deliberate key corruptions) was flagged 12/12;
5. committed it all as `1e33dd3 test: independent closes, written blind`, **before the first
   checker run**.

Before the commentary was written, the ledgers were changed for realism or volume only: more
noise lines so every period has at least 80 transactions, fictional names in place of real
vendor names, and a July summer volume lift on Ember & Rye's beverage lines. None of these
changes was made after a checker run.

**The companies.** Each ledger has one history month (so vendors have a "usual account"),
then the prior and current periods, with 81–168 transactions a month.

| Company | Industry | Periods | Claims (correct / wrong) |
|---|---|---|---|
| Brightline Analytics | B2B SaaS | Sep → Oct 2026 | 11 (8 / 3) |
| Ember & Rye Hospitality | Restaurant group, 3 locations | Jun → Jul 2026 | 12 (7 / 5) |
| Keystone Mechanical | HVAC/plumbing subcontractor | Aug → Sep 2026 | 11 (7 / 4) |
| Cedar Valley Family Medicine | Medical practice | Sep → Oct 2026 | 12 (9 / 3) |
| Lumen & Loom | DTC e-commerce | Sep → Oct 2026 | 10 (7 / 3) |
| Riverbend Community Food Network | Non-profit food bank | May → Jun 2026 | 10 (7 / 3) |
| Halvorsen Precision | CNC job shop | Aug → Sep 2026 | 10 (6 / 4) |
| Northstar Freightways | Regional trucking | Sep → Oct 2026 | 11 (6 / 5) |
| **Total** | | | **87 (57 / 30)** |

Wrong explanations by defect: wrong amount 7, cause too small for the wording 4, wrong cause
(right amount, the stated cause is not what moved it) 4, wrong direction 3, wrong account 3,
cause in the other period 3, cause contradicted by a credit 3, fabricated cause (no such
transactions) 3. The commentary also has 15 sentences that are not ledger claims (ARR,
headcount, visits, backlog, forecasts). The rules turn three of them into claims, all REVIEW.

**The mess it contains.** It includes accruals and reversals: a legal accrual replaced by the
invoice, an insulation sub's accrue, reverse, bill and re-accrue cycle, and a year-end audit
accrual. It has credit memos (a spoiled-product credit, an SLA credit, an RMA credit, a CAM
reconciliation, an invoice credited in full, a cargo recovery) and a duplicate invoice and its
credit. It has a reclass journal, prepaid amortisation on renewal, a late invoice (timing), a
third biweekly pay date in a month, one-offs against recurring lines, causes split across two
or three vendors, and FX (GBP, EUR and CAD). The commentary rounds ("~$31k", "about 13%",
"roughly doubled"), abbreviates (R&M, 3PD, CME, med mal), uses passive voice and business
language rather than memo vocabulary, and puts two claims in one sentence three times.

**Labelling rule.** A claim is CORRECT when the direction is right and every stated figure is
right at its written precision (change within 7%, percent within 1.5 points, balance within
3%). The stated cause must also carry the share the wording claims: 75% for an unqualified
"due to/on/for/as" or "nearly all", 50% for "driven by/mainly/mostly/largely". For timing,
volume and price causes the key instead gives an economic explanation (`share_note`). A
correct claim's ideal verdict is PASS, REVIEW is acceptable, and FAIL is a control failure. A
wrong claim's ideal is FAIL, REVIEW is acceptable, and PASS is an unsafe pass.

### Limits of the protocol

- **The author is an AI model, not a controller,** and had read the README, including its
  thresholds and finding codes.
- **The ledgers are designed, not exported.** The noise is well-behaved, every event is clean,
  and vendor names are consistent.
- **One author wrote both the commentary and the key.** The key was verified arithmetically by
  a script, not by a second person.
- **87 claims is small.** One claim moves a rate by 1.1 to 3.3 points.
- **The fixed rows are not independent.** The three fixes in §3 were written after seeing which
  sentences failed. They are general reading rules, tested on ledgers of their own and checked
  against the synthetic benchmark, but a fresh blind set is needed to measure them.

## 2. Detail

### Per company (after fixes)

| Company | n | Rules decided | Rules caught | Sonnet decided | Sonnet controls passed | Sonnet caught |
|---|---:|---:|---:|---:|---:|---:|
| brightline | 11 | 9.1% | 1/3 | 18.2% | 1/8 | 1/3 |
| ember_rye | 12 | 16.7% | 2/5 | 25.0% | 0/7 | 3/5 |
| keystone | 11 | 9.1% | 1/4 | 18.2% | 0/7 | 2/4 |
| cedar_valley | 12 | 16.7% | 2/3 | 25.0% | 1/9 | 2/3 |
| lumen_loom | 10 | 10.0% | 1/3 | 20.0% | 1/7 | 1/3 |
| riverbend | 10 | 0.0% | 0/3 | 20.0% | 1/7 | 1/3 |
| halvorsen | 10 | 20.0% | 2/4 | 30.0% | 0/6 | 3/4 |
| northstar | 11 | 36.4% | 4/5 | 54.5% | 1/6 | 5/5 |

Unsafe PASS and control FAIL are 0 for every company, in every configuration, after the fixes.

### Per defect type: FAIL / REVIEW / PASS / not extracted

| Family | n | Rules, before the guard | Rules, guarded and after fixes | Sonnet (every state) |
|---|---:|---|---|---|
| wrong_amount | 7 | 7 / 0 / 0 / 0 | 7 / 0 / 0 / 0 | 7 / 0 / 0 / 0 |
| wrong_account | 3 | 3 / 0 / 0 / 0 | 3 / 0 / 0 / 0 | 3 / 0 / 0 / 0 |
| wrong_direction | 3 | 2 / 0 / **1** / 0 | 2 / 1 / 0 / 0 | 2 / 1 / 0 / 0 |
| contradicted_by_credit | 3 | 1 / 0 / **2** / 0 | 1 / 2 / 0 / 0 | 2 / 1 / 0 / 0 |
| cause_in_other_period | 3 | 0 / 1 / **2** / 0 | 0 / 3 / 0 / 0 | 2 / 1 / 0 / 0 |
| cause_too_small | 4 | 0 / 0 / **4** / 0 | 0 / 4 / 0 / 0 | 2 / 2 / 0 / 0 |
| wrong_cause | 4 | 0 / 2 / **2** / 0 | 0 / 4 / 0 / 0 | 0 / 4 / 0 / 0 |
| fabricated_cause | 3 | 0 / 2 / **1** / 0 | 0 / 3 / 0 / 0 | 0 / 3 / 0 / 0 |
| control (correct) | 57 | 2 / 6 / 44 / 5 | guarded 2 / 50 / 0 / 5; fixed 0 / 52 / 0 / 5 | guarded 3 / 47 / 5 / 2; fixed 0 / 50 / 5 / 2 |

Amounts, directions and accounts are decided on this commentary: all 7 wrong amounts and all
3 wrong accounts FAIL in every configuration. No wrong cause and no fabricated cause is ever
FAILed: those go to a person, which is acceptable but means none of the cause-level defects
is decided by the checker alone. Of the 17 cause-level defects (other period, too small,
credit, wrong cause, fabricated), Sonnet FAILs 6; the rules FAIL 1 (a credit claim, on its
amount).

### (c) The reviewer loop

`teach-sim --suite independent` plays a reviewer who reads the key. It teaches from half the
companies (brightline, keystone, lumen_loom, halvorsen) and measures the other half with rules
plus lessons, then the other way round. It uses the `teachsim.py` rule: teach only from a
correct claim in REVIEW because its support rests on model terms, where confirming those terms
makes it PASS. Since `0798d4e` the confirmed words are those `learned.trim_terms` keeps
(docs/teaching.md, "Lessons keep only the words their cause needs"). Re-run with those rules
(again after the third, `814b2d5`), the "after fixes" rows below are unchanged; the earlier
code states taught no lesson, so the rules cannot change them.

| Code | Taught on | Lessons | Held half: decided before → after | Unsafe PASS | Control FAIL |
|---|---|---:|---|---:|---:|
| before the guard | first half | 0 | 82.2% → 82.2% | 4 → 4 | 1 → 1 |
| before the guard | second half | 0 | 81.0% → 81.0% | 8 → 8 | 1 → 1 |
| guarded | first half | 0 | 20.0% → 20.0% | 0 → 0 | 1 → 1 |
| guarded | second half | 0 | 14.3% → 14.3% | 0 → 0 | 1 → 1 |
| after fixes, no longer blind | first half | 0 | 17.8% → 17.8% | 0 → 0 | 0 → 0 |
| after fixes, no longer blind | second half | 0 | 11.9% → 11.9% | 0 → 0 | 0 → 0 |

No lesson qualified in any state. Only two correct claims sit in REVIEW on model terms, and
confirming their terms would make each a FAIL, not a PASS. For RB-03, "pantry" matches the
2 of 6 grant payees whose names contain it (33%). For NSF-02, "fuel card" carries 73% of a
price-and-volume change. A wider, scratch-only reviewer, run on pre-guard code, also confirmed
`WEAK_REASON_MATCH` controls. It taught 10 + 5 lessons. They changed nothing with the rules
and moved one control to PASS in each direction with Sonnet. (That scratch run predates the
lesson-trimming rule and was not repeated.) The reason is structural: a
lesson triggers on a stated reason's exact wording, and eight companies never word a cause the
same way. Lessons might transfer from one month to the next within a company, which this
suite cannot measure.

### (d) `--anchor-model-terms`

On this set the experimental policy passes 10 more correct explanations (15/57 against 5/57)
with no unsafe PASS, in every code state. The README's 12 unsafe PASSes under this policy came
from synthetic closes. This suite does not reproduce them, and 30 wrong claims cannot show the
policy is safe. The case for keeping it off still rests on the synthetic evidence.

## 3. Every unsafe PASS and control FAIL

Ledger facts are from the key (`proven/examples/independent/*/key.json`) and are verified by
`check_key.py`.

### Before the guard: 12 unsafe PASSes with the rules (fixed by `f597068`)

**Mechanism A: an unread reason was treated as no reason (11 claims).** `claims.split_reason`
recognises a reason only after `due to`, `because (of)`, `driven by`, `as a result of`,
`reflecting`, `attributable to`, `owing to`, `thanks to`, `on the back of`, or `on` directly
followed by `higher/lower/increased/decreased/additional`. Otherwise no reason is read, the
attribution check is skipped, and before the guard the verdict came from direction and amount
alone.

| Id | Sentence | What the ledger shows | Connector not read |
|---|---|---|---|
| KMC-09 | Permits and inspections were up $2.2K, the Mercy Ridge mechanical permit. | +$2,200 is right; the Mercy Ridge permit (AP-30096, $1,900) was in **August**; September's rise is Cherry Creek permits (AP-30191) and backflow certs (AP-30241) | ", the …" |
| KMC-11 | Safety & training up $5.3K for the foremen's OSHA 30 class. | OSHA 30 is $2,100 (AP-30234), 40%; fall-protection kits $3,200 (AP-30238) | "for" (and no verb) |
| KMC-03 | Subcontractor costs fell ~$30K as the August insulation accrual reversed. | the reversal (GJ-30167, −$18,000) is offset by the invoice (AP-30208) and a new accrual (GJ-30254): insulation net +$750; the fall is Front Range Sheet Metal −$31,800 | "as" |
| ER-11 | Marketing rose $2.4K on our Restaurant Week listing. | listing $2,750 (ER26-00345) credited in full (ER26-00431); the rise is a photo shoot (ER26-00390) | "on our" |
| RB-07 | Printing and postage rose $3.2K on the gala invitations. | invitations were May (RB-0097, RB-0100); June is the spring appeal (RB-0192, RB-0201) | "on the" |
| RB-10 | Technology rose $4.4K for the new donor CRM. | CRM invoice (RB-0178) credited in full (RB-0202); the rise is laptops (RB-0216) | "for" |
| HPC-07 | Plant utilities rose $3.4K on summer peak-demand charges. | demand charge flat at $3,100 (GL004111, GL004194); a meter back-bill (GL004216) is 96% | "on summer" |
| HPC-08 | Quality costs rose $11.6K for the AS9100 surveillance audit. | audit $5,500 (GL004200), 47%; CMM recalibration $6,100 (GL004249) | "for" |
| NSF-10 | Driver recruiting rose $7.6K on the expanded job-board campaign. | job board +$2,900 (NSF-55128, NSF-55226), 38%; CDL tuition $4,700 (NSF-55275) | "on the" |
| LL-04 | Affiliate & influencer spend rose $5.2K, mostly FX on the euro-denominated creator retainer. | FX is +$447 (LL-200130 → LL-200227), 8.5%; affiliate commissions +$4,800 | ", mostly …" |
| BRT-11 | Rent & facilities were up $2.6K for the new 4th-floor storage lease. | no storage lease exists; carpet cleaning (JE-104795) and electricity (JE-104749) | "for" |

**Mechanism A′: unread direction plus magnitude-only comparison (BRT-06).** *"Contractor spend
ticked up about $2.8K with Polaris QA coming on."* Contractors fell by $2,794.25: Ana Ribeiro's
contract ended (JE-104682), and Polaris QA is new (JE-104791). "ticked up" is not a direction
word, so the stated $2.8K was compared with the change's magnitude and agreed.

**On guarded code** all 12 are REVIEW. The guard withholds a PASS when no reason or no
direction was read. These are regression tests in `proven/tests/test_independent.py`
(`test_unread_reason_does_not_pass[...]`, `test_unread_direction_does_not_pass`). They are
still not *caught*: the reason goes unread and a person must decide. Reading those connectors
would let the checker FAIL them; it would also let it PASS the 34 correct controls now stuck
on "no stated reason was read". That work remains.

### Control FAILs on guarded code, and the fixes (after fixes, no longer blind)

All three are general reading errors. Each fix is tested on a small ledger of its own in
`proven/tests/test_figure_roles.py`. Seven of its tests fail on the code before the fixes; the
other four check that a genuinely wrong claim still FAILs.

**LL-02: a figure belonging to another account's claim (rules and Sonnet).** *"Paid social was
up ~72% as we put spend behind the Hearth fall launch on SocialReach and Clipstream, funded in
part by pulling about $4K out of search."* Both halves are right (paid social +71.8%, paid
search −$4,050). The reader resolved the first alias (Paid Social) and took the first money
figure in the sentence ($4K, search's) as its change: `WRONG_AMOUNT`, so FAIL.
*Fix (`claims.read_figures`, `admit`):* a figure belongs to the account its own clause names.
A figure whose clause (between commas, semicolons, colons, brackets or dashes) names another
account, and not this one, is not read as this claim's, either by the rules or from a
proposal. It is then an unchecked figure, so the guard sends the claim to REVIEW.

**NSF-11: "flat at about $9K", a balance read as a change (rules and Sonnet).** Tolls &
permits went from $9,060 to $9,200 (+$140). The balance cue needed "at" right before the
figure, so the hedge "about" broke it, and $9K was read as the change. Under Sonnet the
proposal correctly said `current_text="$9K"`, but `admit()` also kept the rules' reading of
the same figure as the change ("never subtract"). *Fix:* hedges (about, approximately,
roughly, around, nearly, almost, some, just over/under, ~) may sit between a balance cue
(to, at, reached, was/were, from) and its figure. When a proposal and the deterministic
reading put one written figure in two different roles, `admit()` checks it in neither and
records `figure_conflicts`, which the guard treats as unread. The claim can then be REVIEW,
never PASS, so a proposer cannot dodge a failing change check by relabelling it as a balance.

**BRT-02: a coordinated cause with one side unmatched (Sonnet).** *"Hosting & infrastructure
was up ~$31k (roughly 50%) as onboarding the Meridian Health account drove both compute and
warehouse usage."* Correct: the compute bill (+$21,832) plus the warehouse bill (+$9,264) is
99.6% of +$31,234. The lexicon-vouched written word "compute" bound only the compute bill.
"warehouse" matched nothing (the memo says "Capacity credits"). Because a declared term
vouched for the binding, `WEAK_REASON_MATCH` stood aside, and the 70% share produced
`PARTIAL_EXPLANATION` (confirmed), so FAIL. *Fix (`verify._unbound_written_words`):* before
a FAIL on the reason, if the reason coordinates two causes (`and`, `plus`, `as well as`, ` & `)
and the written word on one side matched while the other matched nothing, the finding is
`WEAK_REASON_MATCH` (advisory) instead. A first, broader version of this fix applied whenever
any written word went unmatched. It cut seen-phrasing decided from 90.1% to 88.3% by sending
lexicon-matched wrong causes ("the product launch campaign": "product" unmatched) to REVIEW.
It was narrowed to coordinated causes before committing.

### What the fixes did to the synthetic benchmark (measured before and after)

| Run (test split, n = 440) | Before: decided / control FAIL / unsafe PASS | After |
|---|---|---|
| rules, seen | 90.1% / 0 / 0 (783/810 controls passed, 279/280 met) | identical |
| rules, heldout | 11.0% / 0 / 0 | identical |
| rules, paraphrase | 11.0% / 0 / 0 | identical |
| oracle, heldout | 11.0% / 0 / 0 | identical |
| oracle, paraphrase | 11.0% / 0 / 0 | identical |
| Sonnet (cached, 440/440 hits), heldout | 11.0% / 0 / 0 | identical |

The printed benchmark output for the rules runs is byte-identical before and after.

## 4. What a real pilot would still need

- **Real books and real commentary**: a GL export and the controller's own variance memo for
  several months of at least three companies, labelled by someone who did not write either.
- **A fresh blind set** to measure the post-fix code. The fixed rows above are not independent.
- **Reading more connectors, safely.** On real commentary a cause introduced by "on", "for",
  "as" or an apposition is the common case. The guard makes those claims safe but leaves them
  all to a person: 34 of 57 correct explanations here.
- **A policy for sentences with no cause**: totals and "flat at" statements can never PASS under
  the guard. That may be right, but it should be a stated choice.
- **Memo vocabulary.** With a model reading the reason, the binding fails mostly on single
  words that real memos abbreviate or replace with job numbers (33 of 50 control REVIEWs).
- **Month-over-month lesson measurement within one company**, the only setting where verbatim
  lessons can transfer.
- **Second-reader labels.**

## Files

- `proven/examples/independent/<company>/{chart.json, ledger.csv, commentary.txt, key.json}`,
  `suite.json`: the suite.
- `benchmarks/independent/build_ledgers.py`, `tb.py`, `check_key.py`: builder, trial balance,
  key verifier (no `proven` imports).
- `proven/independent.py`: loader, matcher, scorer (including REVIEW causes), teach-and-measure.
- `proven/tests/test_independent.py`: the key's soundness, the pinned result, regression tests
  for every mechanism above. `proven/tests/test_figure_roles.py`: unit tests for the three fixes.
