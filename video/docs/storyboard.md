# Storyboard

1920×1080, 30 fps, 3,540 frames (118 s). Scene ranges live in `src/timeline.ts` (`SCENES`); every boundary is on a
15-frame beat and every boundary is a carried element (the column "Carried out" names it).

The brief for this cut: two minutes at most, mostly a walkthrough of the real product, and only what works. Scenes
2–5 (frames 240–2325, 69.5 s, 59% of the runtime) are real captures of the console; the rest is the hook, one
architecture diagram, the proof numbers, one path-forward line and the end card. Grounds: bone, and the console's own
page colour during captures; obsidian only for the proof. Chartreuse appears only for PASS, "Gate: safe", a kept
lesson and the wordmark; red only for FAIL; amber only for REVIEW.

| # | Frames | Time | Scene | What is on screen | Carried out |
|---|---|---|---|---|---|
| 1 | 0–240 | 0:00–0:08 | Hook | One real month-end sentence from the Lumen close ("Legal costs rose $90K because of our Series B funding round.") at headline size; account, amount and reason marked; the ledger rows it must agree with rise beneath it and a reading band walks them. | The sentence fades over the console as the camera finds its editor. |
| 2 | 240–960 | 0:08–0:32 | Walkthrough: paste and verify | **Real capture**, Lumen Robotics, Rules (offline). Empty editor → cursor, "⌘ V" → the commentary appears → cursor clicks **Verify** → Coverage (callout: 9 claims checked · 77.8% decided without a person) → the explanation underlined in verdict colours → **Claims** tab → C1's detail: "States $90K; the ledger shows +$44,900.", FAIL, Ledger and Stated rows ringed in red (callout: "The ledger contradicts the sentence: FAIL") → Findings: POSSIBLE_MISCLASSIFICATION, TX-2068 $45,100 "Series B — investor rights agreements" in Marketing & Advertising (other account), ringed amber (callout: "$45,100 of Series B legal work, booked to Marketing"), then the line "Reclassified … would change by +$90,000 — which agrees with the stated $90K" (callout: "Moved back: +$90,000, what the sentence said"). | The camera, from the Lumen findings into the Brightfield header. |
| 3 | 960–1470 | 0:32–0:49 | Walkthrough: a claim waits | **Real capture**, Brightfield Health, Extractor "Claude (sends narrative only)", model claude-sonnet-5-5. **Verify** → the console's note "Claude receives the explanation text and chart of accounts only, never transactions." under the run line "answered from the proposal cache, no request made" (callout: "The model never sees a transaction") → C1 REVIEW → Searched: "promo, campaign, sale event, … (model)" (callout: "Search words the model proposed") → Findings: SUPPORT_RESTS_ON_MODEL_TERMS with TX-1051 / TX-1061 (callout: "'campaign' matched these two") → sidebar **Learned** → Teach next: "our biggest promotion of the year" → campaign, 1 waiting (callout: "Teach next: waiting for a person"). | The camera, from the queue to the sidebar. |
| 4 | 1470–1980 | 0:49–1:06 | Walkthrough: safety gate, confirm once | **Real capture.** Sidebar **Review** → Resolve, Accept convention, Teach Proven filled with the phrase and "campaign" (callout: "The lesson: this phrase means this ledger word") → **Check with the safety gate** → "Gate: safe · replayed on … known claims; no wrong explanation passes and no right one fails; … This claim: REVIEW → PASS" ringed in chartreuse (callout: "Replayed against known answers before anything is stored") → tick "I checked that the matched transactions really are this cause", a short reason → **Record** → C1 PASS (callout: "Confirmed once: PASS") → sidebar Learned 1 (callout: "One lesson, kept for every close"). | The camera, from the sidebar into the Cobalt header. |
| 5 | 1980–2325 | 1:06–1:17.5 | Walkthrough: next close, rules alone | **Real capture**, Cobalt Freight, Rules (offline). Run line "rules/0.1 · … · nothing left this machine" (callout: "Next close · a different company") → Extractor "Rules (offline)" (callout: "Rules only: no model in the loop") → C1 PASS → Searched "campaign (learned)" ringed in chartreuse (callout: "Decided by the word a reviewer confirmed"). | The capture fades to bone. |
| 6 | 2325–2655 | 1:17.5–1:28.5 | Architecture loop | One diagram, built in the order a claim travels, a token following it: explanation + chart of accounts → proposer (dashed = untrusted; "a language model · proposes claims · no verdict field") → admission → checker ← ledger → PASS / FAIL / REVIEW → reviewer → safety gate → lessons (holding the walkthrough's lesson as a chartreuse pill) → back into the checker: "next close: the rules decide, no model". Adapted from the archived S4Loop, its timings slowed 1.1×. | The ground turns obsidian. |
| 7 | 2655–3255 | 1:28.5–1:48.5 | Proof | Left, all scene: "Kill criteria · on every benchmark", 0 correct explanations failed, 0 wrong explanations passed. Right, first: "11 unseen companies · industries never used in development", **81.7%** of claims decided after teaching, Claude Sonnet 5.5 proposing, held-out phrasing, 0 correct failed · 0 wrong passed. Right, then: "Pre-registered test · 13 new companies · scored once", **0** of 429 wrong explanations approved, **0** of 1,193 correct ones rejected, 78.5% decided by the rules after teaching (Sonnet proposing), and in small type "Checker frozen and test committed before the companies were written. Wrong-approval rate under 0.7% at 95% confidence, counting claims." | The ground returns to bone. |
| 8 | 3255–3420 | 1:48.5–1:54 | Path forward | "Next: A local open-weight proposer, so no sentence leaves the building." A boundary labelled "Your machine" already holds Checker and Ledger; a dashed Proposer card ("open-weight, local") slides inside. No performance claim. | Text lifts away; bone. |
| 9 | 3420–3540 | 1:54–1:58 | Close | The chartreuse band draws, "Proven" rises onto it; "The model proposes. The ledger decides."; the one-line description; held end frame (≥ 45 frames). | (end) |

## The captures (what is real, what is added)

- **Source.** `npm run capture` (`scripts/capture-console.ts`, Playwright, Chromium, 1440×1500 CSS px viewport at
  3× device scale) drives the repo's own console (`proven/server.py` + `proven/web/`, unchanged) through the flow
  above: real clicks, a real paste into the editor, real Verify, gate and Record requests. It writes
  `public/capture/*.png` and `src/data/capture.ts` (the boxes of the elements the video zooms to).
- **Which server.** A private copy started by the capture script (`scripts/py/console_replay.py`, port 8766), not the
  console on 8765, so recording a lesson never writes to the repo's `.proven/`. Its state lives in
  `.scratch/console-data/` and is wiped on every start. It differs from `python -m proven serve` in three ways:
  1. the Claude extractor **replays** Claude Sonnet 5.5's cached proposals for the Brightfield close
     (`.scratch/pydata/cache`, made by `scripts/py/walkthrough_data.py`); nothing is sent: an uncached explanation
     raises, and the network guard is installed, so any outbound connection is refused. The console itself says so
     on screen ("answered from the proposal cache, no request made, 0 tokens");
  2. the Close menu also lists the two held-out test-split closes the walkthrough uses (Brightfield Health, seed 0;
     Cobalt Freight, seed 1155; held-out phrasing), built by `proven.synth.generate` exactly as the benchmark does;
  3. the open-weight option is left out of the Extractor menu (no local model runs during a capture).
- **Added on the page before each screenshot.** Vendor names are replaced with a grey "vendor" tag (in the textarea, a
  grey bar over the word): the synthetic ledgers use real company names (an ad network, a cloud provider, airlines),
  which the video never shows. "AWS" in the Lumen commentary is covered the same way. The editor was dragged open by
  its resize handle to show the whole commentary. Nothing else on the page is changed.
- **Added by the video.** The camera (zooms and pans), the cursor and its click ripples, the "⌘ V" keycap, rings, the
  spotlight that dims everything but the marked element, and the callouts, all in the video's own type
  (`src/components/CaptureView.tsx`). Callouts restate what the console shows or say what it means; the only numbers
  in them (9 claims, 77.8%, $45,100, +$90,000) are on the captured screen and in `results.ts` / `cases.ts`.
- **Legibility.** Reading shots use 2.15–3.3 frame px per CSS px (a slow push of up to 6% adds to that during a
  hold), so the console's 13–15 px text lands at 28–50 px; the two detail overviews (Lumen C1, Cobalt C1) are the
  2.15 ones. Wider shots (the opening, Coverage, the pull-back to Verify) are on screen for under two seconds each
  and carry no reading.
- **Camera.** `CaptureView` fits each focus rect into the frame above the subtitle band, eases between them (zoom in
  log space), crossfades between screenshots, and pushes in slowly during holds so no reading hold is a frozen frame.
  Each walkthrough scene starts from the exact pose the previous one ended on (`focusAt`).

## Where the data comes from

- Every statistic: `src/data/results.ts`, one entry per number with the repo file it was read from.
- Case data (sentences, ledger lines, checker output): the captures themselves, and `src/data/cases.ts` for the hook
  and the lesson pill in the loop.
- Proof: `RESULTS.bench.heldoutControlFail` / `heldoutUnsafePass` (the zeros), `RESULTS.worlds.unseen` (11),
  `RESULTS.worlds.sonnetDecided` (81.7%), `RESULTS.worlds.sonnetControlFail` / `sonnetUnsafePass` (0 / 0), and
  `RESULTS.preregistered` (13 companies; 0 of 429; 0 of 1,193; 78.5%; under 0.7% at 95% confidence, counting claims),
  from `docs/finetune.md` §9 of the worlds worktree at d75a510.

## What this cut leaves out (on purpose)

The fine-tuned local model's results, the sealed suite, constrained decoding and why the small model lost (scenes
S6–S10 of the 168-second cut) are not in this video. Their scene files are kept in `src/scenes/archive/` (excluded
from the build); the 168-second render is `out/archive/proven-demo-silent-168s-12-scenes-v3.mp4` and its stills are in
`out/archive/stills-168s-cut/`.

## Rules this follows

See `README.md`, "Hard rules". In short: every animated value is a function of the frame; easing only from
`EASE`/`SPRING`; nothing under 28 px in the video's own type; nothing important in the face-cam corner (bottom left)
or under a subtitle; the product's own wordmark only.
