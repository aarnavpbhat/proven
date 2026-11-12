// EVERY statistic shown on screen comes from this file. Each entry cites the repo file it was read from
// (paths relative to the Proven repo: ~/proven/.claude/worktrees/worlds/). Nothing here is estimated.
//
// PENDING RESULTS. Entries with `pending: true` are not known yet (marked TODO(main) in docs/finetune.md). Scenes
// render them as a dashed "result pending" placeholder of exactly the same size, so filling one in changes no layout:
//   1. set `value` to the number (a percentage as e.g. 84.1, a count as e.g. 0),
//   2. set `pending: false`,
//   3. update `source` to the file and table the number came from,
//   4. run `npm run check-data` (it fails if a pending entry has a value or a non-pending entry has none).
// The VO line that mentions a pending number is listed in docs/script.md ("pending lines").

export type Unit = 'pct' | 'count' | 'ms' | 's' | 'gb' | 'params-m' | 'ratio';

export interface Stat {
  /** null only while pending. */
  value: number | null;
  unit: Unit;
  /** Digits after the decimal point when shown. */
  decimals?: number;
  pending?: boolean;
  source: string;
}

const s = (value: number, unit: Unit, source: string, decimals = 0): Stat => ({ value, unit, source, decimals });
export const pending = (unit: Unit, source: string, decimals = 1): Stat => ({ value: null, unit, pending: true, source, decimals });

