# Critique log

Rubric: `~/personal/projects/proven-demo-editor/docs/critique-rubric.md` (Clarity, Motion, Continuity, Rhythm,
Type & layout, Restraint, Truthfulness; 1–10; anything under 8 gets fixed). Newest pass on top.

---

## Pass 6 · the two-minute cut (118 s, mostly real product)

Brief: at most 120 s, mostly a walkthrough of the real product, only what works. The 168 s cut is archived
(`out/archive/proven-demo-silent-168s-12-scenes-v3.mp4`, its stills in `out/archive/stills-168s-cut/`).

**What was reviewed.** Every still at 1, 6, 11 … 116 s and the last frame (25 stills, `out/stills/`), each looked at
full size from the final render, plus targeted frame sheets of every scene during the work (`npm run frames`).
Automated: `npm run text-check` (every 5th frame) 0 issues, `npm run dead-time` no static stretch over 36 frames,
`npm run cut-check` all 8 boundaries continuous, `npm run typecheck`, `npm run purity` and `npm run check-data` clean.

**Found and fixed**

- *Captures, cramped first take.* At a 1280×900 viewport the console's claim-detail pane showed only ~400 px of its
  working, so every zoom cut through the section being read. Re-captured at 1440×1500 CSS px (3× scale), with the
  window scrolled so the sticky pane stands at full height and the pane scrolled to the section under discussion.
- *Captures, the Lumen editor* opened at 14 rows, cutting the pasted commentary mid-way; the capture drags it open
  (its resize handle) to the text's height.
- *Captures, a real vendor name in the textarea* ("AWS" in the Lumen commentary): the grey "vendor" tag did not fit a
  monospace word that short and spilled over the next words; it is now a plain grey bar the size of the word. Vendor
  names in the rest of the page are replaced by a grey "vendor" tag.
- *Callouts over the content they described* (11 s, 21 s, 36 s, 41 s, 51 s, 71 s): callouts sat mid-frame over table
  rows and the coverage bar. All moved to one band at y 846–918, just above the subtitle, and the camera's stage
  stops above it; the FAIL callout at 21 s went lower still (it hid "If reclassified +$90,000").
- *The extractor note ringed before Verify* (36 s): the camera showed "Claude receives … never transactions" on the
  pre-Verify screenshot, so the run line still read "rules/0.1". Reordered: Verify first, then the note under the
  run line that says "answered from the proposal cache, no request made".
- *A ring that covered three lines* (31 s, "+$90,000 … agrees with the stated $90K"): tightened to that one line.
- *Subtitle cue split mid-name* ("Series | B invoice"): an explicit break added before "was booked to Marketing".
- *Loop labels clipped* (81–91 s): "Chart of accounts" ran past its node and the REVIEW chip past the verdict node;
  both nodes widened. The lesson pill's text was at 32 px against 28 px node text; set to 28.
- *Proof subtitle wrap* ("Claude Sonnet 5.5 proposing · held-out phrasing" broke after "held-out"): two set lines.
- *Path forward card off-frame* (text-check, f3235): the Proposer card started at x −170; now it starts on screen.
- *Pre-registered rows touching the two-line eyebrow* (text-check, s7): rows moved down 30 px.
- *Cuts between walkthrough scenes jumped* (cut-check s4, s5): each scene now starts from the exact camera pose the
  previous one ended on, and the end-of-scene rings finish before the cut.
- *Frozen reading holds* (dead-time: six stretches of 42–90 frames on still screenshots): the capture camera now pushes
  in slowly (≤ 6%) during every hold.
- *The 81.7% panel left before its line ended* (frame 2985): the swap to the pre-registered result now waits for the
  end of line 12.

**Added late (coordinator):** the pre-registered third suite in the proof scene (13 new companies, 0 of 429 wrong
explanations approved, 0 of 1,193 correct ones rejected, 78.5% decided, under 0.7% at 95% confidence counting
claims), with narration line 13. Paid for by shortening the loop (15 → 11 s), the next-close scene (by 0.5 s), the
path-forward beat and the end card (by 0.5 s each); 116 → 118 s.

**Known, left as is**

- The console's own text is the console's size: in the two detail overviews (Lumen C1 at 21 s, Cobalt C1 at 76 s) the
  smallest UI labels land at about 28 px; the lines that matter are ringed and restated in a callout.
- At 106 s the Proposer card passes over the "Your machine" border as it slides in (intended motion, 1 s).
- The left column of the proof keeps the generic "on every benchmark" zeros beside the pre-registered zeros; it is
  deliberate (the general claim, then the strongest single test), but it is four zeros on one screen.

---

## Pass 5 · final numbers and the kill-criteria correction (168 s)

- Filled: single-world 3B on the unseen suite (20.9%, 0 / 0), constrained decoding on the unseen suite (0 of 1,100 left
  the grammar, 2.28 s per close, 54.4% as without the mask), the rebuilt 3B on the sealed suite (57.8% / 44.0%, used
  in the narration notes). Only `rl.result` remains pending; it is not on screen.
