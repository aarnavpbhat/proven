// Scene 2 · Walkthrough: paste and verify (240–960), VO 2–5. Real captures of the console on the Lumen Robotics
// close (Rules, offline): the commentary is pasted into the editor, Verify, Coverage, the underlined explanation,
// then claim C1: it says $90K, the ledger shows +$44,900 (FAIL), and the evidence shows the other half of the
// Series B legal work booked to Marketing (TX-2068, $45,100), which moved back gives the stated +$90,000.
// The camera stays on the whole console while each step happens (a ring marks where to look) and pushes in only
// for one detail per step: Coverage, the claim's checks, the evidence rows. A step bar names the step on screen.
// Carried in: the hook's sentence fades over the console as the camera finds the editor.
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS } from '../brand/tokens';
import { CaptureView, Callout, Cursor, Keycap, Mark, type CamKey } from '../components/CaptureView';
import { Steps } from '../components/Steps';
import { RESULTS, known } from '../data/results';
import { progress } from '../lib/anim';
import { S1Frame, S1_LEN } from './S1Hook';
import { FOCUS } from './shared/capture-geom';

export const S2_LEN = 720;
export const S2_KEYS: CamKey[] = [
  { at: 0, shot: 'lumen-empty', focus: FOCUS.wide },
  { at: 80, shot: 'lumen-pasted', focus: FOCUS.wide, move: 1, fade: 6 },
  { at: 146, shot: 'lumen-annotated', focus: FOCUS.wide, fade: 8, move: 1 },
  { at: 200, shot: 'lumen-annotated', focus: FOCUS.lumenCoverage, move: 22 },
  { at: 262, shot: 'lumen-annotated', focus: FOCUS.wide, move: 20 },
  { at: 296, shot: 'lumen-claims', focus: FOCUS.wide, fade: 8, move: 1 },
  { at: 340, shot: 'lumen-claims', focus: FOCUS.lumenDetail, move: 24 },
  { at: 480, shot: 'lumen-findings', focus: FOCUS.low, fade: 10, move: 24 },
  { at: 530, shot: 'lumen-findings', focus: FOCUS.lumenFindings, move: 22 },
];

const S = RESULTS.showcase;

export const S2Paste: React.FC = () => {
  const f = useCurrentFrame();
  const hook = 1 - progress(f, 0, 16);
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <div style={{ position: 'absolute', inset: 0, opacity: progress(f, 0, 16) }}>
        <CaptureView keys={S2_KEYS}>
          {(cam) => (
            <>
              <Mark cam={cam} f={f} r={{ x: 257, y: 296, w: 514, h: 500 }} at={30} until={78} />
              <Keycap x={1040} y={520} text="⌘ V" f={f} at={66} dur={30} />
              <Mark cam={cam} f={f} r={FOCUS.lumenCoverage} at={160} until={258} pad={4} />
              <Callout x={560} y={850} f={f} at={176} until={258} text={`${known(S.claims)} claims checked · ${known(S.decided)} decided without a person`} />
              <Mark cam={cam} f={f} r={FOCUS.lumenDetail} at={304} until={338} />
              <Mark cam={cam} f={f} r={{ x: 812, y: 532, w: 545, h: 62 }} at={362} until={470} tone="fail" />
              <Callout x={560} y={878} f={f} at={366} until={470} tone="fail" text="The ledger contradicts the sentence: FAIL" />
              <Mark cam={cam} f={f} r={FOCUS.lumenFindings} at={492} until={528} tone="review" />
              <Mark cam={cam} f={f} r={{ x: 836, y: 1066, w: 566, h: 64 }} at={552} until={622} tone="review" />
              <Callout x={560} y={832} f={f} at={556} until={622} tone="review" text="$45,100 of Series B legal work, booked to Marketing" />
              <Mark cam={cam} f={f} r={{ x: 836, y: 1003, w: 566, h: 22 }} at={622} until={712} tone="ink" pad={5} />
              <Callout x={560} y={832} f={f} at={628} until={712} text="Moved back: +$90,000, what the sentence said" />
              <Cursor
                cam={cam}
                f={f}
                path={[
                  { at: 20, x: 900, y: 250 },
                  { at: 64, x: 420, y: 470, click: true },
                  { at: 112, x: 420, y: 470 },
                  { at: 140, x: 1384, y: 113, click: true },
                  { at: 222, x: 1384, y: 113 },
                  { at: 288, x: 296, y: 311, click: true },
                ]}
                until={300}
              />
              <Steps active={f < 296 ? 1 : 2} />
            </>
          )}
        </CaptureView>
      </div>
      {hook > 0 && (
        <div style={{ position: 'absolute', inset: 0, opacity: hook }}>
          <S1Frame frame={S1_LEN + f} />
        </div>
      )}
    </AbsoluteFill>
  );
};
