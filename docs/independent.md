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

**The short version.** On hand-written commentary the rules extractor **broke the unsafe-PASS kill
criterion 12 times out of 30 wrong explanations, and failed 2 of 57 correct ones**. Every unsafe
PASS has the same mechanism: the sentence states its cause with a word the rules do not treat
as introducing a reason ("on our", "for", "as", ", the", "mostly"), so the cause is never read
and the claim passes on its figures alone. Its 81.6% "decided" mostly measures figure checks:
1 of its 44 control PASSes had the stated cause checked against transactions. With Sonnet
proposing (default guard), there were **0 unsafe PASSes and 3 control FAILs**, at 42.5% decided.
The reviewer-lesson loop taught **0 lessons** and changed nothing on the held-out half.

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
   checker run**. The runner and every result come after it (`8c38c5c` onwards).

Before the commentary was written, the ledgers were changed for realism or volume only: more
noise lines so every period has at least 80 transactions, fictional names in place of real
vendor names, and a July summer volume lift on Ember & Rye's beverage lines. None of these
changes was made after a checker run.

**The companies.** Each ledger has one history month (so vendors have a "usual account"),
then the prior and current periods, with 81–168 transactions a month (tested: at least 80 in
each compared period).

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
headcount, visits, backlog, forecasts). The rules turned three of them into claims, all REVIEW.

**The mess it contains.** It includes accruals and reversals: a legal accrual replaced by the
invoice, an insulation sub's accrue, reverse, bill and re-accrue cycle, and a year-end audit
accrual. It has credit memos (a spoiled-product credit, an SLA credit, an RMA credit, a CAM
reconciliation, an invoice credited in full, a cargo recovery) and a duplicate invoice and its
credit. It has a reclass journal, prepaid amortisation on renewal, a late invoice (timing), a
third biweekly pay date in a month, one-offs against recurring lines, causes split across two
or three vendors, and FX (GBP, EUR and CAD). The commentary rounds ("~$31k", "about 13%",
"roughly doubled"), abbreviates (R&M, 3PD, CME, med mal), uses passive voice and business
language ("onboarding the Meridian Health account") rather than memo vocabulary, and puts two
claims in one sentence three times.

**Labelling rule.** A claim is CORRECT when the direction is right and every stated figure is
right at its written precision (change within 7%, percent within 1.5 points, balance within
3%). The stated cause must also carry the share the wording claims: 75% for an unqualified
"due to/on/for/as" or "nearly all", 50% for "driven by/mainly/mostly/largely". For timing,
volume and price causes the key instead gives an economic explanation (`share_note`). A
correct claim's ideal verdict is PASS, REVIEW is acceptable, and FAIL is a control failure. A
wrong claim's ideal is FAIL, REVIEW is acceptable, and PASS is an unsafe pass.

### Limits of the protocol

- **The author is an AI model, not a controller,** and had read the README, including its
  thresholds (75% / 50% / 10%) and the finding codes. The labelling rule above is close to the
  README's on purpose, so that a disagreement is about reading the text, not about policy.
  "driven by" is the exception: Proven reads it as *full* and the key as *main driver*. No key
  claim depends on that difference.
- **The ledgers are designed, not exported.** The noise is random but well-behaved, every event
  is clean, and vendor names are consistent. Real GL exports have messier memos, split lines
  and partial data.
- **One author wrote both the commentary and the key.** The key was verified arithmetically by
  a script, not by a second person.
- **87 claims is small.** One claim moves a rate by 1.1 to 3.3 points. The counts are reported
  as counts.

## 2. Results

`decided` is PASS or FAIL over all 87 keyed claims. `cause checked` counts the control PASSes
whose attribution check ran and was supported; the rest passed on their figures alone.
`caught` is FAIL on a wrong explanation, and `flagged` is FAIL or REVIEW. A keyed claim no
admitted claim covers is `not extracted`.

| Configuration | Decided | Controls passed | cause checked | **Control FAIL** | Defects caught | Flagged | **Unsafe PASS** | Not extracted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| (a) Rules | 81.6% | 44/57 | 1 | **2** | 13/30 | 18/30 | **12** | 5 |
| (b) Sonnet proposer, default guard | 42.5% | 16/57 | 9 | **3** | 18/30 | 30/30 | **0** | 2 |
| (d) Sonnet, `--anchor-model-terms` | 57.5% | 29/57 | 22 | **3** | 18/30 | 30/30 | **0** | 2 |