- Corrected: the kill-criteria story has a second chapter. S9 now shows Sonnet's gap in full (two cards, rules 1–2)
  and the local model's gap as a compact beat (its sealed lessons failed 2 correct explanations per tier and passed 1
  wrong one; the hedged-lesson mechanism on one card; rule 3, commit 814b2d5), then "Three rules: zero and zero at
  every teaching step" with the caveat in large type: written from these breaches, a fit, not a proof. S5's row reads
  "under the final rules"; S8's narration says "under the final lesson rules, no proposer broke a kill criterion";
  S11's second card says the rules were fit to these suites.
- S7's footer now states the measured effect plainly: no score moved.

Checks: typecheck, purity, check-data clean; text check every 3rd frame over all 5040 frames: 4 issues at one S9 hand-
off (chapter 2 began while chapter 1 was still fading), fixed and clean on every frame of that range; dead-time: only
the final hold; cut check: all 11 boundaries continuous.

---

## Pass 4 · revision for the night's results (156 s, 12 scenes)

The story changed: on the unseen worlds the fine-tuned 3B model lost to Sonnet in all 11 worlds (54.4% and 44.8%
against 81.7%, ceiling 89.3%), and the sealed second suite exposed a safety gap in lessons, fixed by
`learned.trim_terms`. Every number moved to the fixed rule (`results.ts`, with sources; the README teaching curve
moved too, 88.6% → 88.2%).

- New order: S1–S5 unchanged in content, then laptop (S6), decoding (S7), the unseen-worlds result (S8), the sealed
  suite and the trim rule (S9, new, 22 s), why it lost (S10), path forward (S11), close (S12). New carries: S5's
  teaching curve flattens into the laptop's base line; S7's search_terms line becomes S8's header; S8's Sonnet bar
  becomes S9's sealed-suite score; S9's trimmed lesson becomes S10's header.
- S8 headline says it plainly: "The small model lost, in all 11 worlds." Bars ranked as measured, the gap measured
  ("27.3 points below Sonnet"), paraphrase tier in one line, the single-world row pending.
- Honesty fixes found while re-reading the sources: kill criteria are claimed only for fully taught rows (the rebuilt
  3B run had 1 control FAIL at 10 and at 25 taught closes); S5's eyebrow now reads "both must be zero", not "zero on
  every benchmark" (Sonnet had 1 control FAIL in one dev-world teaching run).
- Density: S10's second step lost its memo row (matches now light up in the guesses themselves); each step folds to
  one line. S11's cards have 36 px titles and 30 px bodies with half the words.

Checks: typecheck, purity, check-data clean; text check every 3rd frame over all 4680 frames: 0 issues; dead-time:
only the final hold; cut check: all 11 boundaries continuous.

---

## Pass 3 · the rendered file (`out/proven-demo-silent.mp4`, sampled every 2.5 s and around each transition)

The render matches the stills. Two problems found only in the file, both in S6's switch from the worlds to the bars:
the oracle's hollow bar showed as a 2 px vertical sliver before its label arrived, and the frame was nearly empty
for about 12 frames between the two halves. The sliver is now hidden until a bar is 6 px wide, the oracle bar grows
after the ceiling line, and the headline arrives 9 frames after the worlds leave. The unseen-industry list is 38 px
per row so its label no longer sits on the last row. S6 then clean on every frame.

Own scores after pass 3 (same rubric, judged on the rendered file):

| Scene | Clarity | Motion | Continuity | Rhythm | Type & layout | Restraint | Truth |
|---|---|---|---|---|---|---|---|
| S1 Hook | 8 | 8 | 8 | 8 | 8 | 9 | 10 |
| S2 Trust boundary | 8 | 8 | 9 | 8 | 7 | 8 | 10 |
| S3 Console | 8 | 8 | 9 | 8 | 7 | 8 | 10 |
| S4 Loop | 8 | 8 | 9 | 8 | 7 | 8 | 10 |
| S5 Kill criteria | 9 | 8 | 9 | 8 | 8 | 8 | 10 |
| S6 Unseen worlds | 8 | 8 | 8 | 8 | 8 | 8 | 10 |
| S7 Laptop | 8 | 8 | 8 | 8 | 8 | 8 | 10 |
| S8 Decoding | 8 | 8 | 8 | 8 | 7 | 8 | 10 |
| S9 What went wrong | 7 | 8 | 8 | 8 | 7 | 8 | 10 |
| S10 Path forward | 8 | 7 | 8 | 8 | 7 | 8 | 10 |
| S11 Close | 9 | 8 | 9 | 8 | 9 | 9 | 10 |

Still under 8, honestly: type density in S2, S3, S4, S8, S9 and S10 (28–32 px UI and diagram text in a frame that keeps
the bottom band and the face-cam corner empty), S9's second panel (six rows of chips in one view), and S10's cards,
which all enter the same way. These are design limits of showing real UI and real data at 1080p with the face-cam
corner reserved, not bugs; they are the first things to revisit with the owners.

