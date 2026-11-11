// Scene 10 · Why the small model lost (3780–4260), VO 14. Opens on the trimmed lesson carried from S9. Three steps,
// each folding to one line before the next: (1) the single-world model memorised (95.3% on causes it trained on,
// 29.7% on four held out); (2) the first multi-world targets held words nothing in a request predicts, so they were
// rebuilt from a blind teacher's guesses that the cause's own lines contain (a real dev-world claim and the real
// targets() output); (3) what is left is knowledge: "cause found" on the dev worlds — Sonnet 80.1%, the rebuilt 3B
// 37.7% (double the first model's 18.3%), an untuned 7B 32.7%, an untuned 3B 2.6% — plus the failed 7B run and the
// rejected recall idea. A rule under the chart rises into S11's road.
// Principles: staging (one step at a time; each folds to a line), anticipation (the vendor chip is flagged before
// the guesses arrive), follow-through (matches light up, then the new target forms), slow in / slow out on every bar,
// secondary action (slow push), arcs (the closing rule rises on an arc).
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, RADII, STROKE, TYPE } from '../brand/tokens';
import { TermChip } from '../components/Console';
import { Eyebrow, StatText } from '../components/ui';
import { TEACHER } from '../data/cases';
import { RESULTS, known, type Stat } from '../data/results';
import { lift, mix, progress, rise } from '../lib/anim';
import { css, measure } from '../lib/svg';
import { ROAD, S9_TERMS } from './shared/s9-geom';

const LEN = 480;
const F = RESULTS.finetune;
const C = RESULTS.causeFound;
const UI = TYPE.eyebrow;
const T = {
  s1: 14,
  bars1: 30,
  fold1: 108,
  s2: 122,
  sentence: 128,
  gold: 136,
  vendor: 156,
  guesses: 170,
  hits: 196,
  target: 206,
  fold2: 228,
  s3: 242,
  rows: 256,
  double: 330,
  notes: 360,
  rule: 420,
  out: 452,
} as const;
const BAR = { x0: 640, w: 800, h: 32 } as const;
const STEP_Y = 300;

const Chips: React.FC<{ y: number; f: number; at: number; words: readonly string[]; render: (w: string) => React.ReactNode }> = ({ y, f, at, words, render }) => (
  <div style={{ position: 'absolute', left: 160, top: y, display: 'flex', gap: 10 }}>
    {words.map((w, i) => (
      <div key={w} style={rise(f, at + i * 2, 8, 6)}>
        {render(w)}
      </div>
    ))}
  </div>
);

interface ProbeRow {
  label: string;
  stat: Stat;
  probe?: boolean; // untuned, asked for terms only
}

const PROBE: ProbeRow[] = [
  { label: 'Claude Sonnet 5.5', stat: C.devSonnet },
  { label: 'Qwen2.5-3B, rebuilt targets', stat: C.devQwenRebuilt },
  { label: 'Qwen2.5-7B, untuned', stat: C.dev7bUntuned, probe: true },
  { label: 'Qwen2.5-3B, gold targets', stat: C.devQwenGold },
  { label: 'Qwen2.5-3B, untuned', stat: C.devQwenUntuned, probe: true },
];

