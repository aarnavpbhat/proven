// Scene 9 · Close (3420–3540), VO 15. Adapted from the archived S12Close: bone ground, the chartreuse band draws,
// "Proven" rises onto it; "The model proposes. The ledger decides." lands with the VO; then a held end frame.
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, PRODUCT_NAME, TYPE } from '../brand/tokens';
import { Highlight } from '../components/Highlight';
import { wordmarkWidth } from '../components/Wordmark';
import { progress, rise } from '../lib/anim';
import { css } from '../lib/svg';
import { WM, band } from './shared/s11-geom';

export const S9Close: React.FC = () => {
  const f = useCurrentFrame();
  const b = band();
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <div style={{ position: 'absolute', left: 160, top: 170, ...css('sans', TYPE.hero, COLORS.ash), lineHeight: 1.1, ...rise(f, 15, 14, 16) }}>The model proposes.</div>
      <div style={{ position: 'absolute', left: 160, top: 284, ...css('sans', TYPE.hero, COLORS.ink), lineHeight: 1.1, ...rise(f, 42, 14, 16) }}>The ledger decides.</div>
      <div style={{ position: 'absolute', left: 0, top: 0 }}>
        <Highlight x={b.x} y={b.y} width={b.w} height={b.h} t={progress(f, 0, 24, 'standard')} seed="wordmark" />
      </div>
      <div style={{ position: 'absolute', left: WM.x, top: WM.y, width: wordmarkWidth(WM.size), ...css('sans', WM.size, COLORS.ink), lineHeight: 1, ...rise(f, 8, 18, 30) }}>{PRODUCT_NAME}</div>
      <div style={{ position: 'absolute', left: 160, top: WM.y + WM.size + 28, ...css('sans', TYPE.eyebrow, COLORS.ash), ...rise(f, 56, 12, 8) }}>
        Checks the reasons in month-end variance explanations against the company&apos;s transactions.
      </div>
    </AbsoluteFill>
  );
};
