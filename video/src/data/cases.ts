// Case data shown in the walkthrough and examples: sentences, ledger lines and checker output for specific closes.
// These are not statistics (those live in results.ts); they are the content of fictional closes, copied from the
// real checker's output. Regenerate with scripts/py/walkthrough_data.py and scripts/py/teacher_example.py
// (read-only against the repo, Proven 0.1.0 / verifier 0.1, branch `worlds` at f69dda2).
//
// Real vendor names that occur in the synthetic ledgers (ad networks, cloud providers, airlines) are never shown:
// rows show their ID, date and memo only.

export type Verdict = 'PASS' | 'FAIL' | 'REVIEW';

// ── 1. The demo close: Lumen Robotics, Inc. (proven/showcase.py, pinned by proven/tests/test_showcase.py) ────────
export const LUMEN = {
  entity: 'Lumen Robotics, Inc.',
  close: 'Lumen Robotics, Inc. — October 2026 close',
  // The commentary as pasted. One line is left out of the video because it names a real cloud provider; its claim
  // tag (C3) is skipped in the excerpt, not renumbered.
  sentences: [
    { tag: 'C1', verdict: 'FAIL' as Verdict, text: 'Legal costs rose $90K because of our Series B funding round.' },
    { tag: 'C2', verdict: 'FAIL' as Verdict, text: 'Marketing spend increased $67K, driven by the DevSummit sponsorship.' },
    { tag: 'C4', verdict: 'PASS' as Verdict, text: 'Software & subscriptions rose $31.6K due to annual license renewals.' },
    { tag: 'C5', verdict: 'FAIL' as Verdict, text: 'Contractor costs increased $22K due to the website redesign.' },
    { tag: 'C6', verdict: 'PASS' as Verdict, text: 'The $45K increase in recruiting fees was primarily due to the VP Engineering search.' },
    { tag: 'C7', verdict: 'REVIEW' as Verdict, text: 'Travel fell $12K, reflecting fewer customer visits.' },
    { tag: 'C8', verdict: 'REVIEW' as Verdict, text: 'Lab equipment spend rose $15K for the new test rig.' },
  ],
  // The Exceptions list (FAIL first, then REVIEW), as the console shows it.
  exceptions: [
    { tag: 'C1', verdict: 'FAIL' as Verdict, account: 'Legal & Professional Fees', change: '+$44,900', reason: 'States $90K; the ledger shows +$44,900.' },
    { tag: 'C2', verdict: 'FAIL' as Verdict, account: 'Marketing & Advertising', change: '+$67,400', reason: 'The stated reason accounts for +$22,150 (33%) of the +$67,400 change; +$45,250 is unexplained.' },
    { tag: 'C5', verdict: 'FAIL' as Verdict, account: 'Contractors', change: '+$22,300', reason: 'The stated reason moved $0 — 0% of the +$22,300 change.' },
    { tag: 'C7', verdict: 'REVIEW' as Verdict, account: 'Travel & Entertainment', change: '−$12,200', reason: 'No transaction in Travel & Entertainment mentions the stated reason.' },
    { tag: 'C8', verdict: 'REVIEW' as Verdict, account: 'No account identified', change: '', reason: 'The sentence names no account in the chart of accounts.' },
  ],
  // Claim C1 in detail (report.claims[0]).
  c1: {
    quote: 'Legal costs rose $90K because of our Series B funding round.',
    account: 'Legal & Professional Fees',
    reason: 'States $90K; the ledger shows +$44,900.',
    priorLabel: 'Sep 2026',
    currentLabel: 'Oct 2026',
    prior: 9500,
    current: 54400,
    change: 44900,
    stated: '$90K',
    statedReason: 'our Series B funding round',
    // Legal & Professional Fees, both periods (proven/showcase.py _ROWS).
    ledger: [
      { id: 'TX-2027', date: '2026-09-03', memo: 'General corporate retainer', amount: 6000, period: 'prior' as const },
      { id: 'TX-2043', date: '2026-09-29', memo: 'Monthly close support', amount: 3500, period: 'prior' as const },
      { id: 'TX-2049', date: '2026-10-02', memo: 'General corporate retainer', amount: 6000, period: 'current' as const },
      { id: 'TX-2064', date: '2026-10-17', memo: 'Series B financing — closing documents', amount: 44780, period: 'current' as const },
      { id: 'TX-2075', date: '2026-10-28', memo: 'Monthly close support', amount: 3620, period: 'current' as const },
    ],
    // POSSIBLE_MISCLASSIFICATION evidence: the other half of the Series B legal work, booked to Marketing.
    misbooked: { id: 'TX-2068', date: '2026-10-21', memo: 'Series B — investor rights agreements', amount: 45100, account: 'Marketing & Advertising' },
    reclassified: 90000,
  },
} as const;