export const S10Why: React.FC = () => {
  const f = useCurrentFrame();
  const push = mix(1, 1.02, progress(f, 0, LEN, 'standard'));
  const out = lift(f, T.out, 8, 16);
  const fold1 = progress(f, T.fold1, 14, 'standard');
  const fold2 = progress(f, T.fold2, 14, 'standard');
  const hit = (w: string): boolean => (TEACHER.hits as readonly string[]).includes(w);
  const hitT = progress(f, T.hits, 10);
  const ruleY = 660;
  const ruleT = progress(f, T.out + 6, 22, 'standard');
  const pillW = measure('descaling', 'sans', UI) + 24 + 3;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      {/* Carried in: the trimmed lesson */}
      <div style={{ position: 'absolute', left: S9_TERMS.x, top: S9_TERMS.y, opacity: out.opacity }}>
        <TermChip text="descaling" kind="learned" />
      </div>
      <div style={{ position: 'absolute', left: S9_TERMS.x + pillW + 16, top: S9_TERMS.y, height: 40, display: 'flex', alignItems: 'center', ...css('sans', UI, COLORS.ash), ...rise(f, 4, 10, 6), opacity: rise(f, 4, 10, 6).opacity * out.opacity }}>
        a lesson now keeps only the words its PASS needs
      </div>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: '960px 900px' }}>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          <div style={{ position: 'absolute', left: 160, top: 150, ...css('sans', TYPE.title, COLORS.ink), lineHeight: 1.1, ...rise(f, 0, 12, 14) }}>Why the small model lost</div>
          {/* Folded summaries */}
          <div style={{ position: 'absolute', left: 160, top: 226, ...css('sans', UI, COLORS.ash), opacity: progress(f, T.fold1 + 14, 8) }}>
            {`1 · It memorised one world: ${known(F.ablationSawDecided)} decided on causes it trained on, ${known(F.ablationNeverSawDecided)} on causes held out.`}
          </div>
          <div style={{ position: 'absolute', left: 160, top: 262, ...css('sans', UI, COLORS.ash), opacity: progress(f, T.fold2 + 14, 8) }}>
            2 · Its targets named vendors no sentence predicts; they were rebuilt as guessable, and true.
          </div>

          {/* Step 1 */}
          <div style={{ position: 'absolute', inset: 0, opacity: 1 - fold1, transform: `translateY(${-fold1 * 30}px)` }}>
            <div style={{ position: 'absolute', left: 160, top: STEP_Y, ...css('sans', TYPE.label, COLORS.ink), ...rise(f, T.s1, 10, 10) }}>1 · The first model memorised one world</div>
            {[
              { label: 'causes it was trained on', stat: F.ablationSawDecided },
              { label: 'four causes held out of training', stat: F.ablationNeverSawDecided },
            ].map((r, i) => {
              const y = 376 + i * 80;
              const g = progress(f, T.bars1 + i * 8, 22, 'standard');
              return (
                <div key={r.label}>
                  <div style={{ position: 'absolute', left: 160, top: y, ...css('sans', UI, COLORS.ink), ...rise(f, T.bars1 - 6 + i * 6, 10, 8) }}>{r.label}</div>
                  <div style={{ position: 'absolute', left: BAR.x0, top: y, width: (BAR.w * (r.stat.value ?? 0) * g) / 100, height: 36, borderRadius: RADII.control, backgroundColor: i === 0 ? COLORS.ink : COLORS.ash }} />
                  <div style={{ position: 'absolute', left: BAR.x0 + (BAR.w * (r.stat.value ?? 0)) / 100 + 16, top: y, ...rise(f, T.bars1 + 20 + i * 8, 8, 6) }}>
                    <StatText stat={r.stat} size={TYPE.label} slot={110} />
                  </div>
                </div>
              );
            })}
            <div style={{ position: 'absolute', left: 160, top: 556, ...css('sans', UI, COLORS.ash), ...rise(f, T.bars1 + 30, 10, 8) }}>
              {`claims decided, held-out phrasing · validation loss ${known(F.singleValLossStart)} → ${known(F.singleValLossEnd)} on templated data`}
            </div>
          </div>

          {/* Step 2 */}
          {f >= T.s2 - 2 && (
            <div style={{ position: 'absolute', inset: 0, opacity: 1 - fold2, transform: `translateY(${-fold2 * 30}px)` }}>
              <div style={{ position: 'absolute', left: 160, top: STEP_Y, ...css('sans', TYPE.label, COLORS.ink), ...rise(f, T.s2, 10, 10) }}>2 · The next one guessed vendor-like words</div>
              <div style={{ position: 'absolute', left: 160, top: 346, height: 50, padding: '0 20px', display: 'flex', alignItems: 'center', borderRadius: RADII.ui, backgroundColor: COLORS.paper, boxShadow: `0 0 0 1px ${COLORS.hairline}`, ...rise(f, T.sentence, 10, 10) }}>
                <span style={css('sans', UI, COLORS.ink)}>{`“${TEACHER.sentence}”`}</span>
              </div>
              <Eyebrow style={{ position: 'absolute', left: 160, top: 420, ...rise(f, T.gold, 10, 8) }}>Old target · what the cause left in the books</Eyebrow>
              <Chips
                y={452}
                f={f}
                at={T.gold + 4}
                words={TEACHER.gold}
                render={(w) => {
                  const vendor = (TEACHER.vendorOnly as readonly string[]).includes(w);
                  const v = progress(f, T.vendor, 10);
                  return <TermChip text={w} kind="written" style={vendor ? { boxShadow: `inset 0 0 0 ${2 * v}px ${COLORS.flag}`, backgroundColor: COLORS.paper, textDecoration: v > 0.5 ? 'line-through' : 'none', textDecorationColor: COLORS.flag, textDecorationThickness: 2 } : undefined} />;
                }}
              />
              <div style={{ position: 'absolute', left: 160 + TEACHER.gold.reduce((a, w) => a + measure(w, 'sans', UI) + 27 + 10, 0) + 10, top: 452, height: 40, display: 'flex', alignItems: 'center', ...css('sans', UI, COLORS.flag), ...rise(f, T.vendor + 4, 10, 6) }}>
                a vendor&apos;s name: nothing in the request predicts it
              </div>
              <Eyebrow style={{ position: 'absolute', left: 160, top: 516, ...rise(f, T.guesses, 10, 8) }}>A blind teacher&apos;s guesses · kept first where the cause&apos;s own lines contain them</Eyebrow>
              <Chips y={548} f={f} at={T.guesses + 4} words={TEACHER.guesses} render={(w) => <TermChip text={w} kind="model" style={hit(w) ? { backgroundColor: `rgba(228,242,34,${hitT})`, borderColor: hitT > 0.5 ? 'transparent' : COLORS.ash } : undefined} />} />
              <Eyebrow style={{ position: 'absolute', left: 160, top: 612, ...rise(f, T.target, 10, 8) }}>New target · guessable, and true</Eyebrow>
              <Chips y={644} f={f} at={T.target + 4} words={TEACHER.targets} render={(w) => <TermChip text={w} kind={hit(w) ? 'learned' : (TEACHER.gold as readonly string[]).includes(w) ? 'written' : 'model'} />} />
            </div>
          )}

          {/* Step 3: the knowledge gap */}
          {f >= T.s3 - 2 && (
            <div style={{ position: 'absolute', inset: 0 }}>
              <div style={{ position: 'absolute', left: 160, top: STEP_Y, ...css('sans', TYPE.label, COLORS.ink), ...rise(f, T.s3, 10, 10) }}>3 · What is left is knowledge</div>
              <Eyebrow style={{ position: 'absolute', left: 160, top: 346, ...rise(f, T.s3 + 6, 10, 8) }}>
                Cause found: how often blind guesses find the true cause · dev worlds, held-out
              </Eyebrow>
              {PROBE.map((r, i) => {
                const y = 392 + i * 52;
                const g = progress(f, T.rows + i * 6, 22, 'standard');
                const w = (BAR.w * (r.stat.value ?? 0)) / 100;
                return (
                  <div key={r.label}>
                    <div style={{ position: 'absolute', left: 160, top: y, height: BAR.h, display: 'flex', alignItems: 'center', ...css('sans', UI, COLORS.ink), ...rise(f, T.rows - 4 + i * 6, 10, 8) }}>{r.label}</div>
                    <div
                      style={{
                        position: 'absolute',
                        left: BAR.x0,
                        top: y,
                        width: w * g,
                        opacity: w * g > 4 ? 1 : 0,
                        height: BAR.h,
                        borderRadius: 6,
                        boxSizing: 'border-box',
                        backgroundColor: r.probe ? 'transparent' : COLORS.ink,
                        border: r.probe ? `2px dashed ${COLORS.ash}` : undefined,
                      }}
                    />
                    <div style={{ position: 'absolute', left: BAR.x0 + Math.max(w, 8) + 16, top: y - 1, ...rise(f, T.rows + 16 + i * 6, 8, 6) }}>
                      <StatText stat={r.stat} size={TYPE.eyebrow} slot={90} />
                    </div>
                  </div>
                );
              })}
              {/* The rebuilt targets doubled the 3B rate: a bracket from the gold bar's end to the rebuilt bar's end */}
              {(() => {
                const xG = BAR.x0 + (BAR.w * (C.devQwenGold.value ?? 0)) / 100;
                const xR = BAR.x0 + (BAR.w * (C.devQwenRebuilt.value ?? 0)) / 100;
                const t = progress(f, T.double, 14, 'standard');
                return (
                  <>
                    <div style={{ position: 'absolute', left: 1120, top: 392 + 52 + 4, ...css('sans', UI, COLORS.ink), ...rise(f, T.double + 6, 10, 6) }}>
                      {`rebuilt targets: ${known(C.devQwenGold)} → ${known(C.devQwenRebuilt)}`}
                    </div>
                    <div style={{ position: 'absolute', left: xG, top: 392 + 3 * 52 + BAR.h + 6, width: (xR - xG) * t, height: STROKE.rule, backgroundColor: COLORS.ink }} />
                  </>
                );
              })()}
              <div style={{ position: 'absolute', left: 160, top: 664, ...css('sans', UI, COLORS.ash), ...rise(f, T.notes, 10, 8) }}>
                Dashed: untuned, asked only for terms. A 7B fine-tune diverged (NaN) and left no model.
              </div>
              <div style={{ position: 'absolute', left: 160, top: 700, ...css('sans', UI, COLORS.ash), ...rise(f, T.notes + 8, 10, 8) }}>
                {`Re-offering confirmed words lifted the 3B to ${known(RESULTS.recall.qwenWith)}, but broke both kill criteria: rejected.`}
              </div>
            </div>
          )}
        </div>
      </div>
      {/* A rule draws under the chart and rises into S11's road */}
      {f >= T.rule && (
        <div
          style={{
            position: 'absolute',
            left: mix(960 + (160 - 960) * push, ROAD.x, ruleT),
            top: mix(900 + (ruleY - 900) * push, ROAD.y, ruleT) - Math.sin(Math.PI * ruleT) * 40,
            width: mix(1600 * push * progress(f, T.rule, 20, 'standard'), ROAD.w, ruleT),
            height: STROKE.rule,
            backgroundColor: COLORS.ink,
          }}
        />
      )}
    </AbsoluteFill>
  );
};
