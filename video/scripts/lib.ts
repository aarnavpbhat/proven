import path from 'node:path';
import { bundle } from '@remotion/bundler';

export const ROOT = path.resolve(import.meta.dirname, '..');

export const arg = (name: string, fallback?: string): string | undefined => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
};

export const bundleProject = async () => {
  await guardMemory();
  return bundle({ entryPoint: path.join(ROOT, 'src/index.ts') });
};

// No WebGL in this project; the default headless Chrome backend is enough. Kept as a hook for render options.
export const CHROMIUM = {};
// One frame at a time: a model-training job shares this machine (see README, "Machine safety").
export const CONCURRENCY = 1;

/**
 * Free-memory guard (macOS kern.memorystatus_level, percent free). Renders refuse to start under 25 %
 * (README, "Machine safety"). Set PROVEN_SKIP_MEMORY_GUARD=1 only on a machine with nothing else running.
 */
export const guardMemory = async (min = 25): Promise<void> => {
  if (process.env.PROVEN_SKIP_MEMORY_GUARD === '1' || process.platform !== 'darwin') return;
  const { execFileSync } = await import('node:child_process');
  const level = Number(execFileSync('sysctl', ['-n', 'kern.memorystatus_level']).toString().trim());
  if (Number.isFinite(level) && level < min) {
    console.error(`Free memory is ${level}% (< ${min}%). Not rendering; try again later.`);
    process.exit(2);
  }
};
