// Consistency checks on the numbers file, run when the composition loads (Root.tsx) and by `npm run check-data`.
import { allStats } from './results';

export const checkResults = (): string[] => {
  const errors: string[] = [];
  for (const { path, stat } of allStats()) {
    if (!stat.source.trim()) errors.push(`${path}: no source`);
    if (stat.pending && stat.value !== null) errors.push(`${path}: pending but has a value (set pending: false)`);
    if (!stat.pending && (stat.value === null || !Number.isFinite(stat.value))) errors.push(`${path}: not pending but has no value`);
    if (!stat.pending && /TODO/.test(stat.source)) errors.push(`${path}: filled in, but its source still says TODO`);
  }
  return errors;
};