(b) and (d) use the same 8 Sonnet answers: one live run of `claude-sonnet-5-5` ($0.1543), then
cache hits with the network refused.

### Per company

| Company | n | Rules decided | Rules unsafe | Rules ctl FAIL | Sonnet decided | Sonnet unsafe | Sonnet ctl FAIL |
|---|---:|---:|---:|---:|---:|---:|---:|
| brightline | 11 | 90.9% | 2 | 0 | 63.6% | 0 | 1 |
| ember_rye | 12 | 58.3% | 1 | 0 | 33.3% | 0 | 0 |
| keystone | 11 | 81.8% | 3 | 0 | 18.2% | 0 | 0 |
| cedar_valley | 12 | 91.7% | 0 | 0 | 33.3% | 0 | 0 |
| lumen_loom | 10 | 70.0% | 1 | 1 | 40.0% | 0 | 1 |
| riverbend | 10 | 90.0% | 2 | 0 | 40.0% | 0 | 0 |
| halvorsen | 10 | 80.0% | 2 | 0 | 40.0% | 0 | 0 |
| northstar | 11 | 90.9% | 1 | 1 | 72.7% | 0 | 1 |

### Per defect type

| Family | n | Rules: FAIL / REVIEW / **PASS** | Sonnet: FAIL / REVIEW / **PASS** |
|---|---:|---|---|
| wrong_amount | 7 | 7 / 0 / **0** | 7 / 0 / **0** |
| wrong_account | 3 | 3 / 0 / **0** | 3 / 0 / **0** |
| wrong_direction | 3 | 2 / 0 / **1** | 2 / 1 / **0** |
| contradicted_by_credit | 3 | 1 / 0 / **2** | 2 / 1 / **0** |
| cause_in_other_period | 3 | 0 / 1 / **2** | 2 / 1 / **0** |
| cause_too_small | 4 | 0 / 0 / **4** | 2 / 2 / **0** |
| wrong_cause | 4 | 0 / 2 / **2** | 0 / 4 / **0** |
| fabricated_cause | 3 | 0 / 2 / **1** | 0 / 3 / **0** |
| control (correct) | 57 | 2 FAIL / 6 REVIEW / 44 PASS / 5 missed | 3 FAIL / 36 REVIEW / 16 PASS / 2 missed |

**Read with the synthetic numbers.** On the generator's held-out phrasing the README reports 0
unsafe PASS and 0 control FAIL for the rules, at 11% decided. Here the rules decide 81.6%, and
that figure is not good news. The checks that decide amounts and directions work on this
commentary: all 7 wrong amounts and all 3 wrong accounts are caught by both extractors. The
checks that decide causes almost never ran under the rules (14 of 82 extracted claims had a
reason read). When a cause is not read, the rules do not send the claim to a person. They pass
it.

With Sonnet proposing, the model supplies the reason span for nearly every sentence. Once a
reason is read, the guard sends most of them to REVIEW: 31 of the 36 control REVIEWs are
`WEAK_REASON_MATCH`, where some written words of the reason match nothing in the memos. That
removes the unsafe PASSes but leaves 16 of 57 correct explanations passed.

### (c) The reviewer loop

`teach-sim --suite independent` plays a reviewer who reads the key. It teaches from half the
companies (brightline, keystone, lumen_loom, halvorsen) and measures the other half with rules
plus lessons, then the other way round. It uses the `teachsim.py` rule: teach only from a
correct claim in REVIEW because its support rests on model terms, where confirming those terms
makes it PASS.

| Taught on | Lessons | Held half: decided before → after | Unsafe PASS | Control FAIL |
|---|---:|---|---:|---:|
| brightline, keystone, lumen_loom, halvorsen | 0 | 82.2% → 82.2% | 4 → 4 | 1 → 1 |
| ember_rye, cedar_valley, riverbend, northstar | 0 | 81.0% → 81.0% | 8 → 8 | 1 → 1 |

No lesson qualified. Only two correct claims sat in REVIEW on model terms, and confirming their
terms would have made each a FAIL, not a PASS. For RB-03, "pantry" matches the 2 of 6 grant
payees whose names contain it (33%). For NSF-02, "fuel card" carries 73% of a price-and-volume
change. A wider, scratch-only reviewer that also confirms `WEAK_REASON_MATCH` controls (the
script stays in `.proven/`, uncommitted) taught 10 + 5 lessons. They changed nothing with the
rules on the held half and moved one control to PASS in each direction with Sonnet, with no
new FAIL or unsafe PASS. I did not trace which lesson fired. The reason is structural: a lesson
triggers on a stated reason's exact wording, and eight companies never word a cause the same
way. Lessons might transfer from one month to the next within a company. This suite cannot
measure that, since it has one month per company. The README's 88.6% after lessons depends on
the generator's finite phrase pool repeating, which real commentary does not.

