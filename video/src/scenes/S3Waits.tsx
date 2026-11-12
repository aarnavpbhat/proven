// Scene 3 · Walkthrough: a claim waits for a person (960–1470), VO 6–7. Real captures, Brightfield Health close,
// Claude Sonnet 5.5 as the extractor (its proposals replayed from Proven's proposal cache: the console's own run
// line says "answered from the proposal cache, no request made"). The extractor note ("receives the explanation text
// and chart of accounts only, never transactions"), Verify, C1 in REVIEW, the model's search words, the two
// transactions its word "campaign" matched, then Learned → Teach next, where the claim waits.
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS } from '../brand/tokens';
import { CaptureView, Callout, Cursor, Mark, focusAt, type CamKey } from '../components/CaptureView';
import { Steps } from '../components/Steps';
import { S2_KEYS, S2_LEN } from './S2Paste';
import { FOCUS } from './shared/capture-geom';

export const S3_LEN = 510;
export const S3_KEYS: CamKey[] = [
  { at: 0, shot: 'lumen-findings', focus: focusAt(S2_KEYS, S2_LEN) },
  { at: 0, shot: 'bright-extractor', focus: FOCUS.wide, fade: 12, move: 24 },
  { at: 72, shot: 'bright-claims', focus: FOCUS.wide, fade: 8, move: 1 },
  { at: 116, shot: 'bright-claims', focus: FOCUS.brightNoteWide, move: 22 },
  { at: 180, shot: 'bright-claims', focus: FOCUS.wide, move: 22 },
  { at: 268, shot: 'bright-claims', focus: FOCUS.brightSearched, move: 24 },
  { at: 366, shot: 'bright-findings', focus: FOCUS.brightFindings, fade: 10, move: 22 },
  { at: 418, shot: 'bright-findings', focus: FOCUS.wide, move: 20 },
  { at: 440, shot: 'queue', focus: FOCUS.wide, fade: 10, move: 1 },
];

export const S3Waits: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <CaptureView keys={S3_KEYS}>
        {(cam) => (
          <>
            <Mark cam={cam} f={f} r={{ x: 913, y: 97, w: 236, h: 32 }} at={24} until={68} />
            <Callout x={560} y={846} f={f} at={28} until={68} text="Proposer: a language model" />
            <Mark cam={cam} f={f} r={{ x: 256, y: 187, w: 482, h: 22 }} at={86} until={176} />
            <Callout x={560} y={846} f={f} at={122} until={176} text="The model never sees a transaction" />
            <Mark cam={cam} f={f} r={{ x: 256, y: 405, w: 516, h: 135 }} at={200} until={264} tone="review" />
            <Callout x={560} y={846} f={f} at={204} until={264} tone="review" text="Claim 1 is marked REVIEW" />
            <Mark cam={cam} f={f} r={{ x: 816, y: 727, w: 568, h: 46 }} at={292} until={366} tone="review" />
            <Callout x={560} y={846} f={f} at={300} until={366} tone="review" text="Search words the model proposed" />
            <Mark cam={cam} f={f} r={{ x: 836, y: 622, w: 566, h: 132 }} at={384} until={416} tone="review" />
            <Callout x={560} y={846} f={f} at={388} until={416} tone="review" text="“campaign” matched these two" />
            <Mark cam={cam} f={f} r={{ x: 268, y: 280, w: 1140, h: 78 }} at={456} until={500} tone="review" />
            <Callout x={560} y={846} f={f} at={460} until={500} tone="review" text="Teach next: waiting for a person" />
            <Cursor cam={cam} f={f} path={[{ at: 40, x: 1200, y: 150 }, { at: 64, x: 1384, y: 113, click: true }]} until={80} />
            <Cursor cam={cam} f={f} path={[{ at: 414, x: 400, y: 230 }, { at: 436, x: 78, y: 150, click: true }]} until={452} />
            <Steps active={3} />
          </>
        )}
      </CaptureView>
    </AbsoluteFill>
  );
};