export const RESULTS = {
  // ── The demo close (Lumen Robotics), rules extractor ────────────────────────────────────────────────────
  showcase: {
    claims: s(9, 'count', 'README.md, "Reviewing a close, step by step", step 2'),
    withFigures: s(10, 'count', 'README.md, step 2 ("9 claims out of 10 sentences with figures")'),
    pass: s(4, 'count', 'README.md, step 2'),
    fail: s(3, 'count', 'README.md, step 2'),
    review: s(2, 'count', 'README.md, step 2'),
    notExtracted: s(1, 'count', 'README.md, step 2'),
    decided: s(77.8, 'pct', 'README.md, step 2 ("77.8% decided (7 of 9)")', 1),
  },

  // ── The standard benchmark: 440-close test split ─────────────────────────────────────────────────────────
  bench: {
    closes: s(440, 'count', 'README.md, "Results" ("440 closes and 1,090 claims per phrasing")'),
    seenDecided: s(90.1, 'pct', 'README.md, Results table, "Decided without a person", seen', 1),
    seenControlFail: s(0, 'count', 'README.md, Results table, "Correct explanations failed", seen'),
    seenUnsafePass: s(0, 'count', 'README.md, Results table, "Unsafe PASS", seen'),
    heldoutDecided: s(11.0, 'pct', 'README.md, Results table, "Decided without a person", held-out', 1),
    heldoutControlFail: s(0, 'count', 'README.md, Results table, held-out'),
    heldoutUnsafePass: s(0, 'count', 'README.md, Results table, held-out'),
    // The two kill criteria stated as what was stopped: 0 unsafe PASS and 0 control FAIL on every benchmark.
    blockedPct: s(100, 'pct', 'README.md, Results table: "Unsafe PASS" is 0 in every row, so every wrong explanation was not approved'),
    keptPct: s(100, 'pct', 'README.md, Results table: "Correct explanations failed" is 0 in every row'),
  },

  // ── Red team ────────────────────────────────────────────────────────────────────────────────────────────
  redteam: {
    rewordings: s(900, 'count', 'docs/redteam.md, "What was found" (fuzzer over 60 closes)'),
    rewordedPassedBefore: s(231, 'count', 'docs/redteam.md, "231 of 900 rewordings were passed"'),
    rewordedPassedAfter: s(0, 'count', 'docs/redteam.md, "Results after the change"'),
    lyingProposals: s(6276, 'count', 'docs/redteam.md, "A proposer that lies" ("Of 6,276 such proposals")'),
    lyingPassed: s(0, 'count', 'docs/redteam.md, "none was passed"'),
  },

  // ── Teaching: lessons confirmed by a (simulated) reviewer, then the rules alone ─────────────────────────
  // README.md, "What confirmed lessons buy": Sonnet terms, held-out phrasing, measured on 220 untaught closes.
  // Values as of commit 0798d4e (the lesson trim rule; the curve moved down 0.4 points, e.g. 88.6% -> 88.2%).
  teachCurve: [
    { taught: 0, lessons: 0, decided: s(11.1, 'pct', 'README.md, teach-sim table, row 0', 1) },
    { taught: 10, lessons: 12, decided: s(38.9, 'pct', 'README.md, teach-sim table, row 10', 1) },
    { taught: 20, lessons: 22, decided: s(59.8, 'pct', 'README.md, teach-sim table, row 20', 1) },
    { taught: 55, lessons: 34, decided: s(83.6, 'pct', 'README.md, teach-sim table, row 55', 1) },
    { taught: 110, lessons: 36, decided: s(88.2, 'pct', 'README.md, teach-sim table, row 110', 1) },
  ],
  teachMeasured: s(220, 'count', 'README.md, "What confirmed lessons buy" ("measures the other 220 with the rules alone")'),
  teachControlFail: s(0, 'count', 'README.md, teach-sim table, every row'),
  teachUnsafePass: s(0, 'count', 'README.md, teach-sim table, every row'),

  // docs/teaching.md, section 2: a reviewer who confirms every wrong explanation the queue shows (P = 1).
  gate: {
    carelessUnsafeOff: s(4, 'count', 'docs/teaching.md, section 2 headline ("4 unsafe PASSes ... without the gate")'),
    carelessControlFailOff: s(14, 'count', 'docs/teaching.md, section 2 headline ("14 failed correct explanations")'),
    carelessUnsafeOn: s(0, 'count', 'docs/teaching.md, section 2 headline ("0 and 0 with it")'),
    carelessControlFailOn: s(0, 'count', 'docs/teaching.md, section 2 headline'),
    medianMs: s(277, 'ms', 'docs/teaching.md, section 1 "Latency" (median over the 36 Sonnet lessons)'),
  },

  // ── Fine-tuning a small local proposer (docs/finetune.md) ───────────────────────────────────────────────
  finetune: {
    loraRank: s(16, 'count', 'docs/finetune.md, section 2 ("LoRA rank 16 on the last 16 layers")'),
    loraLayers: s(16, 'count', 'docs/finetune.md, section 2'),
    trainableM: s(13.304, 'params-m', 'docs/finetune.md, section 2 ("13.304M trainable parameters")', 3),
    trainablePct: s(0.431, 'pct', 'docs/finetune.md, section 2 ("0.431% of the model")', 3),
    memoryGb: s(24, 'gb', 'docs/finetune.md, section 2 ("one Apple M5 Pro laptop with 24 GB of memory")'),
    singleRows: s(1000, 'count', 'docs/finetune.md, section 2 ("1,000 training rows")'),
    singleSeconds: s(1593, 's', 'docs/finetune.md, section 2 ("The run took 1593 seconds")'),
    singleValLossStart: s(0.81, 'ratio', 'docs/finetune.md, section 2 ("0.810 at iteration 1")', 3),
    singleValLossEnd: s(0.001, 'ratio', 'docs/finetune.md, section 2 ("0.001 at iteration 500")', 3),
    worldsRows: s(3027, 'count', 'docs/finetune.md, section 5 ("3,027 rows")'),
    // 7B attempt: no adapter (section 6, "The 7B attempt failed"). Not a number, stated in words on screen.
    worldsTrainWorlds: s(91, 'count', 'docs/finetune.md, section 5 table ("Training | 91")'),
    worldsIters: s(1200, 'count', 'docs/finetune.md, section 5 ("trains for 1,200 iterations")'),
    // The model the video reports (rebuilt targets, qwen3b-worlds2): docs/finetune.md section 6, training/README.md "Other worlds".
    rebuiltRows: s(3176, 'count', 'training/README.md, "Other worlds" ("3,176 train rows"); docs/finetune.md section 6 ("94 of its 3,176 training rows")'),
    rebuiltDefaultRows: s(94, 'count', 'docs/finetune.md, section 6 ("94 of its 3,176 training rows from that world")'),
    rebuiltIters: s(1200, 'count', 'docs/finetune.md, section 14 / training/README.md (rebuilt targets, 1,200 iterations, started from the base model)'),
    // Default-world test split, held-out phrasing, fully taught (section 3 table).
    singleWorldDecided: s(92.5, 'pct', 'docs/finetune.md, section 3 table, heldout, single-world', 1),
    sonnetDefaultDecided: s(88.3, 'pct', 'docs/finetune.md, section 3 table, heldout, Claude Sonnet 5.5', 1),
    // Section 4, the ablation: held-out-cause claims decided (held-out phrasing).
    ablationSawDecided: s(95.3, 'pct', 'docs/finetune.md, section 4 table ("61/64 (95.3%)")', 1),
    ablationNeverSawDecided: s(29.7, 'pct', 'docs/finetune.md, section 4 table ("19/64 (29.7%)")', 1),
    ablationSawHits: s(55, 'count', 'docs/finetune.md, section 4 table ("55/59")'),
    ablationNeverSawHits: s(16, 'count', 'docs/finetune.md, section 4 table ("16/59")'),
    ablationTaught: s(59, 'count', 'docs/finetune.md, section 4 table ("/59")'),
  },

  // ── Unseen worlds (docs/finetune.md, section 5; every row under the lesson rule of section 9) ─────────────
  worlds: {
    unseen: s(11, 'count', 'docs/finetune.md, section 5 table ("Unseen (measured) | 11")'),
    requested: s(12, 'count', 'docs/finetune.md, section 5 ("Twelve unseen industries were requested")'),
    training: s(91, 'count', 'docs/finetune.md, section 5 table'),
    dev: s(4, 'count', 'docs/finetune.md, section 5 table'),
    controls: s(998, 'count', 'docs/finetune.md, section 5 ("998 controls and 363 defects")'),
    defects: s(363, 'count', 'docs/finetune.md, section 5'),
    closesPerWorld: s(100, 'count', 'docs/finetune.md, section 5 protocol ("100 test-split closes")'),
    untaughtDecided: s(10.5, 'pct', 'docs/finetune.md, section 5 ("Untaught, 10.5% of claims are decided")', 1),
    sharedMemoLines: s(0, 'count', 'docs/finetune.md, section 5 overlap audit ("0 memo lines are shared")'),
    // Held-out phrasing, fully taught (50 closes per world).
    oracleDecided: s(89.3, 'pct', 'docs/finetune.md, section 5 table, Oracle (ceiling), heldout', 1),
    sonnetDecided: s(81.7, 'pct', 'docs/finetune.md, section 5 table, Claude Sonnet 5.5, heldout', 1),
    qwenRebuiltDecided: s(54.4, 'pct', 'docs/finetune.md, section 5 table, Qwen2.5-3B multi-world, rebuilt targets, heldout', 1),
    qwenGoldDecided: s(44.8, 'pct', 'docs/finetune.md, section 5 table, Qwen2.5-3B multi-world, gold targets, heldout', 1),
    oracleControlFail: s(0, 'count', 'docs/finetune.md, section 5 table, Oracle, heldout'),
    oracleUnsafePass: s(0, 'count', 'docs/finetune.md, section 5 table, Oracle, heldout'),
    sonnetControlFail: s(0, 'count', 'docs/finetune.md, section 5 table, Sonnet, heldout'),
    sonnetUnsafePass: s(0, 'count', 'docs/finetune.md, section 5 table, Sonnet, heldout'),
    qwenRebuiltControlFail: s(0, 'count', 'docs/finetune.md, section 5 table, rebuilt targets, heldout'),
    qwenRebuiltUnsafePass: s(0, 'count', 'docs/finetune.md, section 5 table, rebuilt targets, heldout'),
    qwenGoldControlFail: s(0, 'count', 'docs/finetune.md, section 5 table, gold targets, heldout'),
    qwenGoldUnsafePass: s(0, 'count', 'docs/finetune.md, section 5 table, gold targets, heldout'),
    // Paraphrase tier, same order (oracle, Sonnet, rebuilt, gold).
    oracleParaphrase: s(76.0, 'pct', 'docs/finetune.md, section 5 table, Oracle, paraphrase', 1),
    sonnetParaphrase: s(63.3, 'pct', 'docs/finetune.md, section 5 table, Sonnet, paraphrase', 1),
    qwenRebuiltParaphrase: s(40.7, 'pct', 'docs/finetune.md, section 5 table, rebuilt targets, paraphrase', 1),
    qwenGoldParaphrase: s(33.4, 'pct', 'docs/finetune.md, section 5 table, gold targets, paraphrase', 1),
    qwenRebuiltGapPoints: s(27.3, 'ratio', 'docs/finetune.md, section 5 ("still 27.3 points under Sonnet on held-out phrasing")', 1),
    qwenWorldsWon: s(0, 'count', 'docs/finetune.md, section 5 ("losing all 11 worlds on both tiers")'),
    // Before the lesson rule (section 9 table), shown only where the change is the point.
    sonnetDecidedBeforeFix: s(82.3, 'pct', 'docs/finetune.md, section 9 table, unseen, Sonnet, heldout, before', 1),
    qwenSingleDecided: s(20.9, 'pct', 'docs/finetune.md, section 5 table, Qwen2.5-3B single-world, heldout', 1),
    qwenSingleControlFail: s(0, 'count', 'docs/finetune.md, section 5 table, Qwen2.5-3B single-world, heldout'),
    qwenSingleUnsafePass: s(0, 'count', 'docs/finetune.md, section 5 table, Qwen2.5-3B single-world, heldout'),
    qwenSingleParaphrase: s(17.5, 'pct', 'docs/finetune.md, section 5 table, Qwen2.5-3B single-world, paraphrase', 1),
  },

  // ── A third suite, registered in advance and scored once (docs/finetune.md section 9, "An independent test,
  //    registered in advance"; commits a5b1e2f (registration) and d75a510 (the score); checker frozen at 468605b).
  //    Sonnet proposing, held-out phrasing, after teaching. The bound is the exact one-sided Clopper-Pearson 95%
  //    limit counting claims as trials, 1 - 0.05^(1/429) = 0.696%; shown only as "under 0.7% at 95% confidence".
  preregistered: {
    worlds: s(13, 'count', 'docs/finetune.md, section 9, "An independent test, registered in advance" ("13 validated")'),
    unsafePass: s(0, 'count', 'docs/finetune.md, section 9, registered-suite table, Sonnet heldout, Unsafe PASS ("0 of 429")'),
    wrongExplanations: s(429, 'count', 'docs/finetune.md, section 9, registered-suite table, Sonnet heldout ("0 of 429")'),
    controlFail: s(0, 'count', 'docs/finetune.md, section 9, registered-suite table, Sonnet heldout, Control FAIL ("0 of 1,193")'),
    rightExplanations: s(1193, 'count', 'docs/finetune.md, section 9, registered-suite table, Sonnet heldout ("0 of 1,193")'),
    sonnetDecided: s(78.5, 'pct', 'docs/finetune.md, section 9, registered-suite table, Sonnet heldout, Decided', 1),
    // The same counts, stated as what was stopped: 429 of 429 wrong explanations not approved, 1,193 of 1,193
    // correct ones not rejected; 100 - 0.696 = 99.3 (rounded down) for the bound.
    blockedPct: s(100, 'pct', 'docs/finetune.md, section 9, registered-suite table, Sonnet heldout: 0 of 429 unsafe PASS, so 429 of 429 not approved'),
    keptPct: s(100, 'pct', 'docs/finetune.md, section 9, registered-suite table, Sonnet heldout: 0 of 1,193 control FAIL, so 1,193 of 1,193 not rejected'),
    blockedBound95: s(99.3, 'pct', 'docs/finetune.md, section 9, registered-suite table: unsafe-PASS rate 95% upper bound 0.696% (claims), so at least 99.3% not approved', 1),
    unsafeBound95: s(0.7, 'pct', 'docs/finetune.md, section 9, registered-suite table, "Unsafe-PASS rate, 95% upper bound (claims)" 0.70% (exact: 0.696%)', 1),
  },

  // ── Why it lost: "cause found" (docs/finetune.md, section 6) ───────────────────────────────────────────────
  causeFound: {
    unseenSonnet: s(84.3, 'pct', 'docs/finetune.md, section 6, first table, Sonnet, unseen heldout', 1),
    unseenQwenGold: s(33.1, 'pct', 'docs/finetune.md, section 6, first table, 3B gold targets, unseen heldout', 1),
    devSonnet: s(80.1, 'pct', 'docs/finetune.md, section 6, dev-worlds table, Claude Sonnet 5.5', 1),
    devQwenGold: s(18.3, 'pct', 'docs/finetune.md, section 6, dev-worlds table, 3B gold targets', 1),
    devQwenRebuilt: s(37.7, 'pct', 'docs/finetune.md, section 6, dev-worlds table, 3B rebuilt targets, 1,200 iterations', 1),
    devQwenUntuned: s(2.6, 'pct', 'docs/finetune.md, section 6, dev-worlds table, 3B untuned, terms only', 1),
    dev7bUntuned: s(32.7, 'pct', 'docs/finetune.md, section 6, dev-worlds table, 7B untuned, terms only', 1),
  },

  // ── The sealed second suite and the lesson rules (docs/finetune.md sections 5 and 9; commits 0798d4e, 814b2d5) ──
  sealed: {
    oracleParaphrase: s(76.1, 'pct', 'docs/finetune.md, section 5, sealed table, Oracle, paraphrase', 1),
    sonnetParaphrase: s(62.2, 'pct', 'docs/finetune.md, section 5, sealed table, Sonnet, paraphrase', 1),
    worlds: s(9, 'count', 'docs/finetune.md, section 5 table ("Sealed (measured) | 9")'),
    controls: s(820, 'count', 'docs/finetune.md, section 5 ("820 controls and 297 defects")'),
    defects: s(297, 'count', 'docs/finetune.md, section 5'),
    sonnetBefore: s(80.9, 'pct', 'docs/finetune.md, section 9 table, sealed, Sonnet, heldout, decided before', 1),
    sonnetAfter: s(80.5, 'pct', 'docs/finetune.md, section 9 table, sealed, Sonnet, heldout, decided after', 1),
    unsafeBefore: s(2, 'count', 'docs/finetune.md, section 9 table, sealed, Sonnet, heldout, unsafe PASS before'),
    unsafeAfter: s(0, 'count', 'docs/finetune.md, section 9 table, sealed, Sonnet, heldout, unsafe PASS after'),
    oracleDecided: s(88.9, 'pct', 'docs/finetune.md, section 5, sealed table, Oracle, heldout', 1),
    oracleControlFail: s(0, 'count', 'docs/finetune.md, section 5, sealed table, Oracle, heldout'),
    oracleUnsafePass: s(0, 'count', 'docs/finetune.md, section 5, sealed table, Oracle, heldout'),
    sonnetControlFail: s(0, 'count', 'docs/finetune.md, section 5, sealed table, Sonnet, heldout'),
    // The lesson that broke it (section 9): the teaching close's change and the routine line the wrong word matched.
    teachChange: s(26748, 'count', 'docs/finetune.md, section 9 ("+$689 of a $26,748 change")'),
    routineLine: s(689, 'count', 'docs/finetune.md, section 9 ("+$689 of a $26,748 change")'),
    laterShare: s(99, 'pct', 'docs/finetune.md, section 9 ("covered 99% of the change")'),
    lessonsAtRisk: s(7, 'count', 'docs/finetune.md, section 9 ("7 of Sonnet\'s 1,379 lessons")'),
    lessonsTotal: s(1379, 'count', 'docs/finetune.md, section 9 ("7 of Sonnet\'s 1,379 lessons")'),
    maxCostPoints: s(0.8, 'ratio', 'docs/finetune.md, section 9 table (largest drop: default world, Sonnet, paraphrase, 74.0% -> 73.2%)', 1),
    qwenRebuiltDecided: s(57.8, 'pct', 'docs/finetune.md, section 5, sealed table, 3B rebuilt targets, heldout', 1),
    qwenRebuiltParaphrase: s(44.0, 'pct', 'docs/finetune.md, section 5, sealed table, 3B rebuilt targets, paraphrase', 1),
    qwenGapPoints: s(22.7, 'ratio', 'docs/finetune.md, section 5 ("22.7 points under Sonnet on held-out phrasing")', 1),
    qwenWorldsWon: s(0, 'count', 'docs/finetune.md, section 5 ("loses all 9 worlds on both tiers")'),
    // The second gap (section 9): the local model's first sealed score under rules 1-2.
    qwenControlFailPerTier: s(2, 'count', 'docs/finetune.md, section 9 ("2 control FAILs on each tier")'),
    qwenUnsafePassParaphrase: s(1, 'count', 'docs/finetune.md, section 9 ("1 unsafe PASS on the paraphrase tier")'),
    qwenUnsafePassHeldout: s(0, 'count', 'docs/finetune.md, sections 5 and 9 (unsafe PASS on the paraphrase tier only)'),
    hedgedNeeds: s(50, 'pct', 'docs/finetune.md, section 9 ("the hedged threshold of 50%")'),
    plainNeeds: s(75, 'pct', 'docs/finetune.md, section 9 ("a plain \'because of X\' ... which needs 75%")'),
    allStepsControlFail: s(0, 'count', 'docs/finetune.md, section 9 ("With all three rules every proposer cached here ... has 0 control FAIL and 0 unsafe PASS at every teaching step")'),
    allStepsUnsafePass: s(0, 'count', 'docs/finetune.md, section 9 (same sentence)'),
    rule3CostPoints: s(0.3, 'ratio', 'docs/finetune.md, section 9 ("from 58.0% to 57.8% and from 44.3% to 44.0%")', 1),
    qwenBeforeRule3: s(58.0, 'pct', 'docs/finetune.md, section 9 ("moved the local model\'s sealed results from 58.0% to 57.8%")', 1),
  },

  // ── Lesson recall, tried and rejected (docs/finetune.md, section 10; dev worlds, held-out) ───────────────────
  recall: {
    qwenWithout: s(55.2, 'pct', 'docs/finetune.md, section 10 table, 3B rebuilt, recall no', 1),
    qwenWith: s(70.2, 'pct', 'docs/finetune.md, section 10 table, 3B rebuilt, recall yes', 1),
    qwenWithControlFail: s(3, 'count', 'docs/finetune.md, section 10 table, 3B rebuilt, recall yes, control FAIL'),
    qwenWithUnsafePass: s(2, 'count', 'docs/finetune.md, section 10 table, 3B rebuilt, recall yes, unsafe PASS'),
  },

  // A 20-step multi-world RL run that moved nothing measurable (docs/finetune.md section 11). No RL result is claimed.
  rl: {
    result: s(0.49, 'ratio', 'docs/finetune.md, section 11 table, validation reward at step 20 (32 dev closes)', 3),
    rewardBefore: s(0.486, 'ratio', 'docs/finetune.md, section 11 table, validation reward at step 0', 3),
    steps: s(20, 'count', 'docs/finetune.md, section 11 ("RL was run for 20 optimizer steps")'),
    causeFoundBefore: s(37.7, 'pct', 'docs/finetune.md, section 11 table, cause found before', 1),
    causeFoundAfter: s(37.4, 'pct', 'docs/finetune.md, section 11 table, cause found at step 20', 1),
  },

  // ── Constrained decoding (docs/finetune.md, section 7) ──────────────────────────────────────────────────
  decoding: {
    maskMs: s(0.73, 'ms', 'docs/finetune.md, section 7 "Cost" ("a mean of 0.73 ms per step")', 2),
    goldReplies: s(66, 'count', 'docs/finetune.md, section 7 "Cost" ("66 gold replies")'),
    steps: s(16621, 'count', 'docs/finetune.md, section 7 "Cost" ("16,621 decoding steps")'),
    constrainedSeconds: s(2.5, 's', 'docs/finetune.md, section 7 "Cost" ("about 2.5 s per close constrained")', 1),
    unconstrainedSeconds: s(1.6, 's', 'docs/finetune.md, section 7 "Cost" ("1.6 s unconstrained")', 1),
    batch: s(12, 'count', 'docs/finetune.md, section 7 "Cost" ("in batches of 12")'),
    maxClaims: s(16, 'count', 'docs/finetune.md, section 7 "What is guaranteed" / training/constrain.py MAX_CLAIMS'),
    maxTerms: s(8, 'count', 'docs/finetune.md, section 7 / training/constrain.py MAX_TERMS'),
    // Section 7, "Result on the unseen suite" (rebuilt-target model, all 1,100 taught closes decoded under the mask).
    unseenDecided: s(54.4, 'pct', 'docs/finetune.md, section 7, "Result on the unseen suite" (held-out, 185 lessons)', 1),
    unseenParaphrase: s(40.9, 'pct', 'docs/finetune.md, section 7, "Result on the unseen suite" (paraphrase, 254 lessons)', 1),
    unseenCloses: s(1100, 'count', 'docs/finetune.md, section 7 ("All 1,100 taught closes")'),
    unseenLeftGrammar: s(0, 'count', 'docs/finetune.md, section 7 ("none left the grammar")'),
    unseenSecondsPerClose: s(2.28, 's', 'docs/finetune.md, section 7 ("at 2.28 s per close")', 2),
    unconstrainedParseFails: s(1, 'count', 'docs/finetune.md, section 7 ("one reply in 1,100 failed to parse without the constraint")'),
  },

  // ── Path forward (docs/teaching.md, section 3: teaching order when phrases repeat, skew 2) ──────────────
  order: {
    frequencyAt5: s(34.8, 'pct', 'docs/teaching.md, section 3, skew 2, frequency, 5 confirmations', 1),
    arrivalAt5: s(23.9, 'pct', 'docs/teaching.md, section 3, skew 2, arrival, 5 confirmations', 1),
  },
} as const;

