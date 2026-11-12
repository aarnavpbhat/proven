// The walkthrough's step bar: a band across the top of the frame (above STAGE, so it never covers what the camera
// frames) that names the five steps and shows which one is on screen. In the video's own type, not the console's.
import { COLORS, TYPE } from '../brand/tokens';
import { css } from '../lib/svg';

export const STEPS = ['Paste and verify', 'Check a claim', 'A model proposes', 'Teach it once', 'Next close: rules only'] as const;
export const STEP_BAND = 56;

export const Steps: React.FC<{ active: number }> = ({ active }) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      top: 0,
      width: 1920,
      height: STEP_BAND,
      backgroundColor: COLORS.paper,
      boxShadow: `0 1px 0 ${COLORS.hairline}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 44,
    }}
  >
    {STEPS.map((label, i) => {
      const n = i + 1;
      const on = n === active;
      const done = n < active;
      return (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 21,
              backgroundColor: on ? COLORS.chartreuse : done ? COLORS.ink : COLORS.hairline,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span style={css('sans', TYPE.label, done ? COLORS.paper : on ? COLORS.ink : COLORS.ash, 600)}>{n}</span>
          </div>
          <span style={css('sans', TYPE.eyebrow, on ? COLORS.ink : COLORS.ash, on ? 600 : 400)}>{label}</span>
        </div>
      );
    })}
  </div>
);
