// Scene 9 · Sealed suite: two safety gaps (3120–4140), VO 12–14. Sonnet's bar, carried from the results chart, becomes
// its first score on a second suite of nine worlds nobody inspected: 2 wrong explanations passed. Two closes show the
// mechanism (docs/finetune.md section 9): in a teaching close the model's blind guesses "descaling" (right) and
// "drilling" (in the name of the contractor who bills the account monthly) both matched, the second only on that
// contractor's flat monthly line (+$689 of a $26,748 change), and the reviewer confirmed every matched word; in a
// later close the learned "drilling" matched the same contractor's other job, covered 99% of the change and carried
// a PASS for the wrong cause. Then the fix, learned.trim_terms (commit 0798d4e): the lesson loses "drilling", the
// wrong explanation no longer passes, unsafe PASS 2 → 0. Chapter 2: the local model's lessons, under those two rules,
// failed 2 correct explanations on each tier and passed 1 wrong one (a lesson taught from a hedged sentence held one of a
// cause's two new charges plus part of the other cause); rule 3 (commit 814b2d5). Final: zero at every teaching step for
// every cached proposer, and the caveat that the rules were fit to these breaches. The trimmed lesson carries into S10.
// Schematic: the two closes are drawn from the write-up's description, not from the sealed suite's files.
// Principles: staging (one close, then the other, then the rule acting on both), anticipation (the routine line is
// singled out before the later close appears), follow-through (the match bar drains after the word is struck),
// slow in / slow out, overlapping action (the two cards react 12 frames apart), secondary action (slow push), arcs.
import { AbsoluteFill, interpolateColors, useCurrentFrame } from 'remotion';
import { COLORS, RADII, STROKE, TYPE } from '../brand/tokens';
import { Swap, TermChip } from '../components/Console';
import { Eyebrow, StatText, VerdictChip, eyebrowStyle } from '../components/ui';
import { RESULTS, known } from '../data/results';
import { lift, mix, progress, rise } from '../lib/anim';
import { css } from '../lib/svg';
import { usd } from '../data/cases';
import { BAR, SAFETY_ROW_Y } from './shared/s8-geom';
import { S9_TERMS } from './shared/s9-geom';

const LEN = 1020;
const S = RESULTS.sealed;
const UI = TYPE.eyebrow;
const T = {
  sub: 18,
  barTo: 24,
  kill: 30,
  unsafe: 60,
  caption: 74,
  phase1Out: 200,
  left: 210,
  guesses: 226,
  change: 250,
  routine: 274,
  lesson: 320,
  right: 390,
  rightMatch: 420,
  rightPass: 448,
  rules: 474,
  strike: 492,
  drain: 506,
  noPass: 528,
  done: 566,
  ch2: 642,
  ch2Rows: 660,
  ch2Card: 690,
  ch2Later: 740,
  rule3: 790,
  final: 880,
  out: 990,
} as const;

const LC = { x: 160, y: 244, w: 740, h: 396 } as const;
const RC = { x: 1000, y: 244, w: 760, h: 396 } as const;
const PAD = 28;
const ORIGIN = { x: 960, y: 900 } as const;
const push = (f: number): number => mix(1.025, 1.05, progress(f, 0, LEN, 'standard'));

const Card: React.FC<{ b: typeof LC | typeof RC; style?: React.CSSProperties; children: React.ReactNode }> = ({ b, style, children }) => (
  <div style={{ position: 'absolute', left: b.x, top: b.y, width: b.w, height: b.h, borderRadius: RADII.card, backgroundColor: COLORS.obsidianRaised, boxShadow: `0 0 0 1px ${COLORS.graphite}`, ...style }}>{children}</div>
);