### (d) Why `--anchor-model-terms` stays off: not shown here

On this set the experimental policy raised decided from 42.5% to 57.5% (13 more controls
passed) **without** an unsafe PASS. The README's 12 unsafe PASSes under this policy came from
synthetic closes. This suite does not reproduce them, and 30 wrong claims cannot show the
policy is safe. The case for keeping it off still rests on the synthetic evidence.

## 3. Every unsafe PASS and control FAIL

Ledger facts are from the key (`proven/examples/independent/*/key.json`) and are verified by
`check_key.py`. "Rules" is `extract.py` plus `claims.read_sentence`.

### Rules: 12 unsafe PASSes, one mechanism with a variant

**Mechanism A: an unread reason is treated as no reason (11 claims).** `claims.split_reason`
recognises a reason only after `due to`, `because (of)`, `driven by`, `as a result of`,
`reflecting`, `attributable to`, `owing to`, `thanks to`, `on the back of`, or `on` directly
followed by `higher/lower/increased/decreased/additional`. Otherwise `driver` is `None`, the
attribution check is skipped ("no reason stated"), and the verdict comes from direction and
amount alone. Each sentence below states a cause the ledger contradicts:

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

The README promises that "a reason we cannot find is REVIEW, never FAIL". Here the reason is
never looked for, and the outcome is PASS. The synthetic phrasing always used a connector the
rules know, so the generator could not expose this.

**Mechanism A′: unread direction plus magnitude-only comparison (BRT-06).** *"Contractor spend
ticked up about $2.8K with Polaris QA coming on."* Contractors fell by $2,794.25: Ana Ribeiro's
contract ended (JE-104682, −$6,200), and the new Polaris QA SOW is $3,800 (JE-104791).
`_UP`/`_DOWN` have no "ticked up", so the direction is `None` and the direction check is
skipped. `verify_claim` then compares the stated $2.8K with `abs(change)`, so the change check
agrees. "with" is not a connector, so no reason is read either. Verdict: PASS, *"Agrees with
the ledger: amount."* A figure with no readable direction is checked by magnitude and can
pass a claim whose direction is wrong.

**Suggested fixes (not made: `claims.py`/`verify.py` belong to other streams).**

1. When the head of a sentence ends in a figure and the rest of the sentence still has content
   words (after `on`, `for`, `as`, `with`, `after`, `from`, a comma-apposition, a colon,
   `mostly/nearly all/all of it`), either read that remainder as the reason or raise an
   advisory `REASON_NOT_READ`. Either way the claim cannot PASS on its figures alone.
2. Do not let a change check pass on magnitude when no direction was read. Or add "ticked
   up/down", "came down", "eased", "edged" to the direction words. The first is the safer fix.
