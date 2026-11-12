// Scene 8 · Unseen worlds: the result (2670–3120), VO 11. Opens on the decoding scene's search_terms line: the one
// field this benchmark tests. 91 training worlds on one side of a line, 11 measured worlds in industries the training
// lists never name on the other, each set written by a different model. Then the bars, set before any fine-tuned
// model was scored, in their real order: the ceiling, Sonnet, the two multi-world 3B models far below, the
// single-world 3B as a dashed "pending" slot, and the no-lessons baseline. The small model lost in all eleven
// worlds; every proposer kept both kill criteria at zero. Sonnet's bar carries into the safety scene (S9).
// Principles: staging (two clusters and the line between them, then one ranked chart), overlapping action (tiles
// cascade on a diagonal, list rows on a 3-frame stagger), anticipation (the ceiling row grows first), slow in / slow
// out on every bar, follow-through (values land after their bars, the gap is measured last), secondary action (slow
// push), arcs (the carried bar rises on an arc).
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, RADII, STROKE, TYPE } from '../brand/tokens';
import { Eyebrow, PendingValue, StatText, VerdictChip } from '../components/ui';
import { UNSEEN_INDUSTRIES } from '../data/cases';
import { RESULTS, known, num, type Stat } from '../data/results';
import { enter, lift, mix, progress, rise } from '../lib/anim';
import { css, measure } from '../lib/svg';
import { BAR, SAFETY_ROW_Y, TERMS_CHIPS, TERMS_LINE } from './shared/s8-geom';

const LEN = 450;
const R = RESULTS.worlds;
const T = { suffix: 4, tiles: 8, tilesLabel: 50, divider: 62, list: 70, listLabel: 116, opus: 150, toBars: 186, bars: 206, gap: 300, para: 318, out: 414 } as const;

const GRID = { x: 160, y: 180, cols: 13, rows: 7, w: 46, h: 52, gap: 8 } as const;
const LISTX = 1000;
const KILL = { fail: 1572, pass: 1700 } as const;
const MONO = TYPE.eyebrow;

interface BarRow {
  label: string;
  sub: string;
  decided: Stat;
  fail: Stat | null;
  pass: Stat | null;
  hollow?: boolean;
  carry?: boolean;
  at: number;
}

// Ranked as measured (docs/finetune.md section 5, held-out phrasing, under the lesson rule of section 9).
const ROWS: BarRow[] = [
  { label: 'Oracle (ceiling)', sub: "the generator's own answers", decided: R.oracleDecided, fail: R.oracleControlFail, pass: R.oracleUnsafePass, hollow: true, at: 0 },
  { label: 'Claude Sonnet 5.5', sub: 'hosted proposer', decided: R.sonnetDecided, fail: R.sonnetControlFail, pass: R.sonnetUnsafePass, carry: true, at: 12 },
  { label: 'Qwen2.5-3B, rebuilt targets', sub: `multi-world, ${known(RESULTS.finetune.worldsTrainWorlds)} worlds`, decided: R.qwenRebuiltDecided, fail: R.qwenRebuiltControlFail, pass: R.qwenRebuiltUnsafePass, at: 40 },
  { label: 'Qwen2.5-3B, gold targets', sub: 'multi-world, the first model', decided: R.qwenGoldDecided, fail: R.qwenGoldControlFail, pass: R.qwenGoldUnsafePass, at: 52 },
  { label: 'Qwen2.5-3B, single-world', sub: 'fine-tuned on one world only', decided: R.qwenSingleDecided, fail: R.qwenSingleControlFail, pass: R.qwenSingleUnsafePass, at: 62 },
];
const rowY = (i: number): number => BAR.top + i * BAR.row;
const xOf = (pct: number): number => BAR.x0 + (BAR.w * pct) / 100;