// ── 2. A model proposes, a reviewer teaches (held-out test split, seed 0: "Brightfield Health") ────────────────
// Claude Sonnet 5.5 proposals replayed from the proposal cache (~/proven/.proven/cache, no request sent).
export const BRIGHTFIELD = {
  entity: 'Brightfield Health',
  close: 'Brightfield Health — October 2026 close',
  extractor: 'Claude (sends narrative only)',
  explanation: [
    'October 2026 close — operating expense commentary for Brightfield Health.',
    'The $33.9K increase in marketing was due to our biggest promotion of the year.',
    'Hosting rose $29.7K month over month, driven by the cutover to the new stack.',
    'All other accounts were broadly in line with September.',
  ],
  c1: {
    quote: 'The $33.9K increase in marketing was due to our biggest promotion of the year.',
    account: 'Marketing & Advertising',
    change: 33932.65,
    driver: 'our biggest promotion of the year',
    reasonBefore: 'The reason is supported only through search terms a model proposed.',
    reasonAfter: 'Agrees with the ledger: direction, amount, stated reason.',
    written: ['biggest', 'promotion'],
    model: ['promo', 'campaign', 'sale event', 'coupon', 'discount', 'creative', 'launch'],
    matchedTerm: 'campaign',
    matched: [
      { id: 'TX-1051', date: '2026-10-05', memo: 'Launch campaign — display', amount: 15161.55 },
      { id: 'TX-1061', date: '2026-10-13', memo: 'Q4 launch campaign — paid search', amount: 18530.78 },
    ],
    share: 0.9929, // of the change; the wording ("due to") needs 0.75
    required: 0.75,
  },
  c2: {
    quote: 'Hosting rose $29.7K month over month, driven by the cutover to the new stack.',
    account: 'Cloud Hosting',
    driver: 'the cutover to the new stack',
    model: ['migration', 'new stack', 'migrate', 'parallel run', 'consulting', 'replatform', 'go-live'],
  },
  // learned.make_entry([driver], ['campaign']) and gate.impact(): accepted, no new unsafe PASS, no new control FAIL.
  lesson: { trigger: 'our biggest promotion of the year', terms: ['campaign'] },
  gateLine: 'no wrong explanation passes and no right one fails.',
} as const;

// ── 3. The next close, rules only (held-out test split, seed 1155: "Cobalt Freight") ─────────────────────────
export const COBALT = {
  entity: 'Cobalt Freight',
  close: 'Cobalt Freight — October 2026 close',
  extractor: 'Rules (offline)',
  c1: {
    quote: 'The $38.5K increase in marketing was due to our biggest promotion of the year.',
    account: 'Marketing & Advertising',
    change: 38484.17,
    reasonBefore: 'No transaction in Marketing & Advertising mentions the stated reason.',
    matched: [
      { id: 'TX-1056', date: '2026-10-10', memo: 'Launch campaign — display', amount: 17404.82 },
      { id: 'TX-1068', date: '2026-10-22', memo: 'Q4 launch campaign — paid search', amount: 21272.56 },
    ],
  },
} as const;

// ── 4. Rebuilt training targets (training/build_worlds_dataset.py --teacher, committed on `worlds` in cd22662) ─
// A dev world (training/worlds/dev/commercial-laundry-service.json, used for validation loss only), one cause.
// Teacher guesses: ~/proven/.proven/ft/teacher/commercial-laundry-service.json (training/teacher_terms.py output).
// `targets` is the output of build_worlds_dataset.targets() for this claim.
export const TEACHER = {
  sentence: 'The $23K increase in textile stock was because of the batch that came back the wrong shade.',
  account: 'Linen Replacement & Textile Stock',
  vendor: 'Harlan Dye & Finishing LLC',
  memos: ['Navy tablecloth dye lot rejection reorder PO 52044', 'Navy tablecloth dye lot rejection credit shortfall PO 52045'],
  gold: ['navy', 'tablecloth', 'dye', 'lot', 'rejection', 'harlan'],
  vendorOnly: ['harlan'],
  guesses: ['reorder', 'off-color', 'color mismatch', 'dye lot', 'defective', 'credit memo', 'return to vendor', 'rejected shipment'],
  hits: ['reorder', 'dye lot'],
  targets: ['reorder', 'dye lot', 'navy', 'tablecloth', 'dye', 'lot', 'rejection', 'off-color'],
} as const;

// ── 5. Worlds (proven/examples/worlds/unseen/*.json "industry"; training/industries-train-*.txt) ───────────────
export const UNSEEN_INDUSTRIES = [
  'Childcare center chain',
  'Cold-storage warehouse operator',
  'Cruise line',
  'Esports league operator',
  'Funeral home group',
  'Municipal water utility',
  'Orthopedic surgery center',
  'Precision agriculture equipment dealer',
  'Quarry and aggregates supplier',
  'Satellite ground station operator',
  'Streaming video platform',
] as const;

export const TRAIN_INDUSTRY_SAMPLE = [
  'Regional trucking and freight',
  'Craft brewery',
  'Dental practice group',
  'Commercial construction contractor',
  'Boutique hotel chain',
  'Community hospital',
  'Video game studio',
  'Organic grocery chain',
  'Solar panel installer',
  'Veterinary clinic network',
  'Law firm',
  'Commercial bakery',
] as const;

/** "$44,900" style (whole dollars), with an explicit sign when asked. */
export const usd = (n: number, opts: { sign?: boolean; cents?: boolean } = {}): string => {
  const abs = Math.abs(n);
  const body = abs.toLocaleString('en-US', { minimumFractionDigits: opts.cents ? 2 : 0, maximumFractionDigits: opts.cents ? 2 : 0 });
  const sign = n < 0 ? '−' : opts.sign ? '+' : '';
  return `${sign}$${body}`;
};
