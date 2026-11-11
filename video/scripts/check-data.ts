// Data checks: timeline consistency, every statistic sourced, pending entries well-formed, the narration in
// docs/script.md identical to the VO lines in src/timeline.ts, and recorded takes (if any) inside their slots.
// Usage: npm run check-data
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { checkResults } from '../src/data/check';
import { allStats } from '../src/data/results';
import { facecamFile, TAKES, voiceFile } from '../src/data/voice';
import { FPS, VO, validateTimeline } from '../src/timeline';
import { ROOT } from './lib';

const errors = [...validateTimeline(), ...checkResults()];
const stats = allStats();
const pending = stats.filter((s) => s.stat.pending);

const script = fs.readFileSync(path.join(ROOT, 'docs/script.md'), 'utf8');
for (const l of VO) {
  const plain = l.text.replace(/ \| /g, ' ');
  if (!script.includes(plain)) errors.push(`docs/script.md does not contain VO line ${l.n} verbatim: "${plain.slice(0, 60)}…"`);
}

const duration = (file: string): number | null => {
  try {
    return Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file]).toString().trim());
  } catch {
    return null;
  }
};
for (const l of VO) {
  for (const rel of [facecamFile(l.n), voiceFile(l.n)]) {
    const file = path.join(ROOT, 'public', rel);
    if (!fs.existsSync(file)) continue;
    const d = duration(file);
    const lead = TAKES.find((t) => t.line === l.n)?.lead ?? 0;
    const slot = (l.to - l.from + lead) / FPS;
    if (d !== null && d > slot + 0.25) errors.push(`${rel} is ${d.toFixed(2)} s; its slot (with lead) is ${slot.toFixed(2)} s`);
    console.log(`take ${rel}: ${d?.toFixed(2)} s in a ${slot.toFixed(2)} s slot`);
  }
}

console.log(`${stats.length} statistics, ${pending.length} pending:`);
for (const p of pending) console.log(`  pending  ${p.path}  (${p.stat.source})`);
if (errors.length) {
  console.log(`\n${errors.length} problem(s):`);
  for (const e of errors) console.log(`  ✗ ${e}`);
  process.exit(1);
}
console.log('\nData checks: clean.');
