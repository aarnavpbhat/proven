# Rewording a wrong explanation until it passes

The benchmark's "0 unsafe PASS" was measured on sentences the generator wrote. This
note records what happened when wrong explanations were reworded by hand and by a
deterministic fuzzer, what was fixed, and what is still open.

## What was found

Before commit `f597068`, the rules checker gave **PASS** to wrong explanations
reworded in five ways. Each keeps the account, the figures and the stated cause.

| Rewording | Example (the ledger disagrees with each) | Why it passed |
|---|---|---|
| Reason connector the readers do not know | "Cloud costs rose approximately $38K (122%) compared with September, **fueled by** the model training run." | No reason was read, so the cause was never checked; amount and direction agreed. |
| Negation or contrast inside the reason | "…driven by the DevSummit sponsorship, **not the launch campaign**." | The contrasted cause's words were searched as if they were the reason. |
| Direction word the readers do not know | "Contractor spend **slid** approximately $20K…" (it rose $20,595) | No direction was read, and the amount was compared without its sign. |
| Figure placed after the connector | "Occupancy dropped, reflecting the new Austin office lease in September, **by $35K**." | Only the text before the connector was read for figures. |
| Amount written in words | "The **thirty-five thousand dollar** decrease in occupancy…" | No figure was read. |

The fuzzer in `proven/tests/test_unread.py` applies these rewordings to every
defective sentence in 60 benchmark closes: **231 of 900 rewordings were passed**.

## What was changed

A FAIL needs one thing shown wrong. A PASS claims the whole sentence agrees with the
ledger, so it is now withheld (the verdict becomes REVIEW, with the reason shown)
unless all of the following hold (`claims.unread`):

- every money and percentage figure in the sentence was checked, and no amount is
  written in words;
- a reason was read, and it contains no negation or contrast;
- a direction word was read, and the sentence does not use both a rise and a fall word;
- the sentence names one account;
- every word outside the stated reason is in a closed list of words the readers
  understand (`claims.READ_WORDS`), or is part of an account name.

## Results after the change

| Check | Before | After |
|---|---|---|
| Reworded defects passed (fuzzer, 900 rewordings) | 231 | 0 |
| Seen wording, rules: decided / controls passed | 90.1% / 783 of 810 | 90.1% / 783 of 810 |
| Held-out wording, Sonnet lessons from 110 closes: decided | 88.6% | 88.6% |
| Paraphrase wording, Sonnet lessons from 220 closes: decided | 83.0% | 83.0% |
| Sonnet as extractor, seen wording, 40 closes: decided | 85.2% | 85.2% |
| Showcase output | — | identical |

The guard cost no coverage on any benchmark, because every sentence that passes
today already has a read reason, a read direction and only known words around it.

## A proposer that lies

`LyingProposer` in the same test file plays a compromised model: for each defective
sentence it proposes every span as the reason, the account's real vendor and memo
words as search terms, figures dropped, and every other account. Of 6,276 such
proposals over 100 closes, **none was passed, before or after the change**. The
admission step and the model-terms guard already held; the hole was in the
deterministic reader.

## Not done, and still open

- No adaptive model-driven attacker and no prompt-injection runs against the hosted
  proposer were carried out. The agent assigned to them was stopped by a safety
  classifier before writing code, and that part of the plan was dropped rather than
  reworked. No API money was spent on this stream.
- `READ_WORDS` is a closed list tuned to plain month-end wording. Real commentary
  will use words outside it and go to REVIEW; that is the intended failure direction,
  but it has not been measured on real closes.
- Lesson triggers match without a closing word boundary, and a lesson removes its
  trigger's words from the search. Neither produced a wrong PASS in testing; neither
  has been fuzzed.
- The sentence is assumed to compare the ledger's two periods. A sentence that names
  a different month is not detected.
