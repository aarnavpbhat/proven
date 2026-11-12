// Purity gate (from the v2 editor's CLAUDE.md): nothing in src/ may animate outside the frame number.
// Fails on CSS transitions/animations/keyframes, timers, requestAnimationFrame, animation libraries, Math.random,
// Date, and three.js / R3F clocks. Usage: npm run purity
import fs from 'node:fs';
import path from 'node:path';
import { ROOT } from './lib';

const BANNED = /transition|animation|@keyframes|setTimeout|setInterval|requestAnimationFrame|framer-motion|Math\.random|Date\.now|new Date|useFrame|Clock/;
const files: string[] = [];
const walk = (d: string): void => {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(tsx?|css)$/.test(e.name)) files.push(p);
  }
};
walk(path.join(ROOT, 'src'));
let bad = 0;
for (const f of files) {
  fs.readFileSync(f, 'utf8')
    .split('\n')
    .forEach((line, i) => {
      if (BANNED.test(line)) {
        bad++;
        console.log(`${path.relative(ROOT, f)}:${i + 1}: ${line.trim()}`);
      }
    });
}
console.log(bad ? `\n${bad} purity violation(s).` : `Purity: clean (${files.length} files).`);
process.exit(bad ? 1 : 0);