/** Every Stat in RESULTS, with its dotted path (for scripts/check-data.ts). */
export const allStats = (): { path: string; stat: Stat }[] => {
  const out: { path: string; stat: Stat }[] = [];
  const walk = (node: unknown, path: string): void => {
    if (node && typeof node === 'object' && 'unit' in node && 'source' in node) {
      out.push({ path, stat: node as Stat });
      return;
    }
    if (Array.isArray(node)) node.forEach((n, i) => walk(n, `${path}[${i}]`));
    else if (node && typeof node === 'object') for (const [k, v] of Object.entries(node)) walk(v, path ? `${path}.${k}` : k);
  };
  walk(RESULTS, '');
  return out;
};

const group = (n: number): string => n.toLocaleString('en-US');

/** The text a Stat shows. Pending stats return null: render <PendingValue> in the same box instead. */
export const fmt = (st: Stat, opts: { unit?: boolean } = {}): string | null => {
  if (st.pending || st.value === null) return null;
  const d = st.decimals ?? 0;
  const n = d > 0 ? st.value.toFixed(d) : group(st.value);
  if (opts.unit === false) return n;
  switch (st.unit) {
    case 'pct':
      return `${n}%`;
    case 'ms':
      return `${n} ms`;
    case 's':
      return `${n} s`;
    case 'gb':
      return `${n} GB`;
    case 'params-m':
      return `${n}M`;
    default:
      return n;
  }
};

/** fmt() for stats that are known to be final (throws on a pending one, so a scene cannot show "null"). */
export const known = (st: Stat, opts: { unit?: boolean } = {}): string => {
  const t = fmt(st, opts);
  if (t === null) throw new Error(`Stat is pending: ${st.source}`);
  return t;
};

/** Numeric value for charts; pending stats give null. */
export const num = (st: Stat): number | null => (st.pending ? null : st.value);
