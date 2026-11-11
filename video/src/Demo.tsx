import { AbsoluteFill, Sequence } from 'remotion';
import { COLORS } from './brand/tokens';
import { FaceCam, Subtitles, VoPlaceholder, VoiceTrack } from './components/Slots';
import { SCENES, type SceneId } from './timeline';
import { S1Hook } from './scenes/S1Hook';
import { S2Paste } from './scenes/S2Paste';
import { S3Waits } from './scenes/S3Waits';
import { S4Gate } from './scenes/S4Gate';
import { S5NextClose } from './scenes/S5NextClose';
import { S6Loop } from './scenes/S6Loop';
import { S7Proof } from './scenes/S7Proof';
import { S8Next } from './scenes/S8Next';
import { S9Close } from './scenes/S9Close';

// One component per scene, mounted at its range from timeline.ts. Voice slots and subtitles sit on top.
const SCENE_COMPONENTS: Record<SceneId, React.FC> = {
  s1: S1Hook,
  s2: S2Paste,
  s3: S3Waits,
  s4: S4Gate,
  s5: S5NextClose,
  s6: S6Loop,
  s7: S7Proof,
  s8: S8Next,
  s9: S9Close,
};

export const Demo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
    {SCENES.map((s) => {
      const Scene = SCENE_COMPONENTS[s.id];
      return (
        <Sequence key={s.id} from={s.from} durationInFrames={s.durationInFrames} name={`${s.id} · ${s.label}`}>
          <Scene />
        </Sequence>
      );
    })}
    <FaceCam />
    <VoiceTrack />
    <Subtitles />
    <VoPlaceholder />
  </AbsoluteFill>
);