## Pass 2 · independent review (a subagent that saw only contact sheets, the rubric and a product summary)

Its scores (from 480 px thumbnails, so it read 28 px text as "12–16 px"; motion judged from stills):

| Scene | C | M | Co | R | T | Re |
|---|---|---|---|---|---|---|
| S1 | 7 | 6 | 7 | 4 | 6 | 8 |
| S2 | 6 | 6 | 7 | 5 | 4 | 7 |
| S3 | 5 | 5 | 7 | 5 | 4 | 5 |
| S4 | 6 | 6 | 8 | 6 | 4 | 7 |
| S5 | 7 | 6 | 8 | 6 | 6 | 6 |
| S6 | 5 | 5 | 6 | 4 | 5 | 6 |
| S7 | 6 | 6 | 5 | 6 | 6 | 7 |
| S8 | 5 | 6 | 5 | 6 | 4 | 6 |
| S9 | 4 | 5 | 6 | 6 | 3 | 5 |
| S10 | 5 | 5 | 7 | 6 | 4 | 7 |
| S11 | 7 | 6 | 8 | 7 | 5 | 8 |

**Applied**
- S1's second half held still (the push alone passed the dead-time check): a reading band now walks the ledger rows.
- S2's FAIL landed as the scene left (fixed in pass 1, confirmed).
- Ground changes went through mid-grey for 22–24 frames (S4→S5, S6→S7, S8→S9): now 10 frames, under carried
  elements.
- Empty subtitle pills at phrase changes: phrases now swap at once.
- Chartreuse on the Verify button diluted "verified": the button is ink.
- S5 chart labels collided with the line at 11.1% / 39.3%: they sit right of their points.
- S7 left an orphan white screen: the laptop's line work now leaves with the screen's growth; 24 GB demoted to body size.
- S6 bars and S8 lacked a takeaway: headlines "The bars were set before any model was scored." and "Constrained
  decoding: admissible by construction". S6's pending slots have slowly marching dashes (frame-driven).
- S10 jargon ("RLOO over multi-world episodes"): plain words.
- S4's token crossed node labels: it now travels on the edges only and is hidden inside nodes.

**Not applied, and why**
- "Remove every PENDING": the brief requires pending results to be visible slots that fill in from `results.ts`
  with no layout change. They are labelled "result pending", never shown as a number.
- "Scale everything up 1.7–2×": measured on the 1080p frames, the smallest text is 28 px (text check: 0 issues).
  The empty lower band is the subtitle band and face-cam corner, kept clear on purpose.
- "Zoom the camera into S3's panels": a zoom that keeps the console legible cuts the sidebar text at the frame edge;
  the scene uses a 3.5% push and swaps one region at a time instead.
- S9's red annotation ("a vendor's name…") is a flag, which is what red means here.
- S11's band starting left of the P is the Wordmark component's designed overhang (from the editor project).

**Checks after pass 2:** text check every 3rd frame over the whole video: 1 issue (S4 token), fixed; S4 then clean
on every frame. Dead-time: clean except the final hold. Cut check: all ten boundaries continuous.

---

## Pass 1 · build-out (contact sheets every 20 frames, text check every 5th frame)

**Text check, first run: 437 issues in 768 sampled frames.** Root causes and fixes:

- **Face-cam corner (237).** The console's explanation lines and the lower claim rows sat in the bottom-left
  corner. Sentences now start at x 552 with their claim tags at the right edge; list rows are 54 px; S7's "24 GB"
  moved to the right column.
- **Overlaps during carries (114).** S2's words crossed while shrinking from three lines to two; the proposal now
  keeps the hero's three line breaks so the shrink is a near-similarity. The copied fields no longer fly across the
  quote: they rise in place while their source words are underlined. On the way out the words first slide sideways
  on their own lines, then the lines close up. S1's labels are drawn above the words at the cut.
- **Transient covers (21).** Chips and screens that fly over fading content now start after it has gone (S4 → S5
  chips, S6 → S7 title, S7 screen, S8 search-terms line, S9 rule, S3 lesson pill).
- **Under 28 px (53).** Pressed buttons and the popping Learned badge shrank text below 28 px; buttons are 30 px
  and the badge fades and rises instead of scaling. The "›" separator is 30 px.
- **Cut (11).** Subtitle text was clipped while its pill eased wider; the pill now grows at once and only eases
  when it shrinks, and long phrases split at the space nearest the middle.

**Second run: 6 issues**, fixed (carry-out path in S2, S3 push anchor, S9 rule timing). Every frame of the S2,
S3→S4 and S9→S10 transitions then checked clean (`--every 1`).

**By eye, fixed:** S2 FAIL was on screen for 9 frames before the scene left; the arithmetic now lands on beat 38
and holds 40 frames. S4's zone labels collided with the boundary. S6's "Opus" underline sat under "Claude". S10 had a
40-frame hold; a marker now walks the road. The admission line "account is on the chart" overstated `admit()`
(which ignores an off-chart account rather than rejecting the claim); it now reads "an account is used only if it is
on the chart".
