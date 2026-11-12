# Narration script

Fifteen lines, 244 words, for a 118-second cut (3,540 frames at 30 fps). No line needs more than 2.5 words per
second (150 words per minute); most need about 2. Every line's words are also in `src/timeline.ts` (`VO`), which
drives the subtitles; `npm run check-data` fails if this file and the timeline drift apart. Change a line in **both**
places.

Rules the script follows: concrete, no hype words, no number that is not on screen or in `src/data/results.ts`, and
only what works. It says nothing about the fine-tuned model's results; the one local-model line (14) is a plan, with
no performance claim. Numbers are spelled the way they should be said.

Speakers (suggested split; change freely in `src/data/voice.ts`):
speaker 1 — lines 1, 11–15 · speaker 2 — lines 2–7 (the walkthrough up to the waiting claim) ·
speaker 3 — lines 8, 9, 10 (gate, confirm, next close).

Timecodes are video time (30 fps). "First word at" is where the first spoken word should land; the take may start
earlier with room tone (see `docs/recording-guide.md`, "lead"). "Must end by" is the end of the line's slot.


## S1 · Hook — 0:00.0–0:08.0 (frames 0–240)

**Line 01** · first word at 0:00.5 (frame 15) · must end by 0:07.5 (7.0 s) · 17 words

> Every month-end close, finance teams explain why each number moved. Proven checks those explanations against the ledger.


## S2 · Walkthrough: paste and verify — 0:08.0–0:32.0 (frames 240–960)

**Line 02** · first word at 0:08.5 (frame 255) · must end by 0:12.5 (4.0 s) · 7 words

> Paste the month's commentary and press Verify.

**Line 03** · first word at 0:13.0 (frame 390) · must end by 0:18.0 (5.0 s) · 12 words

> Each claim gets a verdict, and Coverage shows how much was checked.

**Line 04** · first word at 0:18.0 (frame 540) · must end by 0:24.0 (6.0 s) · 9 words

> Legal says ninety thousand; the ledger shows about forty-five.

**Line 05** · first word at 0:24.5 (frame 735) · must end by 0:31.5 (7.0 s) · 13 words

> The evidence shows why: a forty-five-thousand-dollar Series B invoice was booked to Marketing.


## S3 · Walkthrough: a claim waits for a person — 0:32.0–0:49.0 (frames 960–1470)

**Line 06** · first word at 0:32.5 (frame 975) · must end by 0:40.0 (7.5 s) · 18 words

> Here a language model proposes the claims. It sees the text and chart of accounts, never a transaction.

**Line 07** · first word at 0:40.5 (frame 1215) · must end by 0:48.5 (8.0 s) · 20 words

> Its word, campaign, found the cause. But only the model's word supports it, so the claim waits for a person.


## S4 · Walkthrough: safety gate, confirm once — 0:49.0–1:06.0 (frames 1470–1980)

**Line 08** · first word at 0:49.5 (frame 1485) · must end by 0:57.5 (8.0 s) · 20 words

> The safety gate replays the lesson against explanations with known answers: no wrong one passes, and no right one fails.

**Line 09** · first word at 0:58.0 (frame 1740) · must end by 1:05.5 (7.5 s) · 13 words

> The reviewer checks the two transactions and confirms it once. The claim passes.


## S5 · Walkthrough: next close, rules alone — 1:06.0–1:17.5 (frames 1980–2325)

**Line 10** · first word at 1:06.5 (frame 1995) · must end by 1:17.0 (10.5 s) · 26 words

> On the next close, at another company, the rules run alone. The same reason passes on the learned word. No model ran; nothing left the machine.


## S6 · Architecture loop — 1:17.5–1:28.5 (frames 2325–2655)

**Line 11** · first word at 1:18.0 (frame 2340) · must end by 1:28.5 (10.5 s) · 26 words

> The model only proposes; its reply has no verdict field. Deterministic code decides from the ledger, and each confirmed lesson moves work from people to rules.


## S7 · Proof — 1:28.5–1:48.5 (frames 2655–3255)

**Line 12** · first word at 1:29.0 (frame 2670) · must end by 1:39.5 (10.5 s) · 26 words

> On every benchmark, every wrong explanation is blocked, and no correct one is rejected. On eleven unseen companies, with Sonnet proposing, almost eighty-two percent are decided.

**Line 13** · first word at 1:40.0 (frame 3000) · must end by 1:48.0 (8.0 s) · 20 words

> Then we froze the checker, wrote thirteen new companies, and scored once: all four hundred twenty-nine wrong explanations were blocked.


## S8 · Path forward — 1:48.5–1:54.0 (frames 3255–3420)

**Line 14** · first word at 1:49.0 (frame 3270) · must end by 1:53.5 (4.5 s) · 11 words

> Next: a local open-weight proposer, so no sentence leaves the building.


## S9 · Close — 1:54.0–1:58.0 (frames 3420–3540)

**Line 15** · first word at 1:54.5 (frame 3435) · must end by 1:57.0 (2.5 s) · 6 words

> The model proposes. The ledger decides.


---

## Notes on wording

- Lines 2–10 narrate real captures of the console (`public/capture/`, `scripts/capture-console.ts`); what is said is
  what the screen shows at that moment.
- Line 3: Coverage on the Lumen close reads 9 claims of 10 sentences with figures, 77.8% decided
  (`RESULTS.showcase`); the callout shows those two numbers.
- Line 4: the ledger change is +$44,900; "about forty-five" is the spoken rounding.
- Line 5: the misbooked invoice is TX-2068, $45,100, "Series B — investor rights agreements", booked to Marketing &
  Advertising; the console's finding says that reclassified, Legal & Professional Fees would change by +$90,000,
  which agrees with the stated $90K.
- Line 6: the console's own note when Claude is the extractor: "Claude receives the explanation text and chart of
  accounts only, never transactions." The capture replays Claude Sonnet 5.5's cached proposals; the console's run
  line says "answered from the proposal cache, no request made".
- Lines 7–9: the claim's finding is `SUPPORT_RESTS_ON_MODEL_TERMS`; the model's word "campaign" matched two
  transactions (TX-1051, TX-1061). The gate result is the console's real output for that lesson ("Gate: safe … This
  claim: REVIEW → PASS").
- Line 10: Cobalt Freight, Rules (offline); the run line reads "nothing left this machine"; Searched shows
  "campaign (learned)".
- Line 12: "on every benchmark, two numbers stay at zero" is the README's kill criteria (correct explanations failed,
  wrong explanations passed), 0 / 0 on every benchmark in `results.ts`. "Almost eighty-two percent" is 81.7%: 11
  unseen worlds (industries never used in development), Claude Sonnet 5.5 proposing, held-out phrasing, fully taught
  (`RESULTS.worlds.sonnetDecided`), with 0 control FAIL and 0 unsafe PASS.
- Line 13: the third suite, registered in advance (`docs/finetune.md` §9, "An independent test, registered in
  advance"; registration commit a5b1e2f, score d75a510; checker and lesson rules frozen at 468605b): 13 companies in
  industries used nowhere else, written after the test was committed, scored once. Sonnet proposing, held-out
  phrasing: 0 of 429 wrong explanations passed (unsafe PASS), 0 of 1,193 correct ones failed, 78.5% decided after
  teaching (`RESULTS.preregistered`). The screen adds the bound, always with its confidence level: wrong-approval
  rate under 0.7% at 95% confidence, counting claims (exact one-sided Clopper-Pearson, 0.696%; counting a world as a
  trial it is 20.6%, which the video does not show). Never "guaranteed" or "proven safe".
- Line 14: a plan, not a result. Nothing in the video says how a local proposer performs.
