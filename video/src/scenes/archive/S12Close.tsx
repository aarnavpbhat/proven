// Scene 12 · Close (4530–4680), VO 16. Bone ground, ink wordmark on its chartreuse band. The band carried from S10 finishes drawing and the wordmark rises onto it;
// the two-line thesis lands above it with the VO; then a held end frame (≥ 45 frames).
// Principles: staging (one lockup, left-aligned), follow-through (the band completes as the name settles),
// anticipation (the band is drawn before the name), slow in / slow out, timing (VO lines on beats 1 and 3).
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, TYPE } from '../brand/tokens';
import { Highlight } from '../components/Highlight';
import { wordmarkWidth } from '../components/Wordmark';
import { mix, progress, rise } from '../lib/anim';
import { css } from '../lib/svg';
import { PRODUCT_NAME } from '../brand/tokens';
import { BAND_START, WM, band } from './shared/s11-geom';

export const S12Close: React.FC = () => {
  const f = useCurrentFrame();
  const b = band();
  const swipe = mix(BAND_START, 1, progress(f, 0, 24, 'standard'));
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <div style={{ position: 'absolute', left: 160, top: 170, ...css('sans', TYPE.hero, COLORS.ash), lineHeight: 1.1, ...rise(f, 15, 14, 16) }}>The model proposes.</div>
      <div style={{ position: 'absolute', left: 160, top: 284, ...css('sans', TYPE.hero, COLORS.ink), lineHeight: 1.1, ...rise(f, 45, 14, 16) }}>The ledger decides.</div>
      <div style={{ position: 'absolute', left: 0, top: 0 }}>
        <Highlight x={b.x} y={b.y} width={b.w} height={b.h} t={swipe} seed="wordmark" />
      </div>
      <div style={{ position: 'absolute', left: WM.x, top: WM.y, width: wordmarkWidth(WM.size), ...css('sans', WM.size, COLORS.ink), lineHeight: 1, ...rise(f, 8, 18, 30) }}>{PRODUCT_NAME}</div>
      <div style={{ position: 'absolute', left: 160, top: WM.y + WM.size + 28, ...css('sans', TYPE.eyebrow, COLORS.ash), ...rise(f, 60, 12, 8) }}>
        Checks the reasons in month-end variance explanations against the company&apos;s transactions.
      </div>
    </AbsoluteFill>
  );
};