3. More generally: count a PASS on figures alone separately from a PASS with its cause checked,
   in the report and the benchmark (this suite's `cause checked` column).

Strict expected-failure tests pin each of these in `proven/tests/test_independent.py`
(`test_unread_reason_does_not_pass[...]`, `test_unread_direction_does_not_pass`,
`test_no_unsafe_pass_with_rules`).

### Rules: 2 control FAILs

**LL-02: two claims in one sentence.** *"Paid social was up ~72% as we put spend behind the
Hearth fall launch on SocialReach and Clipstream, funded in part by pulling about $4K out of
search."* Both halves are right: paid social +71.8%, paid search −$4,050. The rules make one
claim per sentence and resolve the first alias (Paid Social). `read_figures` then takes the
first money figure in the sentence ($4K, which belongs to search) as paid social's change.
Result: `WRONG_AMOUNT` (confirmed), so FAIL. *Fix:* a money figure that follows a second
account's alias should not be attributed to the first. When a sentence names two accounts,
assign figures by position or go to REVIEW. Pinned by
`test_second_accounts_figure_is_not_the_firsts`.

**NSF-11: "flat at about $9K".** Tolls & permits went from $9,060 to $9,200 (+$140). The
balance cue `_CURRENT_CUE` needs "at" right before the figure, so the hedge "about" breaks it.
"$9K" is read as the change, and the change check fails ($9K against +$140). Ember's
"Occupancy was flat at $41.3K." passes because no hedge intervenes. "Flat" is not read as a
direction either. *Fix:* allow hedges (about, roughly, approximately, ~) between a balance cue
and its figure, and treat "flat/unchanged" as a stated direction of zero. Pinned by
`test_flat_at_about_is_a_balance`.

### Sonnet (default guard): 0 unsafe PASSes, 3 control FAILs

Every one of the 12 rules unsafe PASSes was FAIL or REVIEW with Sonnet: KMC-09, ER-11, RB-07,
HPC-08 and NSF-10 FAIL; the rest REVIEW. The protection came from the model **proposing the
reason span**: `admit()` keeps it because it is a span of the sentence, and from then on the
written words decide. It did not come from the model's search terms. The safety therefore
depends on the model finding every reason. Where a proposal leaves the reason out and the rules
cannot read it either, "a proposal can add to the reading, never subtract from it" protects
nothing, because there is nothing to keep, and the claim falls back to mechanism A.

**LL-02** fails as under the rules. Sonnet also reads the sentence as one claim, and admit()
keeps the rules' $4K.

**NSF-11** fails a second way. Sonnet proposed `current_text="$9K"` (right: a balance).
`admit()` then saw that the rules read the same "$9K" as a change, which the proposal had left
out, and **kept it as the change too** (note: "change figure written in the sentence was left
out of the proposal; kept"). The current check agrees and the change check FAILs. The "never
subtract" rule, meant to stop a model from dropping a figure, here turns the model's correct
reading into a control FAIL. *Fix:* when a proposal places a figure's exact span in one role,
do not also keep the rules' reading of that span in another role. Pinned by
`test_balance_proposal_is_not_also_a_change`.

**BRT-02: a cause split across two vendors.** *"Hosting & infrastructure was up ~$31k (roughly
50%) as onboarding the Meridian Health account drove both compute and warehouse usage."*
Correct: compute (JE-104614 → JE-104718, +$21,832) plus data warehouse (JE-104620 → JE-104723,
+$9,264) is 99.6% of +$31,234. The rules read no reason ("as") and passed it. With Sonnet's
reason span, the written word "compute" matches the compute bills, and it is a lexicon term
(`cloud_usage`). "warehouse" matches nothing: the warehouse bill's memo says "Capacity
credits" and the vendor is Glacier Data Cloud. Because a declared lexicon term vouched for the
match, `WEAK_REASON_MATCH` did not fire. The bound transactions carry 70%, under the 75% that
"as" (read as full) needs, so the claim got `PARTIAL_EXPLANATION` (confirmed) and FAILed. This
is the README's "single word binds one of a cause's invoices" mechanism, reached through a
*lexicon* term rather than a model term. The FAIL guard covers only model terms. *Fix:* when a
reason has other content words that match nothing (here "warehouse"), a partial share from a
lexicon-vouched subset should be advisory (REVIEW), not confirmed. Pinned by
`test_split_vendor_cause_does_not_fail`.

### Key corrections made after the first checker run

None. No commentary, key or ledger was changed after `1e33dd3`. The changes listed in §1 were
all made before it.

## 4. What a real pilot would still need

- **Real books and real commentary**: a GL export and the controller's own variance memo for
  several months of at least three companies, labelled by someone who did not write either.
  This suite is a stand-in written by an AI model that had read the README.
- **Fix mechanisms A and A′ first.** On real commentary an unread reason is the common case,
  not the edge case. Until then, the rules extractor's PASS means "the figures agree", and the
  report should say so.
- **Month-over-month lesson measurement within one company**, the only setting where verbatim
  lessons can transfer, and the one this suite cannot test.
- **Two-claim sentences and balances written with hedges**, both common in real memos and both
  sources of control FAILs here.
- **Second-reader labels.** One author wrote the commentary and the key, and a script checked
  only the arithmetic.

## Files

- `proven/examples/independent/<company>/{chart.json, ledger.csv, commentary.txt, key.json}`,
  `suite.json`: the suite.
- `benchmarks/independent/build_ledgers.py`, `tb.py`, `check_key.py`: builder, trial balance,
  key verifier (no `proven` imports).
- `proven/independent.py`: loader, matcher, scorer, teach-and-measure.
- `proven/tests/test_independent.py`: offline tests and the strict expected failures.
