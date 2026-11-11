// Scene 4 · Walkthrough: safety gate, confirm once (1470–1980), VO 8–9. Real captures: back in Review, C1's Teach
// Proven form is filled with the model's word ("our biggest promotion of the year" → campaign); "Check with the
// safety gate" replays it against known answers ("Gate: safe … This claim: REVIEW → PASS"); the reviewer ticks
// that they checked the matched transactions, writes why, and records; C1 is now PASS and Learned shows 1.
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS } from '../brand/tokens';
import { CaptureView, Callout, Cursor, Mark, focusAt, type CamKey } from '../components/CaptureView';
import { Steps } from '../components/Steps';
import { S3_KEYS, S3_LEN } from './S3Waits';
import { FOCUS } from './shared/capture-geom';

export const S4_LEN = 510;
export const S4_KEYS: CamKey[] = [
  { at: 0, shot: 'queue', focus: focusAt(S3_KEYS, S3_LEN) },
  { at: 30, shot: 'teach-form', focus: FOCUS.low, fade: 10, move: 24 },
  { at: 78, shot: 'teach-form', focus: FOCUS.teachFields, move: 22 },
  { at: 128, shot: 'gate-safe', focus: FOCUS.gate, fade: 8, move: 22 },
  { at: 262, shot: 'gate-safe', focus: FOCUS.confirm, move: 18 },
  { at: 290, shot: 'teach-ready', focus: FOCUS.confirm, fade: 6, move: 1 },
  { at: 326, shot: 'teach-ready', focus: FOCUS.low, move: 22 },
  { at: 384, shot: 'bright-pass', focus: FOCUS.wide, fade: 10, move: 24 },
];

export const S4Gate: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <CaptureView keys={S4_KEYS}>
        {(cam) => (
          <>
            <Mark cam={cam} f={f} r={{ x: 822, y: 1010, w: 570, h: 375 }} at={44} until={80} />
            <Callout x={560} y={846} f={f} at={46} until={80} text="The reviewer's form: Teach Proven" />
            <Mark cam={cam} f={f} r={{ x: 836, y: 1125, w: 540, h: 100 }} at={92} until={124} />
            <Callout x={560} y={846} f={f} at={94} until={124} text="The lesson: this phrase means this ledger word" />
            <Mark cam={cam} f={f} r={{ x: 836, y: 1196, w: 365, h: 80 }} at={146} until={262} tone="pass" />
            <Callout x={560} y={846} f={f} at={156} until={262} tone="pass" text="Replayed against known answers before anything is stored" maxWidth={1300} />
            <Mark cam={cam} f={f} r={{ x: 836, y: 1282, w: 540, h: 40 }} at={296} until={326} dim={false} />
            <Mark cam={cam} f={f} r={{ x: 1316, y: 929, w: 78, h: 36 }} at={346} until={384} />
            <Mark cam={cam} f={f} r={{ x: 256, y: 500, w: 516, h: 160 }} at={400} until={446} tone="pass" />
            <Callout x={560} y={846} f={f} at={404} until={446} tone="pass" text="Confirmed once: PASS" />
            <Mark cam={cam} f={f} r={{ x: 8, y: 132, w: 215, h: 36 }} at={452} until={500} tone="pass" />
            <Callout x={560} y={846} f={f} at={456} until={500} tone="pass" text="One lesson, kept for every close" />
            <Cursor cam={cam} f={f} path={[{ at: 6, x: 200, y: 200 }, { at: 24, x: 75, y: 75, click: true }]} until={36} />
            <Cursor cam={cam} f={f} path={[{ at: 96, x: 1150, y: 1200 }, { at: 120, x: 1290, y: 1249, click: true }]} until={140} />
            <Cursor cam={cam} f={f} path={[{ at: 266, x: 1000, y: 1250 }, { at: 286, x: 845, y: 1301, click: true }]} />
            <Cursor cam={cam} f={f} path={[{ at: 344, x: 1200, y: 980 }, { at: 376, x: 1355, y: 947, click: true }]} until={392} />
            <Steps active={4} />
          </>
        )}
      </CaptureView>
    </AbsoluteFill>
  );
};
