// Contact sheet: one thumbnail of the video every `step` frames for a scene, labeled with frame and beat.
// scripts/contact-sheet.ts renders the thumbnails first (public/contact-frames/<scene>/f<frame>.jpeg) and then this
// still, which only tiles images. (Mounting the video once per cell would open dozens of WebGL contexts.)
import { AbsoluteFill, Img, staticFile, type CalculateMetadataFunction } from 'remotion';
import { COLORS, TYPE } from '../brand/tokens';
import { mono } from '../brand/fonts';
import { BEAT, SCENES } from '../timeline';
import { CELL_H, CELL_W, COLS, GAP, HEADER, LABEL, framesFor, type SheetProps } from './contact-layout';

export type { SheetProps };

export const sheetMetadata: CalculateMetadataFunction<SheetProps> = ({ props }) => {
  const rows = Math.ceil(framesFor(props).length / COLS);
  return {
    width: COLS * CELL_W + (COLS + 1) * GAP,
    height: HEADER + rows * (CELL_H + LABEL + GAP) + GAP,
  };
};

export const ContactSheet: React.FC<SheetProps> = (props) => {
  const frames = framesFor(props);
  const spec = props.scene === 'all' ? null : SCENES.find((x) => x.id === props.scene)!;
  return (
    <AbsoluteFill style={{ backgroundColor: '#2a2a2a', fontFamily: mono, color: '#ddd' }}>
      <div
        style={{
          position: 'absolute',
          left: GAP,
          top: 22,
          fontSize: TYPE.label,
        }}
      >
        {spec ? `${spec.id} · ${spec.label} · frames ${spec.from}–${spec.from + spec.durationInFrames}` : 'Full video'} · every {props.step} f
      </div>
      {frames.map((f, i) => {
        const c = i % COLS;
        const r = Math.floor(i / COLS);
        const x = GAP + c * (CELL_W + GAP);
        const y = HEADER + r * (CELL_H + LABEL + GAP);
        return (
          <div
            key={f}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: CELL_W,
              height: CELL_H + LABEL,
            }}
          >
            <Img
              src={staticFile(`contact-frames/${props.scene}/f${f}.jpeg`)}
              style={{
                display: 'block',
                width: CELL_W,
                height: CELL_H,
                backgroundColor: COLORS.bone,
              }}
            />
            <div
              style={{
                fontSize: 16,
                marginTop: 6,
                color: f % BEAT === 0 ? '#ddd' : '#999',
              }}
            >
              {`f${f}${spec ? ` · local ${f - spec.from}` : ''} · beat ${(f / BEAT).toFixed(1)}`}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
