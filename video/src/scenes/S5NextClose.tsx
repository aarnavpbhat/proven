// Scene 5 · Walkthrough: the next close, rules alone (1980–2325), VO 10. Real capture: Cobalt Freight, a different
// company, Extractor "Rules (offline)"; the run line reads "rules/0.1 … nothing left this machine"; C1, the same
// reason in other words, PASSes, and Searched shows the confirmed word as "campaign (learned)".
// Carried out: the capture fades to bone, where the loop diagram builds.
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS } from '../brand/tokens';
import { CaptureView, Callout, Mark, focusAt, type CamKey } from '../components/CaptureView';
import { Steps } from '../components/Steps';
import { S4_KEYS, S4_LEN } from './S4Gate';
import { progress } from '../lib/anim';
import { FOCUS } from './shared/capture-geom';

const LEN = 345;
const KEYS: CamKey[] = [
  { at: 0, shot: 'bright-pass', focus: focusAt(S4_KEYS, S4_LEN) },
  { at: 0, shot: 'cobalt-pass', focus: FOCUS.wide, fade: 12, move: 24 },
  { at: 172, shot: 'cobalt-pass', focus: FOCUS.cobaltDetail, move: 24 },
  { at: 240, shot: 'cobalt-pass', focus: FOCUS.cobaltSearched, move: 22 },
];

export const S5NextClose: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <div style={{ position: 'absolute', inset: 0, opacity: 1 - progress(f, LEN - 22, 20) }}>
        <CaptureView keys={KEYS}>
          {(cam) => (
            <>
              <Callout x={560} y={846} f={f} at={30} until={110} text="Next close · a different company" />
              <Mark cam={cam} f={f} r={{ x: 256, y: 110, w: 432, h: 21 }} at={40} until={110} />
              <Mark cam={cam} f={f} r={{ x: 1105, y: 97, w: 236, h: 32 }} at={122} until={170} />
              <Callout x={560} y={846} f={f} at={126} until={170} text="Rules only: no model in the loop" />
              <Mark cam={cam} f={f} r={{ x: 816, y: 444, w: 80, h: 30 }} at={194} until={240} tone="pass" dim={false} />
              <Mark cam={cam} f={f} r={{ x: 894, y: 676, w: 136, h: 26 }} at={262} until={LEN} tone="pass" />
              <Callout x={560} y={846} f={f} at={270} tone="pass" text="Decided by the word a reviewer confirmed" />
              <Steps active={5} />
            </>
          )}
        </CaptureView>
      </div>
    </AbsoluteFill>
  );
};
