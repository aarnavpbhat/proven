import { Composition, Folder, getInputProps } from 'remotion';
import { Demo } from './Demo';
import { CANVAS } from './brand/tokens';
import { FontGate } from './components/FontGate';
import { FPS, TOTAL_FRAMES, validateTimeline } from './timeline';
import { checkResults } from './data/check';
import { ContactSheet, sheetMetadata, type SheetProps } from './tools/ContactSheet';
import { TextAudit } from './tools/TextAudit';

const problems = [...validateTimeline(), ...checkResults()];
if (problems.length > 0) throw new Error(`Project data is inconsistent:\n- ${problems.join('\n- ')}`);

// `npm run text-check` renders with { audit: true }: the auditor mounts after the content and measures it.
const AUDIT = Boolean((getInputProps() as { audit?: boolean }).audit);

const GatedDemo: React.FC = () => (
  <FontGate>
    <Demo />
    {AUDIT && <TextAudit />}
  </FontGate>
);

const GatedSheet: React.FC<SheetProps> = (p) => (
  <FontGate>
    <ContactSheet {...p} />
  </FontGate>
);

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Demo" component={GatedDemo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={CANVAS.width} height={CANVAS.height} />
    <Folder name="Tools">
      <Composition
        id="ContactSheet"
        component={GatedSheet}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={{ scene: 's1', step: 15 } as SheetProps}
        calculateMetadata={sheetMetadata}
      />
    </Folder>
  </>
);