/** The lesson as confirmed (both words) or trimmed (`drop` 0 → 1 strikes and removes "drilling"). */
const Lesson: React.FC<{ drop: number }> = ({ drop }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <TermChip text="descaling" kind="learned" />
    {drop < 1 && (
      <div style={{ opacity: 1 - Math.max(0, drop - 0.5) * 2, transform: `translateY(${Math.max(0, drop - 0.5) * 24}px)` }}>
        <TermChip
          text="drilling"
          kind="learned"
          style={{ textDecoration: drop > 0.15 ? 'line-through' : 'none', textDecorationColor: COLORS.flag, textDecorationThickness: 3, backgroundColor: interpolateColors(Math.min(1, drop * 2), [0, 1], [COLORS.chartreuse, COLORS.paper]) }}
        />
      </div>
    )}
  </div>
);

export const S9Safety: React.FC = () => {
  const f = useCurrentFrame();
  const p = push(f);
  const out = lift(f, T.out, 8, 16);
  const toLight = progress(f, T.out + 8, 10);
  const bg = interpolateColors(toLight, [0, 1], [COLORS.obsidian, COLORS.bone]);
  const phase1 = lift(f, T.phase1Out, 10, 16);
  const drop = progress(f, T.strike, 16);
  const drain = progress(f, T.drain, 18, 'standard');
  const sonnetW = (BAR.w * mix(RESULTS.worlds.sonnetDecided.value ?? 0, S.sonnetBefore.value ?? 0, progress(f, T.barTo, 20, 'standard'))) / 100;
  const routineW = ((LC.w - PAD * 2) * (S.routineLine.value ?? 0)) / (S.teachChange.value ?? 1);

  return (
    <AbsoluteFill style={{ backgroundColor: bg }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${p})`, transformOrigin: `${ORIGIN.x}px ${ORIGIN.y}px` }}>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          {(() => {
            const eyebrows = [
              `${known(S.worlds)} more worlds, written after the first suite was scored, never inspected`,
              `Sealed suite, Sonnet: decided ${known(S.sonnetBefore)} → ${known(S.sonnetAfter)} · nowhere more than ${known(S.maxCostPoints)} points · commit 0798d4e`,
              'Qwen2.5-3B, rebuilt targets: its first sealed score, under rules 1 and 2',
              `Every cached proposer · unseen, sealed, dev and default worlds · rule 3 cost at most ${known(S.rule3CostPoints)} points`,
            ];
            const heads = [
              'A sealed second suite found a real gap.',
              `Fixed the same night: unsafe PASS ${known(S.unsafeBefore)} → ${known(S.unsafeAfter)}.`,
              "Then the local model's lessons broke it again.",
              'Three rules: zero and zero at every teaching step.',
            ];
            const at = [0, T.done, T.ch2 + 8, T.final + 6];
            let k = 0;
            for (let i = 1; i < at.length; i++) if (f >= at[i]) k = i;
            const pa = Math.max(0, k - 1);
            return (
              <>
                <div style={{ position: 'absolute', left: 160, top: 108, ...rise(f, 2, 10, 8) }}>
                  <Swap a={eyebrows[pa]} b={eyebrows[k]} t={k === 0 ? 0 : progress(f, at[k] + 6, 10)} style={eyebrowStyle(COLORS.mist)} />
                </div>
                <div style={{ position: 'absolute', left: 160, top: 150, ...rise(f, 4, 12, 12) }}>
                  <Swap a={heads[pa]} b={heads[k]} t={k === 0 ? 0 : progress(f, at[k], 10)} style={{ ...css('sans', TYPE.title, COLORS.paper), lineHeight: 1.1 }} />
                </div>
              </>
            );
          })()}

          <div style={{ position: 'absolute', inset: 0, ...lift(f, T.ch2, 10, 16) }}>
          {/* Phase 1: the carried bar, as the sealed suite's first score */}
          <div style={{ position: 'absolute', inset: 0, ...phase1 }}>
            <div style={{ position: 'absolute', left: 160, top: SAFETY_ROW_Y - 6 }}>
              <div style={css('sans', TYPE.label, COLORS.paper)}>Claude Sonnet 5.5</div>
              <div style={{ ...css('sans', UI, COLORS.mist), marginTop: 4, ...rise(f, T.sub, 10, 6) }}>sealed suite, first score</div>
            </div>
            <div style={{ position: 'absolute', left: BAR.x0, top: SAFETY_ROW_Y, width: sonnetW, height: BAR.h, borderRadius: RADII.control, backgroundColor: COLORS.paper }} />
            <div style={{ position: 'absolute', left: BAR.x0 + sonnetW + 16, top: SAFETY_ROW_Y + 2, ...rise(f, T.barTo + 18, 8, 6) }}>
              <StatText stat={S.sonnetBefore} size={TYPE.label} color={COLORS.paper} dark slot={110} />
            </div>
            {(['fail', 'pass'] as const).map((k, i) => (
              <div key={k} style={{ position: 'absolute', left: [1572, 1700][i], top: SAFETY_ROW_Y - 66, ...rise(f, T.kill, 10, 8) }}>
                <VerdictChip verdict={k === 'fail' ? 'FAIL' : 'PASS'} size={UI} />
              </div>
            ))}
            <div style={{ position: 'absolute', left: 1602, top: SAFETY_ROW_Y - 2, ...rise(f, T.kill + 6, 8, 6) }}>
              <StatText stat={S.sonnetControlFail} size={TYPE.label} color={COLORS.paper} dark slot={64} />
            </div>
            <div style={{ position: 'absolute', left: 1730, top: SAFETY_ROW_Y - 2, ...rise(f, T.unsafe, 8, 6) }}>
              <StatText stat={S.unsafeBefore} size={TYPE.label} color={COLORS.flag} dark slot={64} />
              <div style={{ position: 'absolute', left: -6, top: 44, width: 34 * progress(f, T.unsafe + 6, 8), height: STROKE.rule + 1, backgroundColor: COLORS.flag }} />
            </div>
            <div style={{ position: 'absolute', left: 160, top: SAFETY_ROW_Y + 110, ...css('sans', TYPE.ui, COLORS.paper), ...rise(f, T.caption, 12, 10) }}>
              <span style={{ color: COLORS.flag }}>{`${known(S.unsafeBefore)} wrong explanations passed`}</span>, on lessons drafted from Sonnet&apos;s guesses.
            </div>
          </div>

          {/* Phase 2: the teaching close */}
          {f >= T.left - 2 && (
            <Card b={LC} style={rise(f, T.left, 14, 16)}>
              <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: PAD, top: 20 }}>
                Teaching close · the explanation is true
              </Eyebrow>
              <div style={{ position: 'absolute', left: PAD, top: 60, ...css('sans', TYPE.label, COLORS.paper) }}>Reason: clearing a clogged well</div>
              <div style={{ position: 'absolute', left: PAD, top: 116, ...css('sans', UI, COLORS.mist), ...rise(f, T.guesses, 10, 6) }}>Guessed blind, and both found lines in the books:</div>
              <div style={{ position: 'absolute', left: PAD, top: 152, display: 'flex', gap: 10 }}>
                {['descaling', 'drilling'].map((w, i) => (
                  <div key={w} style={rise(f, T.guesses + 6 + i * 4, 8, 6)}>
                    <TermChip text={w} kind="model" style={{ color: COLORS.paper, borderColor: COLORS.mist }} />
                  </div>
                ))}
              </div>
              <div style={{ position: 'absolute', left: PAD, top: 214, display: 'flex', alignItems: 'baseline', gap: 12, ...rise(f, T.change, 10, 6) }}>
                <span style={css('sans', UI, COLORS.mist)}>the account&apos;s change</span>
                <span style={css('sans', UI, COLORS.paper)}>{usd(S.teachChange.value ?? 0, { sign: true })}</span>
              </div>
              <div style={{ position: 'absolute', left: PAD, top: 252, width: (LC.w - PAD * 2) * progress(f, T.change + 4, 18, 'standard'), height: 24, borderRadius: 6, backgroundColor: COLORS.graphite }} />
              <div style={{ position: 'absolute', left: PAD, top: 252, width: Math.max(6, routineW), height: 24, borderRadius: 4, backgroundColor: COLORS.flag, opacity: progress(f, T.routine, 8) }} />
              <div style={{ position: 'absolute', left: PAD, top: 288, width: LC.w - PAD * 2, ...css('sans', UI, COLORS.paper), whiteSpace: 'normal', lineHeight: 1.3, ...rise(f, T.routine + 4, 10, 6) }}>
                <span style={{ color: COLORS.flag }}>drilling</span>
                {` matched only a flat monthly bill: ${usd(S.routineLine.value ?? 0, { sign: true })}`}
              </div>
              <div style={{ position: 'absolute', left: PAD, top: 340, display: 'flex', alignItems: 'center', gap: 14, ...rise(f, T.lesson, 10, 8) }}>
                <span style={css('sans', UI, COLORS.mist)}>Confirmed as a lesson:</span>
                <div style={{ opacity: f >= T.out ? 0 : 1 }}>
                  <Lesson drop={drop} />
                </div>
              </div>
            </Card>
          )}

          {/* Phase 2: the later close */}
          {f >= T.right - 2 && (
            <Card b={RC} style={rise(f, T.right, 14, 16)}>
              <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: PAD, top: 20 }}>
                Later close · the explanation is wrong
              </Eyebrow>
              <div style={{ position: 'absolute', left: PAD, top: 60, ...css('sans', TYPE.label, COLORS.paper) }}>Reason: clearing a clogged well</div>
              <div style={{ position: 'absolute', left: PAD, top: 112, ...css('sans', UI, COLORS.mist) }}>What really moved: the same contractor&apos;s other job</div>
              <div style={{ position: 'absolute', left: PAD, top: 166, display: 'flex', alignItems: 'center', gap: 14 }}>
                <span style={css('sans', UI, COLORS.mist)}>Lesson applied:</span>
                <Lesson drop={progress(f, T.strike + 12, 16)} />
              </div>
              <div style={{ position: 'absolute', left: PAD, top: 228, ...css('sans', UI, COLORS.paper), ...rise(f, T.rightMatch, 10, 6) }}>
                <Swap a="drilling matched the other job:" b="drilling is no longer in the lesson" t={progress(f, T.drain, 10)} style={css('sans', UI, COLORS.paper)} />
              </div>
              <div style={{ position: 'absolute', left: PAD, top: 272, width: RC.w - PAD * 2, height: 24, borderRadius: 6, backgroundColor: COLORS.graphite, opacity: progress(f, T.rightMatch, 8) }} />
              <div
                style={{
                  position: 'absolute',
                  left: PAD,
                  top: 272,
                  width: (RC.w - PAD * 2) * ((S.laterShare.value ?? 0) / 100) * progress(f, T.rightMatch + 4, 18, 'standard') * (1 - drain),
                  height: 24,
                  borderRadius: 6,
                  backgroundColor: COLORS.paper,
                }}
              />
              <div style={{ position: 'absolute', left: PAD, top: 306, ...css('sans', UI, COLORS.mist), ...rise(f, T.rightMatch + 16, 8, 6), opacity: rise(f, T.rightMatch + 16, 8, 6).opacity * (1 - drain) }}>
                {`${known(S.laterShare)} of the change`}
              </div>
              <div style={{ position: 'absolute', left: PAD, top: 344, display: 'flex', alignItems: 'center', gap: 14, ...rise(f, T.rightPass, 10, 8) }}>
                <div style={{ textDecoration: 'none', position: 'relative', opacity: 1 - progress(f, T.noPass, 8) }}>
                  <VerdictChip verdict="PASS" size={UI} />
                </div>
                <Swap a="a wrong explanation passed" b="the wrong explanation no longer passes" t={progress(f, T.noPass, 10)} style={css('sans', UI, f < T.noPass + 5 ? COLORS.flag : COLORS.paper)} />
              </div>
            </Card>
          )}

          {/* Phase 3: the rule */}
          <div style={{ position: 'absolute', left: 160, top: 664, ...rise(f, T.rules, 12, 10) }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
              <span style={css('mono', UI, COLORS.paper)}>learned.trim_terms</span>
              <span style={css('sans', UI, COLORS.paper)}>A lesson keeps only the words its PASS needs,</span>
            </div>
            <div style={{ ...css('sans', UI, COLORS.paper), marginTop: 6 }}>and never a word whose every match was a routine line that did not move.</div>
          </div>
          <div style={{ position: 'absolute', left: 1000, top: 764, ...css('sans', UI, COLORS.mist), ...rise(f, T.left + 20, 10, 6) }}>Schematic of docs/finetune.md §9; amounts as stated there.</div>
          </div>

          {/* Chapter 2: the local model's lessons, under rules 1 and 2 */}
          {f >= T.ch2 + 10 && (
            <div style={{ position: 'absolute', inset: 0, ...lift(f, T.final - 4, 10, 16) }}>
              {(['fail', 'pass'] as const).map((k, i) => (
                <div key={k} style={{ position: 'absolute', left: [1572, 1700][i], top: 248, ...rise(f, T.ch2Rows, 10, 8) }}>
                  <VerdictChip verdict={k === 'fail' ? 'FAIL' : 'PASS'} size={UI} />
                </div>
              ))}
              {[
                { label: 'Its lessons · sealed suite, held-out', fail: S.qwenControlFailPerTier, pass: S.qwenUnsafePassHeldout },
                { label: 'Its lessons · sealed suite, paraphrase', fail: S.qwenControlFailPerTier, pass: S.qwenUnsafePassParaphrase },
              ].map((r, i) => (
                <div key={r.label} style={{ position: 'absolute', left: 0, top: 0, ...rise(f, T.ch2Rows + 4 + i * 6, 10, 8) }}>
                  <div style={{ position: 'absolute', left: 160, top: 300 + i * 52, ...css('sans', TYPE.label, COLORS.paper) }}>{r.label}</div>
                  {([[1602, r.fail], [1730, r.pass]] as const).map(([x, st]) => (
                    <div key={x} style={{ position: 'absolute', left: x, top: 300 + i * 52 }}>
                      <StatText stat={st} size={TYPE.label} color={(st.value ?? 0) > 0 ? COLORS.flag : COLORS.paper} dark slot={64} />
                    </div>
                  ))}
                </div>
              ))}
              <div style={{ position: 'absolute', left: 160, top: 420, width: 1600, height: 216, borderRadius: RADII.card, backgroundColor: COLORS.obsidianRaised, boxShadow: `0 0 0 1px ${COLORS.graphite}`, ...rise(f, T.ch2Card, 14, 14) }}>
                {[
                  {
                    x: 28,
                    eyebrow: `Taught: “primarily due to X” · needs ${known(S.hedgedNeeds)}`,
                    need: S.hedgedNeeds.value ?? 50,
                    segs: [
                      { w: 40, c: COLORS.paper },
                      { w: 20, c: COLORS.flag },
                    ],
                    note: 'one new charge + part of the other cause: it passes, both words kept',
                    at: T.ch2Card + 10,
                  },
                  {
                    x: 840,
                    eyebrow: `Later: “because of X” · needs ${known(S.plainNeeds)}`,
                    need: S.plainNeeds.value ?? 75,
                    segs: [{ w: 55, c: COLORS.paper }],
                    note: 'one charge falls short: a correct explanation FAILs',
                    at: T.ch2Later,
                  },
                ].map((h) => {
                  const W = 720;
                  const g = progress(f, h.at + 6, 18, 'standard');
                  let acc = 0;
                  return (
                    <div key={h.x} style={{ position: 'absolute', left: h.x, top: 0, width: W, height: 216, ...rise(f, h.at, 10, 8) }}>
                      <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: 0, top: 22 }}>
                        {h.eyebrow}
                      </Eyebrow>
                      <div style={{ position: 'absolute', left: 0, top: 76, width: W, height: 26, borderRadius: 6, backgroundColor: COLORS.graphite }} />
                      {h.segs.map((sg, i) => {
                        const left = (W * acc) / 100;
                        acc += sg.w;
                        return <div key={i} style={{ position: 'absolute', left, top: 76, width: ((W * sg.w) / 100) * g, height: 26, backgroundColor: sg.c, borderRadius: 4 }} />;
                      })}
                      <div style={{ position: 'absolute', left: (W * h.need) / 100 - 1, top: 66, width: 3, height: 46, backgroundColor: COLORS.mist }} />
                      <div style={{ position: 'absolute', left: 0, top: 124, width: W, ...css('sans', UI, COLORS.paper), whiteSpace: 'normal', lineHeight: 1.3, ...rise(f, h.at + 20, 10, 6) }}>{h.note}</div>
                    </div>
                  );
                })}
                <div style={{ position: 'absolute', left: 840, top: 164, ...css('sans', UI, COLORS.paper), ...rise(f, T.ch2Later + 34, 10, 6) }}>
                  and one whose second charge was misbooked <span style={{ color: COLORS.flag }}>PASSes</span>
                </div>
              </div>
              <div style={{ position: 'absolute', left: 160, top: 664, ...rise(f, T.rule3, 12, 10) }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
                  <span style={css('mono', UI, COLORS.paper)}>rule 3 · 814b2d5</span>
                  <span style={css('sans', UI, COLORS.paper)}>A lesson&apos;s words must cover all of a vendor&apos;s new charges in a period, or none.</span>
                </div>
                <div style={{ ...css('sans', UI, COLORS.mist), marginTop: 6 }}>Schematic of docs/finetune.md §9: shares drawn for illustration, thresholds as stated.</div>
              </div>
            </div>
          )}

          {/* Final: the result, and what it does not establish */}
          {f >= T.final && (
            <div style={{ position: 'absolute', inset: 0 }}>
              <div style={{ position: 'absolute', left: 160, top: 300, ...css('sans', TYPE.ui, COLORS.paper), ...rise(f, T.final + 10, 12, 10) }}>The three rules were written from these breaches,</div>
              <div style={{ position: 'absolute', left: 160, top: 350, ...css('sans', TYPE.ui, COLORS.paper), ...rise(f, T.final + 16, 12, 10) }}>so the zeros are a fit to them, not a proof.</div>
              <div style={{ position: 'absolute', left: 160, top: 470, display: 'flex', alignItems: 'center', gap: 16, ...rise(f, T.final + 26, 10, 8) }}>
                <div style={{ opacity: f >= T.out ? 0 : 1 }}>
                  <TermChip text="descaling" kind="learned" />
                </div>
                <span style={css('sans', UI, COLORS.mist)}>rules 1–2: only the words a PASS needs, and none that matched only routine lines</span>
              </div>
              <div style={{ position: 'absolute', left: 160, top: 530, ...css('sans', UI, COLORS.mist), ...rise(f, T.final + 32, 10, 8) }}>
                rule 3: all of a vendor&apos;s new charges in a period, or none
              </div>
              <div style={{ position: 'absolute', left: 160, top: 590, ...css('sans', UI, COLORS.paper), ...rise(f, T.final + 40, 10, 8) }}>
                {`${known(S.allStepsControlFail)} correct failed · ${known(S.allStepsUnsafePass)} wrong passed, at 0, 10, 25 and 50 taught closes`}
              </div>
            </div>
          )}
        </div>
      </div>
      {/* The trimmed lesson carries into S10 */}
      {f >= T.out &&
        (() => {
          const t = progress(f, T.out + 6, 24, 'standard');
          const x0 = ORIGIN.x + (160 - ORIGIN.x) * p;
          const y0 = ORIGIN.y + (470 - ORIGIN.y) * p;
          return (
            <div style={{ position: 'absolute', left: mix(x0, S9_TERMS.x, t), top: mix(y0, S9_TERMS.y, t) - Math.sin(Math.PI * t) * 40 }}>
              <TermChip text="descaling" kind="learned" />
            </div>
          );
        })()}
    </AbsoluteFill>
  );
};