export const S8Worlds: React.FC = () => {
  const f = useCurrentFrame();
  const push = mix(1, 1.025, progress(f, 0, LEN, 'standard'));
  const phaseA = lift(f, T.toBars, 8, 18);
  const out = lift(f, T.out, 8, 16);
  const carryT = progress(f, T.out + 8, 27, 'standard');
  const baseX = xOf(num(R.untaughtDecided) ?? 0);
  const chipsW = TERMS_CHIPS.reduce((a, w) => a + measure(w, 'sans', MONO) + 20 + 3 + 10, measure('"search_terms": [', 'mono', MONO) + 10);
  const sonnetRow = ROWS.findIndex((r) => r.carry);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.obsidian }}>
      {/* Carried in: the decoding scene's search_terms line, and what it means here */}
      <div style={{ position: 'absolute', left: TERMS_LINE.x, top: TERMS_LINE.y, height: 40, display: 'flex', alignItems: 'center', gap: 10, ...phaseA }}>
        <span style={css('mono', MONO, COLORS.paper)}>{'"search_terms": ['}</span>
        {TERMS_CHIPS.map((w) => (
          <span key={w} style={{ ...css('sans', MONO, COLORS.paper), padding: '0 10px', lineHeight: '36px', borderRadius: 6, border: `1.5px dashed ${COLORS.mist}` }}>
            {w}
          </span>
        ))}
      </div>
      <div style={{ position: 'absolute', left: TERMS_LINE.x + chipsW + 16, top: TERMS_LINE.y, height: 40, display: 'flex', alignItems: 'center', ...css('sans', MONO, COLORS.mist), ...rise(f, T.suffix, 10, 6), opacity: rise(f, T.suffix, 10, 6).opacity * phaseA.opacity }}>
        guessed blind: the one thing the unseen worlds test
      </div>

      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: '960px 900px' }}>
        {/* Phase A: who wrote what */}
        <div style={{ position: 'absolute', inset: 0, ...phaseA }}>
          {Array.from({ length: GRID.cols * GRID.rows }, (_, i) => {
            const c = i % GRID.cols;
            const r = Math.floor(i / GRID.cols);
            const t = enter(f, T.tiles + (c + r) * 1.4, 12);
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: GRID.x + c * (GRID.w + GRID.gap),
                  top: GRID.y + r * (GRID.h + GRID.gap),
                  width: GRID.w,
                  height: GRID.h,
                  borderRadius: 6,
                  backgroundColor: COLORS.obsidianRaised,
                  boxShadow: `0 0 0 1.5px #55524F`,
                  opacity: t,
                  transform: `translateY(${(1 - t) * 10}px)`,
                }}
              >
                {[0, 1, 2].map((k) => (
                  <div key={k} style={{ position: 'absolute', left: 8, top: 12 + k * 11, width: [26, 18, 22][(i + k) % 3], height: 3, borderRadius: 2, backgroundColor: COLORS.mist, opacity: 0.55 }} />
                ))}
              </div>
            );
          })}
          <div style={{ position: 'absolute', left: 160, top: 614, ...rise(f, T.tilesLabel, 12, 10) }}>
            <div style={css('sans', TYPE.ui, COLORS.paper)}>{`${known(R.training)} training worlds`}</div>
            <div style={{ ...css('sans', TYPE.eyebrow, COLORS.mist), marginTop: 8 }}>written by Claude Sonnet and Haiku</div>
          </div>
          <div style={{ position: 'absolute', left: 920, top: 180, width: STROKE.rule, height: 540 * progress(f, T.divider, 22), backgroundColor: COLORS.paper }} />
          {UNSEEN_INDUSTRIES.map((name, i) => (
            <div key={name} style={{ position: 'absolute', left: LISTX, top: 172 + i * 38, display: 'flex', alignItems: 'center', gap: 14, ...rise(f, T.list + i * 3, 10, 8) }}>
              <span style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: COLORS.paper }} />
              <span style={css('sans', TYPE.eyebrow, COLORS.paper)}>{name}</span>
            </div>
          ))}
          <div style={{ position: 'absolute', left: LISTX, top: 614, ...rise(f, T.listLabel, 12, 10) }}>
            <div style={css('sans', TYPE.ui, COLORS.paper)}>{`${known(R.unseen)} unseen worlds, new industries`}</div>
            <div style={{ ...css('sans', TYPE.eyebrow, COLORS.mist), marginTop: 8, position: 'relative', display: 'inline-block' }}>
              written by Claude Opus · {known(R.sharedMemoLines)} memo lines shared
              <span style={{ position: 'absolute', left: measure('written by Claude ', 'sans', TYPE.eyebrow), top: 36, width: measure('Opus', 'sans', TYPE.eyebrow) * progress(f, T.opus, 10), height: STROKE.rule, backgroundColor: COLORS.paper }} />
            </div>
          </div>
        </div>

        {/* Phase B: the ranked result */}
        {f >= T.toBars && (
          <div style={{ position: 'absolute', inset: 0 }}>
            <div style={{ position: 'absolute', inset: 0, ...out }}>
              <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: 160, top: 108, ...rise(f, T.toBars + 8, 10, 8) }}>
                Unseen-worlds benchmark · bars set before any model was scored
              </Eyebrow>
              <div style={{ position: 'absolute', left: 160, top: 150, ...css('sans', TYPE.title, COLORS.paper), lineHeight: 1.1, ...rise(f, T.toBars + 10, 12, 12) }}>
                {`The small model lost, in all ${known(R.unseen)} worlds.`}
              </div>
              <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: 160, top: 238, ...rise(f, T.toBars + 16, 10, 8) }}>
                {`Decided without a person · held-out · fully taught, ${known(R.closesPerWorld)} closes a world`}
              </Eyebrow>
              {(['fail', 'pass'] as const).map((k) => (
                <div key={k} style={{ position: 'absolute', left: KILL[k], top: 234, ...rise(f, T.toBars + 18, 10, 8) }}>
                  <VerdictChip verdict={k === 'fail' ? 'FAIL' : 'PASS'} size={TYPE.eyebrow} />
                </div>
              ))}
              {/* The no-lessons baseline */}
              <div style={{ position: 'absolute', left: baseX, top: BAR.top - 10, width: 0, height: (ROWS.length * BAR.row - 30) * progress(f, T.bars - 6, 18), borderLeft: `2px dashed ${COLORS.mist}` }} />
              <div style={{ position: 'absolute', left: baseX - 12, top: BAR.top + ROWS.length * BAR.row - 30, ...css('sans', TYPE.eyebrow, COLORS.mist), ...rise(f, T.bars + 8, 10, 6) }}>
                {`no lessons · ${known(R.untaughtDecided)}`}
              </div>
            </div>
            {ROWS.map((r, i) => {
              const at = T.bars + r.at;
              const v = num(r.decided);
              const w = v === null ? BAR.w : (BAR.w * v) / 100;
              const grow = progress(f, at, 26, 'standard');
              // The Sonnet row is carried into the safety scene; the others leave with the chart.
              const carrying = r.carry && f >= T.out;
              const y = carrying ? mix(rowY(i), SAFETY_ROW_Y, carryT) - Math.sin(Math.PI * carryT) * 26 : rowY(i);
              const rowStyle = carrying ? {} : out;
              return (
                <div key={r.label} style={{ position: 'absolute', inset: 0, ...rowStyle }}>
                  <div style={{ position: 'absolute', left: 160, top: y - 6, ...rise(f, T.toBars + 14 + i * 4, 10, 8) }}>
                    <div style={css('sans', TYPE.label, COLORS.paper)}>{r.label}</div>
                    <div style={{ ...css('sans', TYPE.eyebrow, COLORS.mist), marginTop: 4, opacity: carrying ? 1 - progress(f, T.out, 8) : 1 }}>{r.sub}</div>
                  </div>
                  {v === null ? (
                    <div style={{ position: 'absolute', left: BAR.x0, top: y, opacity: grow }}>
                      <PendingValue width={BAR.w} height={BAR.h} dark label="result pending" dash={-f * 0.6} />
                    </div>
                  ) : (
                    <div
                      style={{
                        position: 'absolute',
                        left: BAR.x0,
                        top: y,
                        width: w * grow,
                        opacity: w * grow > 6 ? 1 : 0,
                        height: BAR.h,
                        borderRadius: RADII.control,
                        boxSizing: 'border-box',
                        backgroundColor: r.hollow ? 'transparent' : COLORS.paper,
                        border: r.hollow ? `2px solid ${COLORS.paper}` : undefined,
                      }}
                    />
                  )}
                  {v !== null && (
                    <div style={{ position: 'absolute', left: BAR.x0 + w + 16, top: y + 2, ...rise(f, at + 20, 8, 6), opacity: rise(f, at + 20, 8, 6).opacity * (carrying ? 1 - progress(f, T.out, 6) : 1) }}>
                      <StatText stat={r.decided} size={TYPE.label} color={COLORS.paper} dark slot={110} />
                    </div>
                  )}
                  {!carrying &&
                    ([['fail', r.fail], ['pass', r.pass]] as const).map(([k, st]) => (
                      <div key={k} style={{ position: 'absolute', left: KILL[k] + 30, top: y - 2, ...rise(f, at + 22, 8, 6) }}>
                        {st === null ? (
                          <span style={css('sans', TYPE.label, COLORS.mist)}>—</span>
                        ) : st.pending ? (
                          <div style={{ marginLeft: -26 }}>
                            <PendingValue width={64} height={44} dark label="…" dash={-f * 0.6} />
                          </div>
                        ) : (
                          <StatText stat={st} size={TYPE.label} color={COLORS.paper} dark slot={64} />
                        )}
                      </div>
                    ))}
                </div>
              );
            })}
            <div style={{ position: 'absolute', inset: 0, ...out }}>
              {/* The gap between the better 3B model and Sonnet, measured last */}
              {(() => {
                const x0 = xOf(num(R.qwenRebuiltDecided) ?? 0) + 24;
                const x1 = xOf(num(R.sonnetDecided) ?? 0);
                const y = rowY(sonnetRow) + BAR.h + 42;
                const t = progress(f, T.gap, 16, 'standard');
                return (
                  <>
                    <div style={{ position: 'absolute', left: x1 - (x1 - x0) * t, top: y, width: (x1 - x0) * t, height: STROKE.rule, backgroundColor: COLORS.flag }} />
                    <div style={{ position: 'absolute', left: x1 - measure(`${known(R.qwenRebuiltGapPoints)} points below Sonnet`, 'sans', TYPE.eyebrow), top: y - 38, ...css('sans', TYPE.eyebrow, COLORS.paper), ...rise(f, T.gap + 10, 10, 6) }}>
                      {`${known(R.qwenRebuiltGapPoints)} points below Sonnet`}
                    </div>
                  </>
                );
              })()}
              <div style={{ position: 'absolute', left: BAR.x0, top: 756, ...css('sans', TYPE.eyebrow, COLORS.mist), ...rise(f, T.para, 10, 8) }}>
                {`Paraphrase tier, same order: ${known(R.oracleParaphrase)} · ${known(R.sonnetParaphrase)} · ${known(R.qwenRebuiltParaphrase)} · ${known(R.qwenGoldParaphrase)} · ${known(R.qwenSingleParaphrase)}`}
              </div>
            </div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
