// @ts-check
/**
 * Proven reviewer console.
 *
 * Plain ES module, no build step, no dependencies: `python -m proven serve` is
 * the whole toolchain a reviewer needs. Type-checked under `tsc --strict`
 * through JSDoc (see tsconfig.json in this directory), so the API contract
 * below is checked rather than assumed.
 *
 * The screen follows the reviewer's job: claim, source, reconstruction,
 * verdict, reason — and one action. Every verdict, number and finding is
 * computed by the server; this file formats and arranges, and decides nothing.
 */

/** @typedef {"PASS"|"FAIL"|"REVIEW"} Verdict */
/** @typedef {{text: string, value: number, half_unit: number}} Figure */
/** @typedef {{text: string, origin: string}} Term */
/**
 * @typedef {{claim_id: string, span: [number, number], quote: string, account: string|null,
 *   account_origin: string|null, direction: string|null,
 *   stated: {change: Figure|null, percent: Figure|null, prior: Figure|null, current: Figure|null},
 *   driver: string|null, terms: Term[], strength: string, extractor: string, notes: string[]}} Claim
 */
/** @typedef {{name: string, ran: boolean, outcome: string, detail: string}} Check */
/** @typedef {{code: string, severity: string, summary: string, detail: string, evidence: string[]}} Finding */
/** @typedef {{id: string, term: string, origin: string, period: string, amount: number}} Match */
/**
 * @typedef {{matched: Match[], prior: number, current: number, change: number, share: number,
 *   share_anchored: number, required_share: number, residual: number}} DriverRecon
 */
/** @typedef {{vendor: string, prior: number, current: number, change: number, txn_ids: string[]}} Mover */
/**
 * @typedef {{account?: string, prior?: number, current?: number, change?: number,
 *   change_pct?: number|null, movers?: Mover[], driver?: DriverRecon, residual?: number|null,
 *   reclassified_change?: number|null}} Recon
 */
/**
 * @typedef {{claim: Claim, verdict: Verdict, computed_verdict: Verdict, reason: string,
 *   checks: Check[], findings: Finding[], reconstruction: Recon, adjustments: string[]}} ClaimResult
 */
/** @typedef {{id: string, date: string, account: string, vendor: string, memo: string, amount: number}} Txn */
/** @typedef {{account: string, prior: number, current: number, change: number, change_pct: number|null, total: boolean}} AccountRow */
/**
 * @typedef {{entity: string, prior_period: string, current_period: string, accounts: AccountRow[],
 *   transaction_count: number, sha256: string}} LedgerSummary
 */
/**
 * @typedef {{sentences: number, sentences_with_figures: number, claims: number, decided: number,
 *   decided_share: number, verdicts: Record<string, number>, unextracted: number, rejected: number}} Coverage
 */
/** @typedef {{provider: string, model: string, bytes: number, sent: string[], not_sent: string[]}} Transmission */
/**
 * @typedef {{run_id: string, created_at: string, explanation_sha256: string, ledger_sha256: string,
 *   versions: Record<string, string>, policy: Record<string, number>,
 *   network: {allowed: boolean, transmissions: Transmission[]}}} RunInfo
 */
/**
 * @typedef {{run: RunInfo, explanation: string, ledger: LedgerSummary, coverage: Coverage,
 *   claims: ClaimResult[], unextracted: {start: number, end: number, text: string}[],
 *   rejected: {quote: string, reason: string, extractor: string}[], transactions: Record<string, Txn>,
 *   usage?: Usage, answer_key?: KeyRow[]}} VerifyReport
 */
/** @typedef {{id: string, kind: string, title: string, family?: string}} ScenarioRef */
/**
 * @typedef {{quote: string, family: string, kind: string, requirement: string,
 *   expected_codes: string[], culprits: string[], account: string}} GroundLabel
 */
/**
 * @typedef {{id: string, title: string, explanation: string,
 *   ground_truth: {family: string, requirement: string, labels: GroundLabel[]}|null,
 *   answer_key?: KeyRow[]}} Scenario
 */
/** @typedef {{id: string, label: string, help: string, reduces_review: boolean}} Action */
/**
 * @typedef {{id: string, created_at: string, triggers: string[], terms: string[],
 *   provenance: {run_id: string, claim_id: string, quote: string, action: string, note: string}}} Lesson
 */
/**
 * @typedef {{accepted: boolean, refusal: string|null, tested: boolean, new_unsafe_passes: number,
 *   new_control_fails: number, newly_passed_right: number, newly_failed_wrong: number, touched: number,
 *   cases_changed: number, elapsed_ms: number}} GateSummary
 */
/**
 * @typedef {{touched: number, touched_wrong: number, touched_right: number, new_unsafe_passes: number,
 *   new_control_fails: number, newly_passed_right: number, newly_failed_wrong: number, unpassed_right: number}} GateRegression
 */
/** @typedef {{quote: string, before: string|null, after: string|null}} VerdictChange */
/**
 * @typedef {{accepted: boolean, refusal: string|null, tested: boolean, regression: GateRegression,
 *   cases: {n: number, touched: number, changed: VerdictChange[], new_unsafe_passes: number, new_control_fails: number},
 *   regression_set: {claims?: number, closes?: number}, elapsed_ms: number, claim?: VerdictChange}} GateReport
 */
/**
 * @typedef {{key: string, run_id: string, quote: string, driver: string, scenario_id: string, uploaded: boolean,
 *   entity: string, extractor: string}} QueueExample
 */
/**
 * @typedef {{trigger: string, terms: string[], waiting: number, proposing: number, runs: number,
 *   example: QueueExample, unlocks: number|null, impact: GateSummary|null}} QueueItem
 */
/** @typedef {{items: QueueItem[], waiting: number, runs: number}} TeachQueue */
/**
 * @typedef {{key: string, run_id: string, explanation: string, scenario_id: string, ledger_csv: string,
 *   entity: string, extractor: string, created_at: string}} PendingRun
 */
/** @typedef {{quote: string, triggers: string[], terms: string[], item: QueueItem}} Prefill */
/** @typedef {{ok: boolean, lesson?: Lesson, verdict_before?: Verdict, verdict_after?: Verdict, impact?: GateReport}} Recorded */
/**
 * @typedef {{id: string, label: string, available: boolean, reason: string, uses_model: boolean,
 *   default_model: string, models: string[]}} ExtractorInfo
 */
/**
 * @typedef {{extractor: string, model: string, calls: number, input_tokens: number, output_tokens: number,
 *   tokens: number, max_tokens: number, usd: number, max_usd: number|null,
 *   cache: {hits: number, misses: number}}} Usage
 */
/**
 * @typedef {{quote: string, requirement: string, defective: boolean, why: string, culprits: string[],
 *   defect: string|null, verdict: string, met: boolean, claim_id: string|null}} KeyRow
 */
/**
 * @typedef {{version: string, network: {allowed: boolean, guard_installed: boolean},
 *   extractors: ExtractorInfo[], policy: Record<string, number>, actions: Action[],
 *   benchmark_extractors: string[], learned: {active: number}}} Config
 */
/**
 * @typedef {{family: string, kind: string, requirement: string, expected_codes: string[], n: number,
 *   met: number, met_rate: number, codes_rate: number|null, evidence_recall: number|null,
 *   evidence_precision: number|null, verdicts: Record<string, number>, mean_reward: number}} FamilyRow
 */
/**
 * @typedef {{extractor: string, split: string, phrasing: string, scenarios: number, claims: number, families: FamilyRow[],
 *   controls: {n: number, passed: number, false_alarms: number, fails: number},
 *   defects: {n: number, caught: number, flagged: number, unsafe_passes: number, missed: number},
 *   coverage: {claims: number, decided: number, decided_share: number}, mean_reward: number}} Benchmark
 */

// ── DOM helpers ──────────────────────────────────────────────────────────

/**
 * @template {HTMLElement} T
 * @param {string} id
 * @returns {T}
 */
function byId(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing element #${id}`);
  return /** @type {T} */ (el);
}

/** @typedef {Node | string | number | null | undefined | false} Child */

/**
 * Create an element. Text children are inserted as text nodes, never as HTML,
 * because the explanation and every memo shown here are user-supplied.
 * @param {string} tag
 * @param {Record<string, string | number | boolean | null | undefined | EventListener>} [attrs]
 * @param {...(Child | Child[])} children
 * @returns {HTMLElement}
 */
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = String(value);
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

/** @param {Element} el @param {...(Child | Child[])} children */
function replace(el, ...children) {
  el.replaceChildren();
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

// ── formatting (presentation only; every number comes from the server) ──

/** @param {number} value */
const money = (value) =>
  `${value < -0.005 ? "-" : ""}$${Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
/** @param {number} value */
const signed = (value) => `${value > 0.005 ? "+" : ""}${money(value)}`;
/** @param {number | null | undefined} value */
const points = (value) => (value === null || value === undefined ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`);
/** @param {number} share */
const share = (share) => `${Math.round(share * 100)}%`;
/** @param {string} period */
function monthLabel(period) {
  const [year, month] = period.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}
/** @param {number} value */
const rate = (value) => `${(value * 100).toFixed(1)}%`;

const STRENGTH = { full: "the whole movement", majority: "most of the movement", partial: "part of the movement" };
const ORIGIN = { quote: "written", lexicon: "lexicon", learned: "learned", model: "model" };
/** @type {Record<string, string>} */
const OUTCOME_CLASS = {
  agree: "good", supported: "good", clear: "good",
  disagree: "bad", wrong_cause: "bad", partial: "bad",
  near: "warn", not_found: "warn", weak_match: "warn", model_only: "warn", flagged: "warn",
};
const ORDER = { FAIL: 0, REVIEW: 1, PASS: 2 };

// ── API ──────────────────────────────────────────────────────────────────

/** A refused request, with the server's whole answer (a refused lesson carries the gate's report). */
class ApiError extends Error {
  /** @param {string} message @param {{error?: string, impact?: GateReport}} data */
  constructor(message, data) {
    super(message);
    this.data = data;
  }
}

/**
 * @template T
 * @param {string} path
 * @param {object} [body]
 * @returns {Promise<T>}
 */
async function api(path, body) {
  const init = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  let response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error("The Proven server is not reachable. Is `python -m proven serve` still running?");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data.error || `Request failed (${response.status})`, data);
  return /** @type {T} */ (data);
}

// ── state ────────────────────────────────────────────────────────────────

const state = {
  /** @type {Config | null} */ config: null,
  /** @type {ScenarioRef[]} */ scenarios: [],
  /** @type {Scenario | null} */ scenario: null,
  /** @type {VerifyReport | null} */ report: null,
  /** @type {{name: string, text: string} | null} */ upload: null,
  /** @type {"exceptions" | "all"} */ filter: "exceptions",
  /** @type {"claims" | "explanation" | "key"} */ pane: "claims",
  editing: false,
  /** @type {string | null} */ active: null,
  /** @type {Record<string, number>} */ openedAt: {},
  /** @type {Record<string, string>} */ resolved: {},
  /** @type {Lesson[]} */ lessons: [],
  /** @type {string | null} */ lessonNotice: null,
  /** @type {TeachQueue | null} */ queue: null,
  /** @type {Prefill | null} */ prefill: null,     // a Teach form opened from the queue
  /** @type {Record<string, Benchmark>} */ bench: {},     // keyed "extractor:phrasing"
  /** @type {"seen" | "heldout" | "paraphrase"} */ benchPhrasing: "seen",
  benchExtractor: "rules",
  /** @type {Record<string, string>} */ models: {},        // the model typed for each extractor
};

const el = {
  banner: byId("banner"),
  status: byId("status"),
  toolbar: /** @type {HTMLFormElement} */ (byId("toolbar")),
  scenario: /** @type {HTMLSelectElement} */ (byId("scenario")),
  extractor: /** @type {HTMLSelectElement} */ (byId("extractor")),
  modelField: byId("model-field"),
  model: /** @type {HTMLInputElement} */ (byId("model")),
  modelList: byId("model-list"),
  extractorNote: byId("extractor-note"),
  heading: byId("review-heading"),
  keyTab: byId("answer-key-tab"),
  detail: byId("claim-detail"),
  coverageBar: byId("coverage-bar"),
  crumbView: byId("crumb-view"),
  keySummary: byId("answer-key-summary"),
  keyList: byId("answer-key"),
  benchExtractor: /** @type {HTMLSelectElement} */ (byId("bench-extractor")),
  verify: /** @type {HTMLButtonElement} */ (byId("verify")),
  runMeta: byId("run-meta"),
  annotated: byId("annotated"),
  editor: /** @type {HTMLTextAreaElement} */ (byId("explanation")),
  edit: /** @type {HTMLButtonElement} */ (byId("edit")),
  groundTruth: byId("ground-truth"),
  download: /** @type {HTMLAnchorElement} */ (byId("download-csv")),
  upload: /** @type {HTMLInputElement} */ (byId("upload-csv")),
  ledgerSource: byId("ledger-source"),
  variance: /** @type {HTMLTableElement} */ (byId("variance")),
  priorHead: byId("prior-head"),
  currentHead: byId("current-head"),
  coverage: byId("coverage"),
  claims: byId("claims"),
  unextracted: byId("unextracted"),
  lessonNotice: byId("lesson-notice"),
  lessons: byId("lessons"),
  lessonCount: byId("lesson-count"),
  queue: byId("queue"),
  queueCount: byId("queue-count"),
  queueRefresh: /** @type {HTMLButtonElement} */ (byId("queue-refresh")),
  benchForm: /** @type {HTMLFormElement} */ (byId("bench-form")),
  benchSplit: /** @type {HTMLSelectElement} */ (byId("bench-split")),
  benchN: /** @type {HTMLInputElement} */ (byId("bench-n")),
  benchRun: /** @type {HTMLButtonElement} */ (byId("bench-run")),
  benchMeta: byId("bench-meta"),
  benchSummary: byId("bench-summary"),
  benchFamilies: byId("bench-families"),
};

/** @param {string | null} message */
function showError(message) {
  el.banner.hidden = !message;
  el.banner.textContent = message || "";
}

// ── review: loading and running ──────────────────────────────────────────

async function loadScenario(/** @type {string} */ id) {
  await prepareScenario(id);
  await verify();
}

/** Fetch a close and put its text, ledger link and ground truth on screen, without verifying. */
async function prepareScenario(/** @type {string} */ id) {
  /** @type {Scenario} */
  const scenario = await api(`/api/scenario?id=${encodeURIComponent(id)}`);
  state.scenario = scenario;
  state.lessonNotice = null;
  state.prefill = null;
  state.upload = null;
  state.resolved = {};
  el.editor.value = scenario.explanation;
  el.heading.textContent = scenario.title;
  el.download.href = `/api/ledger.csv?id=${encodeURIComponent(id)}`;
  el.download.setAttribute("download", `${id}-ledger.csv`);
  const truth = scenario.ground_truth;
  el.groundTruth.hidden = !truth && !scenario.answer_key;
  if (!truth && scenario.answer_key) {
    replace(el.groundTruth, h("strong", {}, "Hand-written example: "),
      "the answer key was written from the ledger before Proven was run on it; see the Answer key panel.");
  }
  if (truth) {
    const target = truth.labels[0];
    replace(el.groundTruth, h("strong", {}, "Ground truth (synthetic): "),
      `${truth.family.replace(/_/g, " ")} — must ${truth.requirement === "NOT_PASS" ? "not pass" : truth.requirement.toLowerCase()}`,
      target.culprits.length ? `; culprit transactions ${target.culprits.join(", ")}` : "",
      `. The other ${truth.labels.length - 1} claim(s) are correct.`);
  }
}

/** @returns {Promise<boolean>} whether a new report is on screen */
async function verify() {
  if (!state.scenario) return false;
  const body = {
    explanation: el.editor.value,
    extractor: el.extractor.value,
    ...(selectedExtractor()?.uses_model && el.model.value.trim() ? { model: el.model.value.trim() } : {}),
    ...(state.upload ? { ledger_csv: state.upload.text, entity: state.upload.name } : { scenario_id: state.scenario.id }),
  };
  el.verify.disabled = true;
  el.verify.textContent = "Verifying…";
  document.body.classList.add("loading");
  const started = performance.now();
  try {
    /** @type {VerifyReport} */
    const fresh = await api("/api/verify", body);
    state.report = fresh;
    // Resolutions belong to a run; claim ids are re-issued by every run.
    state.resolved = {};
    state.openedAt = {};
    state.active = null;
    setEditing(false);
    showError(null);
    render(performance.now() - started);
    // A model run may have added claims that wait for a confirmation.
    if (!fresh.run.versions.extractor.startsWith("rules/")) refreshQueue();
    return true;
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
    return false;
  } finally {
    el.verify.disabled = false;
    el.verify.textContent = "Verify";
    document.body.classList.remove("loading");
  }
}

/** @param {boolean} editing */
function setEditing(editing) {
  state.editing = editing;
  el.editor.hidden = !editing;
  el.annotated.hidden = editing;
  el.edit.textContent = editing ? "Show checked text" : "Edit text";
  if (editing) el.editor.focus();
}

// ── review: rendering ────────────────────────────────────────────────────

/** @param {number} elapsed */
function render(elapsed) {
  const report = state.report;
  if (!report) return;
  const run = report.run;
  const sent = run.network.transmissions;
  replace(el.runMeta,
    `Run ${run.run_id} · ${run.versions.extractor} · verifier ${run.versions.verifier} · ${Math.round(elapsed)} ms`,
    sent.length
      ? ` · sent ${sent.reduce((n, t) => n + t.bytes, 0).toLocaleString()} bytes to ${sent[0].provider} (${sent[0].sent.join(", ")}; no transactions)`
      : " · nothing left this machine");
  if (report.usage) el.runMeta.append(h("br"), h("span", { class: "usage" }, usageText(report.usage)));
  renderAnswerKey(report);
  renderAnnotated(report);
  renderLedger(report);
  renderCoverage(report.coverage);
  renderClaims(report);
  renderUnextracted(report);
  el.lessonNotice.hidden = !state.lessonNotice;
  el.lessonNotice.textContent = state.lessonNotice || "";
}

/** @param {Usage} usage */
function usageText(usage) {
  const cache = `cache ${usage.cache.hits} hit${usage.cache.hits === 1 ? "" : "s"} / ${usage.cache.misses} miss${usage.cache.misses === 1 ? "" : "es"}`;
  const what = `${usage.extractor}${usage.model ? ` ${usage.model}` : ""}`;
  if (!usage.calls) return `${what}: answered from the proposal cache, no request made, 0 tokens · ${cache}`;
  const budget = `${usage.tokens.toLocaleString()} of ${usage.max_tokens.toLocaleString()} token budget`;
  return `${what}: ${usage.calls} request${usage.calls === 1 ? "" : "s"}, ${usage.input_tokens.toLocaleString()} in + ` +
    `${usage.output_tokens.toLocaleString()} out tokens (${budget}) · $${usage.usd.toFixed(4)}` +
    `${usage.max_usd === null ? "" : ` of $${usage.max_usd.toFixed(2)}`} · ${cache}`;
}

/** @returns {ExtractorInfo | undefined} */
function selectedExtractor() {
  return state.config?.extractors.find((x) => x.id === el.extractor.value);
}

/** Show the model field for a model extractor, and say why any extractor is unavailable. */
function updateExtractorUi() {
  const config = state.config;
  if (!config) return;
  const chosen = selectedExtractor();
  el.modelField.hidden = !chosen?.uses_model;
  if (chosen?.uses_model) {
    el.model.value = state.models[chosen.id] ?? chosen.default_model;
    replace(el.modelList, ...chosen.models.map((m) => h("option", { value: m })));
    el.model.placeholder = chosen.default_model || "model id";
  }
  const unavailable = config.extractors.filter((x) => !x.available);
  const sends = chosen?.available && chosen.uses_model
    ? `${chosen.id === "claude" ? "Claude" : "The model server"} receives the explanation text and chart of accounts only, never transactions.`
    : "";
  replace(el.extractorNote,
    ...unavailable.map((x, i) => h("span", {}, i ? " · " : "", h("strong", {}, x.label), `: ${x.reason}`)),
    sends ? ` ${sends}` : "");
}

/** @param {VerifyReport} report */
function renderAnswerKey(report) {
  const key = report.answer_key;
  el.keyTab.hidden = !key;
  if (!key && state.pane === "key") state.pane = "claims";
  showPane();
  if (!key) return;
  const met = key.filter((row) => row.met).length;
  const edited = state.scenario && report.explanation !== state.scenario.explanation;
  replace(el.keySummary,
    `${met} of ${key.length} sentences end where the key says they should (PASS where the key says PASS, FAIL or REVIEW where it says the sentence cannot pass). `,
    edited ? "The text was edited; the key describes the original commentary, so edited sentences show as not extracted." : "");
  replace(el.keyList, ...key.map((row) => h("li", { class: `key-item ${row.met ? "met" : "unmet"}` },
    h("div", { class: "key-row" },
      h("span", { class: `verdict v-${row.verdict}` }, row.verdict === "MISSED" ? "NO CLAIM" : row.verdict),
      h("span", { class: "key-tag" }, `key: ${row.requirement === "NOT_PASS" ? "not PASS" : row.requirement === "NO_CLAIM" ? "no claim" : row.requirement}`),
      h("span", { class: "key-tag" }, row.met ? "agrees" : "differs"),
      row.claim_id ? h("button", { type: "button", class: "button small", onclick: () => focusClaim(/** @type {string} */ (row.claim_id)) }, `Open ${row.claim_id}`) : null),
    h("p", {}, row.quote),
    h("p", { class: "key-why" }, row.why, row.culprits.length ? ` Culprits: ${row.culprits.join(", ")}.` : ""))));
}

/** @param {VerifyReport} report */
function renderAnnotated(report) {
  const text = report.explanation;
  /** @type {{start: number, end: number, node: (inner: string) => HTMLElement}[]} */
  const spans = [];
  for (const result of report.claims) {
    const [start, end] = result.claim.span;
    const id = result.claim.claim_id;
    spans.push({ start, end, node: (inner) => h("mark", {
      class: `v-${result.verdict}${state.active === id ? " active" : ""}`,
      "data-claim": id, tabindex: 0, role: "button",
      "aria-label": `${id}: ${result.verdict}. ${result.reason}`,
      onclick: () => focusClaim(id),
      onkeydown: (/** @type {Event} */ e) => { if (/** @type {KeyboardEvent} */ (e).key === "Enter") focusClaim(id); },
    }, inner, h("sup", {}, id)) });
  }
  for (const missed of report.unextracted) {
    spans.push({ start: missed.start, end: missed.end, node: (inner) =>
      h("span", { class: "unextracted", title: "States a figure, but no checkable claim was extracted" }, inner) });
  }
  spans.sort((a, b) => a.start - b.start);
  /** @type {Child[]} */
  const parts = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.start < cursor) continue;
    parts.push(text.slice(cursor, span.start), span.node(text.slice(span.start, span.end)));
    cursor = span.end;
  }
  parts.push(text.slice(cursor));
  replace(el.annotated, ...parts);
}

/** @param {VerifyReport} report */
function renderLedger(report) {
  const ledger = report.ledger;
  el.priorHead.textContent = monthLabel(ledger.prior_period);
  el.currentHead.textContent = monthLabel(ledger.current_period);
  const activeAccount = state.active
    ? report.claims.find((c) => c.claim.claim_id === state.active)?.claim.account
    : null;
  replace(el.ledgerSource,
    `${ledger.entity} · ${ledger.transaction_count} transactions · sha256 ${ledger.sha256.slice(0, 12)}`,
    state.upload ? h("span", {}, ` · uploaded: ${state.upload.name} `,
      h("button", { type: "button", class: "button small", onclick: () => { state.upload = null; el.upload.value = ""; verify(); } }, "Use scenario ledger")) : "");
  const rows = ledger.accounts.map((row) => h("tr", {
    class: [row.total ? "total" : "", row.account === activeAccount ? "highlight" : ""].join(" ").trim() || null,
  },
  h("th", { scope: "row", class: "wrap" }, row.account),
  h("td", { class: "num" }, money(row.prior)),
  h("td", { class: "num" }, money(row.current)),
  h("td", { class: `num${row.change < 0 ? " neg" : ""}` }, signed(row.change)),
  h("td", { class: "num muted pct" }, points(row.change_pct))));
  replace(el.variance.tBodies[0], ...rows);
}

/** @param {Coverage} coverage */
function renderCoverage(coverage) {
  /** @param {string} label @param {Child} value @param {Child} [sub] @param {string} [tone] */
  const stat = (label, value, sub, tone) => h("div", { class: tone ? `stat v-${tone}` : "stat" },
    h("dt", {}, label), h("dd", {}, value, sub ? h("small", {}, sub) : null));
  const { PASS, FAIL, REVIEW } = coverage.verdicts;
  replace(el.coverage,
    stat("Claims checked", coverage.claims, `of ${coverage.sentences_with_figures} with figures`),
    stat("Pass", PASS, "", "PASS"),
    stat("Fail", FAIL, "", "FAIL"),
    stat("Need review", REVIEW, coverage.unextracted ? `+${coverage.unextracted} not extracted` : "", "REVIEW"),
    stat("Decided", rate(coverage.decided_share), `${coverage.decided} of ${coverage.claims}`));
  // The same counts as proportions; the numbers above remain the record.
  /** @type {[string, number][]} */
  const parts = [["PASS", PASS], ["FAIL", FAIL], ["REVIEW", REVIEW], ["MISSED", coverage.unextracted]];
  el.coverageBar.setAttribute("aria-label",
    `${PASS} pass, ${FAIL} fail, ${REVIEW} need review, ${coverage.unextracted} not extracted`);
  replace(el.coverageBar, ...parts.filter(([, n]) => n > 0).map(([tone, n]) =>
    h("span", { class: `outcome-seg v-${tone}`, style: `flex-grow:${n}` })));
}

/** @param {VerifyReport} report */
function renderClaims(report) {
  for (const button of document.querySelectorAll("[data-filter]")) {
    button.setAttribute("aria-pressed", String(button.getAttribute("data-filter") === state.filter));
  }
  let claims = report.claims.slice();
  if (state.filter === "exceptions") {
    claims = claims.filter((c) => c.verdict !== "PASS").sort((a, b) => ORDER[a.verdict] - ORDER[b.verdict]);
  }
  if (!report.claims.length) {
    replace(el.claims, h("li", { class: "empty" },
      "No claims were extracted. A checkable sentence names an account and states a change, a percentage or a balance."));
    renderDetail(report, null, []);
    return;
  }
  if (!claims.length) {
    replace(el.claims, h("li", { class: "empty" }, `No exceptions: all ${report.claims.length} claims passed.`));
    renderDetail(report, null, []);
    return;
  }
  // The list is the index; the selected claim's working is shown in the detail pane beside it.
  const selected = claims.find((c) => c.claim.claim_id === state.active) || claims[0];
  replace(el.claims, ...claims.map((result) => claimItem(result, report, result === selected)));
  renderDetail(report, selected, claims);
}

/**
 * One row of the claims list.
 * @param {ClaimResult} result
 * @param {VerifyReport} report
 * @param {boolean} selected
 */
function claimItem(result, report, selected) {
  const claim = result.claim;
  const id = claim.claim_id;
  const change = result.reconstruction.change;
  return h("li", { class: `claim${selected ? " active" : ""}`, id: `claim-${id}` },
    h("button", { type: "button", class: "claim-row", "aria-current": selected ? "true" : null, onclick: () => focusClaim(id) },
      h("span", { class: "claim-top" },
        h("span", { class: `verdict v-${result.verdict}` }, result.verdict),
        h("span", { class: "claim-id" }, id),
        h("span", { class: "claim-account" }, claim.account || "No account identified"),
        change === undefined ? null : h("span", { class: "claim-change num" }, signed(change))),
      h("span", { class: "claim-quote" }, claim.quote),
      h("span", { class: "claim-reason" }, result.reason, keyTag(report, id),
        state.resolved[id] ? h("span", { class: "muted" }, ` · resolved: ${state.resolved[id]}`) : null)));
}

/**
 * The detail pane: reason, reconstruction, checks, cited transactions, adjustments, resolution.
 * @param {VerifyReport} report
 * @param {ClaimResult | null} result
 * @param {ClaimResult[]} claims the list as shown, for previous / next
 */
function renderDetail(report, result, claims) {
  if (!result) {
    replace(el.detail, h("p", { class: "empty" }, "No claim selected. A claim's reconstruction, checks and evidence appear here."));
    return;
  }
  const claim = result.claim;
  const id = claim.claim_id;
  const at = claims.indexOf(result);
  /** @param {string} label @param {string} glyph @param {ClaimResult | undefined} target */
  const step = (label, glyph, target) => h("button", {
    type: "button", class: "button small icon-only", "aria-label": label, title: label, disabled: !target,
    onclick: () => { if (target) focusClaim(target.claim.claim_id); },
  }, glyph);
  state.openedAt[id] = state.openedAt[id] || Date.now();
  replace(el.detail,
    h("header", { class: "detail-head" },
      h("h2", {}, h("span", { class: "claim-id" }, id), claim.account || "No account identified"),
      h("div", { class: "detail-nav" },
        h("span", { class: "muted" }, `${at + 1} of ${claims.length}`),
        step("Previous claim", "↑", claims[at - 1]),
        step("Next claim", "↓", claims[at + 1]))),
    h("div", { class: "detail-body" },
      h("div", { class: "detail-lead" },
        h("p", { class: "detail-reason" }, result.reason),
        h("p", { class: "detail-chips" },
          h("span", { class: `verdict v-${result.verdict}` }, result.verdict), keyTag(report, id),
          state.resolved[id] ? h("span", { class: "muted" }, ` · resolved: ${state.resolved[id]}`) : null),
        h("blockquote", { class: "detail-quote" }, claim.quote)),
      reconstruction(result, report),
      checksSection(result.checks),
      findingsSection(result, report),
      moversSection(result, report),
      notesSection(result),
      resolveSection(result, report)));
}

/** Show one of the list pane's views: the claims, the explanation in context, or the answer key. */
function showPane() {
  for (const tab of document.querySelectorAll("[data-pane]")) {
    tab.setAttribute("aria-pressed", String(tab.getAttribute("data-pane") === state.pane));
  }
  for (const part of /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll("[data-pane-body], [data-pane-tools]"))) {
    part.hidden = (part.getAttribute("data-pane-body") || part.getAttribute("data-pane-tools")) !== state.pane;
  }
}

/** @param {VerifyReport} report @param {string} claimId */
function keyTag(report, claimId) {
  const row = report.answer_key?.find((r) => r.claim_id === claimId);
  return row ? h("span", { class: "muted" }, ` · key: ${row.requirement === "NOT_PASS" ? "not PASS" : row.requirement}`) : null;
}

/** @param {ClaimResult} result @param {VerifyReport} report */
function reconstruction(result, report) {
  const claim = result.claim;
  const recon = result.reconstruction;
  const ledger = report.ledger;
  /** @type {Child[]} */
  const rows = [];
  /** @param {string} key @param {...Child} value */
  const row = (key, ...value) => rows.push(h("dt", {}, key), h("dd", {}, ...value));

  row("Account", claim.account || "not identified", claim.account_origin === "model" ? h("span", { class: "muted" }, " · mapped by the model") : "");
  if (recon.change !== undefined && recon.prior !== undefined && recon.current !== undefined) {
    row("Ledger", h("span", { class: "mono" },
      `${monthLabel(ledger.prior_period)} ${money(recon.prior)} → ${monthLabel(ledger.current_period)} ${money(recon.current)} · ${signed(recon.change)} (${points(recon.change_pct)})`));
  }
  const stated = [
    claim.direction ? (claim.direction === "up" ? "rose" : "fell") : null,
    claim.stated.change ? `change ${claim.stated.change.text}` : null,
    claim.stated.percent ? `${claim.stated.percent.text}` : null,
    claim.stated.current ? `to ${claim.stated.current.text}` : null,
    claim.stated.prior ? `from ${claim.stated.prior.text}` : null,
  ].filter(Boolean).join(", ");
  row("Stated", stated || "no figure");
  if (claim.driver) {
    row("Reason", `“${claim.driver}” — claims ${STRENGTH[/** @type {keyof typeof STRENGTH} */ (claim.strength)] || claim.strength}`);
    /** @type {Record<string, string[]>} */
    const groups = {};
    for (const term of claim.terms) (groups[term.origin] = groups[term.origin] || []).push(term.text);
    row("Searched", ...(Object.keys(groups).length
      ? Object.entries(groups).map(([origin, words]) => h("span", { class: origin === "learned" ? "learned-terms" : null },
        `${words.join(", ")} (${ORIGIN[/** @type {keyof typeof ORIGIN} */ (origin)] || origin})`)).flatMap((node, i) => (i ? ["; ", node] : [node]))
      : ["no searchable words"]));
    const driver = recon.driver;
    if (driver && recon.change) {
      row("Matched", h("span", { class: "mono" },
        `${driver.matched.length} txn · ${signed(driver.change)} of ${signed(recon.change)} = ${share(driver.share)}`),
        ` (needs ${share(driver.required_share)})`);
    }
  } else {
    row("Reason", h("span", { class: "muted" }, "none stated"));
  }
  if (recon.reclassified_change !== null && recon.reclassified_change !== undefined) {
    row("If reclassified", h("span", { class: "mono" }, signed(recon.reclassified_change)));
  }
  return h("section", { class: "claim-section" }, h("h3", {}, "Reconstruction"), h("dl", { class: "kv" }, ...rows));
}

/** @param {Check[]} checks */
function checksSection(checks) {
  return h("section", { class: "claim-section" }, h("h3", {}, "Checks"),
    h("ul", { class: "checks" }, ...checks.map((check) => h("li", { class: check.ran ? null : "skipped" },
      h("span", {}, check.name),
      h("span", { class: `outcome ${OUTCOME_CLASS[check.outcome] || ""}` }, check.ran ? check.outcome.replace(/_/g, " ") : "skipped"),
      h("span", {}, check.detail)))));
}

/** @param {ClaimResult} result @param {VerifyReport} report */
function findingsSection(result, report) {
  if (!result.findings.length) return null;
  return h("section", { class: "claim-section" }, h("h3", {}, "Findings"),
    ...result.findings.map((finding) => h("div", { class: `finding ${finding.severity}` },
      h("span", { class: "finding-code" }, `${finding.code} · ${finding.severity}`),
      h("p", { class: "finding-summary" }, finding.summary),
      h("p", { class: "finding-detail" }, finding.detail),
      finding.evidence.length ? txnTable(finding.evidence.map((id) => report.transactions[id]).filter(Boolean), result.claim.account) : null)));
}

/** @param {Txn[]} txns @param {string | null} account */
function txnTable(txns, account) {
  return h("div", { class: "table-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, ...["ID", "Date", "Account", "Vendor", "Memo", "Amount"].map((label, i) =>
      h("th", { scope: "col", class: i === 5 ? "num" : null }, label)))),
    h("tbody", {}, ...txns.map((txn) => h("tr", {},
      h("td", { class: "mono nowrap" }, txn.id),
      h("td", { class: "mono nowrap" }, txn.date),
      h("td", { class: "wrap" }, txn.account, account && txn.account !== account && account !== "Total operating expenses" ? h("span", { class: "muted" }, " (other account)") : ""),
      h("td", { class: "wrap" }, txn.vendor),
      h("td", { class: "wrap" }, txn.memo),
      h("td", { class: "num" }, money(txn.amount)))))));
}

/** @param {ClaimResult} result @param {VerifyReport} report */
function moversSection(result, report) {
  const movers = (result.reconstruction.movers || []).filter((m) => Math.abs(m.change) >= 1);
  if (!movers.length) return null;
  return h("section", { class: "claim-section" }, h("h3", {}, `Largest movements in ${result.claim.account}`),
    h("div", { class: "table-wrap" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Vendor"),
        h("th", { scope: "col", class: "num" }, monthLabel(report.ledger.prior_period)),
        h("th", { scope: "col", class: "num" }, monthLabel(report.ledger.current_period)),
        h("th", { scope: "col", class: "num" }, "Change"))),
      h("tbody", {}, ...movers.slice(0, 5).map((m) => h("tr", {},
        h("td", { class: "wrap" }, m.vendor),
        h("td", { class: "num" }, money(m.prior)),
        h("td", { class: "num" }, money(m.current)),
        h("td", { class: `num${m.change < 0 ? " neg" : ""}` }, signed(m.change))))))));
}

/** @param {ClaimResult} result */
function notesSection(result) {
  const notes = [...result.adjustments, ...result.claim.notes];
  if (!notes.length) return null;
  return h("section", { class: "claim-section" }, h("h3", {}, "Adjustments and notes"),
    h("ul", { class: "unextracted-list" }, ...notes.map((n) => h("li", {}, n))));
}

/** @param {string} text @returns {string[]} */
const splitWords = (text) => text.split(/[,;\n]/).map((w) => w.trim()).filter(Boolean);

/** @param {ClaimResult} result @param {VerifyReport} report */
function resolveSection(result, report) {
  if (result.verdict === "PASS" || !state.config) return null;
  const id = result.claim.claim_id;
  const claim = result.claim;
  const select = /** @type {HTMLSelectElement} */ (h("select", { "aria-label": "Resolution" },
    ...state.config.actions.map((a) => h("option", { value: a.id, title: a.help }, a.label))));
  const note = /** @type {HTMLTextAreaElement} */ (h("textarea", { "aria-label": "Reason for the resolution", placeholder: "Why? (required)", rows: 1 }));
  const status = h("p", { class: "resolve-status", "aria-live": "polite" }, state.resolved[id] ? `Recorded: ${state.resolved[id]}` : (state.config.actions[0].help));

  // "Teach Proven": only for the actions that teach, and only when there is a stated reason to learn from.
  // The model's words that actually matched ledger transactions are offered for confirmation; when
  // they are the only thing between this claim and a PASS, the form opens ready to confirm them.
  const matchedByModel = (result.reconstruction.driver?.matched || []).filter((m) => m.origin === "model");
  const proposed = [...new Set(matchedByModel.map((m) => m.term))];
  const awaitsConfirmation = proposed.length > 0 && result.findings.some((f) => f.code === "SUPPORT_RESTS_ON_MODEL_TERMS");
  // Opened from the teaching queue: the stored run's model words, re-checked here with the rules.
  const prefill = state.prefill && state.prefill.quote === claim.quote ? state.prefill : null;
  const trigger = /** @type {HTMLInputElement} */ (h("input", {
    type: "text", "aria-label": "When the stated reason contains", value: prefill ? prefill.triggers.join(", ") : claim.driver || "",
  }));
  const words = /** @type {HTMLInputElement} */ (h("input", {
    type: "text", "aria-label": "Ledger words it corresponds to", placeholder: "e.g. flights, hotel",
    value: prefill ? prefill.terms.join(", ") : proposed.join(", "),
  }));
  const confirm = /** @type {HTMLInputElement} */ (h("input", { type: "checkbox", id: `confirm-${id}` }));
  const gateOut = h("div", { class: "gate", "aria-live": "polite" }, "Not checked yet. Every lesson is checked when you record it.");
  /** @returns {Record<string, string>} where the claim was checked */
  const ledgerRef = () => (state.upload ? { ledger_csv: state.upload.text, entity: state.upload.name } : { scenario_id: state.scenario?.id || "" });
  const checkButton = /** @type {HTMLButtonElement} */ (h("button", { type: "button", class: "button small" }, "Check with the safety gate"));
  const runCheck = async () => {
    checkButton.disabled = true;
    replace(gateOut, "Replaying the lesson against known answers…");
    gateOut.className = "gate";
    try {
      /** @type {GateReport} */
      const gateReport = await api("/api/lexicon/check", {
        triggers: splitWords(trigger.value), terms: splitWords(words.value),
        explanation: report.explanation, quote: claim.quote, ...ledgerRef(),
      });
      showGate(gateOut, gateSummary(gateReport), gateReport.claim);
    } catch (error) {
      gateOut.className = "gate refused";
      replace(gateOut, h("strong", {}, "Refused"), ` · ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      checkButton.disabled = false;
    }
  };
  checkButton.addEventListener("click", runCheck);
  const teach = h("fieldset", { class: "teach", hidden: true },
    h("legend", {}, "Teach Proven"),
    prefill ? h("p", { class: "hint" },
      `From Teach next: in run ${prefill.item.example.run_id} (${prefill.item.example.extractor}) the model proposed ${prefill.terms.map((w) => `“${w}”`).join(", ")} for this reason, and ${prefill.item.waiting} waiting claim${prefill.item.waiting === 1 ? "" : "s"} use the same phrase. This close was re-checked with the rules alone, so the model's matches are not listed under Findings; check the transactions in Largest movements before you confirm.`)
      : awaitsConfirmation ? h("p", { class: "hint" },
        `The model proposed ${proposed.map((w) => `“${w}”`).join(", ")}, which matched ${matchedByModel.length} transaction${matchedByModel.length === 1 ? "" : "s"} (listed under Findings). Proven will not rely on a model's words alone. If those transactions really are this cause, record it and Proven will know this phrase from now on, with no model needed.`) : null,
    h("label", { class: "field" }, h("span", { class: "field-label" }, "When the stated reason says"), trigger),
    h("label", { class: "field" }, h("span", { class: "field-label" }, "search the ledger for (comma separated; pick words from the transaction memos above)"), words),
    h("div", { class: "gate-row" }, gateOut, checkButton),
    h("label", { class: "check" }, confirm, " If this turns the claim into a PASS: I checked that the matched transactions really are this cause."),
    h("p", { class: "hint" }, "Leave the words empty to record the decision without teaching. A lesson applies to every close until you remove it from the Learned list."));
  /** @param {string} actionId */
  const teaches = (actionId) => Boolean(claim.driver) && Boolean(state.config?.actions.find((a) => a.id === actionId)?.reduces_review);
  select.addEventListener("change", () => {
    const action = state.config?.actions.find((a) => a.id === select.value);
    status.className = "resolve-status";
    status.textContent = action ? action.help : "";
    teach.hidden = !teaches(select.value);
  });
  if ((awaitsConfirmation || prefill) && teaches("accept_convention")) {
    select.value = "accept_convention";
    teach.hidden = false;
    if (!state.resolved[id]) status.textContent = state.config.actions.find((a) => a.id === "accept_convention")?.help || "";
  }
  if (prefill) runCheck();
  const button = /** @type {HTMLButtonElement} */ (h("button", { type: "submit", class: "button" }, "Record"));
  const form = h("form", { class: "resolve" }, select, note, button, teach, status);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    try {
      const opened = state.openedAt[id];
      const lesson = teaches(select.value) && splitWords(words.value).length
        ? { triggers: splitWords(trigger.value), terms: splitWords(words.value), confirm_pass: confirm.checked }
        : undefined;
      /** @type {Recorded} */
      // The text and ledger go with every decision, so the safety gate can replay it later
      // ("Confirm defect" becomes a known-wrong case no lesson may pass).
      const saved = await api("/api/resolutions", {
        run_id: report.run.run_id, claim_id: id, quote: claim.quote, verdict: result.verdict,
        action: select.value, note: note.value,
        seconds_on_claim: opened ? Math.round((Date.now() - opened) / 1000) : null,
        explanation: report.explanation, ...ledgerRef(),
        ...(lesson ? { learn: lesson, extractor: "rules" } : {}),
      });
      const label = select.options[select.selectedIndex].text;
      if (saved.lesson) {
        await afterLesson(claim.quote, label, saved);
        return;
      }
      state.resolved[id] = label;
      status.className = "resolve-status ok";
      status.textContent = `Recorded: ${label}, appended to the resolutions log.`;
      refreshQueue();
    } catch (error) {
      status.className = "resolve-status err";
      status.textContent = error instanceof Error ? error.message : String(error);
      const impact = error instanceof ApiError ? error.data.impact : undefined;
      if (impact) showGate(gateOut, gateSummary(impact), impact.claim);
    } finally {
      button.disabled = false;
    }
  });
  return h("section", { class: "claim-section" }, h("h3", {}, "Resolve"), form);
}

/**
 * Re-run Verify so the reviewer sees what the lesson did to this claim.
 * @param {string} quote @param {string} label @param {Recorded} saved
 */
async function afterLesson(quote, label, saved) {
  await refreshLessons();
  const gate = saved.impact ? ` ${gateSentence(gateSummary(saved.impact))}` : "";
  const text = `Taught Proven (${label}): “${saved.lesson?.triggers.join(" / ")}” → ${saved.lesson?.terms.join(", ")}. ` +
    `This claim: ${saved.verdict_before} → ${saved.verdict_after}.${gate}`;
  state.lessonNotice = text;
  state.prefill = null;
  refreshQueue();
  if (!(await verify()) || !state.report) return;
  const now = state.report.claims.find((c) => c.claim.quote === quote);
  if (now) {
    state.active = now.claim.claim_id;
    if (now.verdict === "PASS") state.filter = "all";
    state.resolved[now.claim.claim_id] = label;
    renderAnnotated(state.report);
    renderLedger(state.report);
    renderClaims(state.report);
  }
  document.getElementById(`claim-${state.active}`)?.scrollIntoView({ block: "nearest" });
}

// ── the safety gate and the teaching queue ──────────────────────────────

/** @param {GateReport} report @returns {GateSummary} */
function gateSummary(report) {
  return {
    accepted: report.accepted, refusal: report.refusal, tested: report.tested,
    new_unsafe_passes: report.regression.new_unsafe_passes + report.cases.new_unsafe_passes,
    new_control_fails: report.regression.new_control_fails + report.cases.new_control_fails,
    newly_passed_right: report.regression.newly_passed_right,
    newly_failed_wrong: report.regression.newly_failed_wrong,
    touched: report.regression.touched + report.cases.touched,
    cases_changed: report.cases.changed.length, elapsed_ms: report.elapsed_ms,
  };
}

/** One line on what the gate found, for a notice. @param {GateSummary} g */
function gateSentence(g) {
  if (!g.accepted) return g.refusal || "The safety gate refused this lesson.";
  if (!g.tested) return "Not tested by the safety gate: no known claim uses this phrase or these words.";
  return `Safety gate: replayed on ${g.touched} known claim${g.touched === 1 ? "" : "s"}; no wrong explanation passes and no right one fails` +
    `; ${g.newly_passed_right} correct claim${g.newly_passed_right === 1 ? "" : "s"} newly pass` +
    `${g.newly_failed_wrong ? `, ${g.newly_failed_wrong} wrong one${g.newly_failed_wrong === 1 ? "" : "s"} newly fail` : ""}` +
    `${g.cases_changed ? `; ${g.cases_changed} of your recorded decisions change verdict` : ""}.`;
}

/**
 * Render a gate result into `target`: refused, untested or safe, always in words as well as colour.
 * @param {HTMLElement} target @param {GateSummary} g @param {VerdictChange} [claim]
 */
function showGate(target, g, claim) {
  const kind = !g.accepted ? "refused" : !g.tested ? "untested" : "safe";
  target.className = `gate ${kind}`;
  const label = { refused: "Gate refuses", untested: "Not tested", safe: "Gate: safe" }[kind];
  const detail = kind === "refused" ? (g.refusal || "")
    : kind === "untested" ? "no claim in the regression set or your recorded decisions uses this phrase or these words, so nothing known could catch a mistake. Check the transactions yourself."
    : gateSentence(g).replace(/^Safety gate: /, "");
  replace(target, h("strong", {}, label), ` · ${detail}`,
    claim && claim.before ? ` This claim: ${claim.before} → ${claim.after}.` : "",
    g.elapsed_ms ? h("span", { class: "muted" }, ` (${Math.round(g.elapsed_ms)} ms)`) : null);
}

async function refreshQueue() {
  el.queueRefresh.disabled = true;
  try {
    state.queue = /** @type {TeachQueue} */ (await api("/api/queue"));
    renderQueue();
  } catch (error) {
    replace(el.queue, h("li", { class: "empty" }, error instanceof Error ? error.message : String(error)));
  } finally {
    el.queueRefresh.disabled = false;
  }
}

function renderQueue() {
  const queue = state.queue;
  if (!queue) return;
  el.queueCount.textContent = queue.waiting ? `${queue.waiting} waiting` : "";
  if (!queue.items.length) {
    replace(el.queue, h("li", { class: "empty" },
      queue.runs ? "Nothing waits for a confirmation in the stored runs." :
        "Nothing waits yet. A claim joins this list when a model extractor's words are the only support for its reason; each such run is stored in the data directory."));
    return;
  }
  replace(el.queue, ...queue.items.map((item, index) => {
    const gate = h("div", { class: "gate" }, "Not previewed (outside the first rows).");
    if (item.impact) showGate(gate, item.impact);
    const counts = [
      `${item.waiting} waiting claim${item.waiting === 1 ? "" : "s"} use this phrase`,
      item.unlocks === null ? null : `${item.unlocks} would be decided by the rules`,
      `${item.runs} run${item.runs === 1 ? "" : "s"}`,
    ].filter(Boolean).join(" · ");
    return h("li", { class: "queue-item" },
      h("span", { class: "queue-rank num" }, `${index + 1}.`),
      h("div", { class: "queue-main" },
        h("p", { class: "queue-rule" }, `“${item.trigger}” → `, h("span", { class: "learned-terms" }, item.terms.join(", "))),
        h("p", { class: "hint" }, counts),
        gate),
      h("button", {
        type: "button", class: "button small", "aria-label": `Open the Teach form for “${item.trigger}”`,
        onclick: () => openQueued(item),
      }, "Open"));
  }));
}

/**
 * Open a queued lesson: load its stored run, re-check it, and select its claim with the Teach form filled in.
 * @param {QueueItem} item
 */
async function openQueued(item) {
  try {
    /** @type {PendingRun} */
    const run = await api(`/api/pending?key=${encodeURIComponent(item.example.key)}`);
    const scenarioId = run.scenario_id || state.scenario?.id || "showcase";
    await prepareScenario(scenarioId);
    if (!el.scenario.querySelector(`option[value="${CSS.escape(scenarioId)}"]`)) {
      el.scenario.append(h("option", { value: scenarioId }, `Stored run · ${scenarioId}`));
    }
    el.scenario.value = scenarioId;
    state.upload = run.ledger_csv ? { name: run.entity || "Uploaded ledger", text: run.ledger_csv } : null;
    el.editor.value = run.explanation;
    state.prefill = { quote: item.example.quote, triggers: [item.example.driver], terms: item.terms, item };
    state.lessonNotice = `Opened from Teach next: run ${run.run_id} (${run.extractor}), re-checked with the ${el.extractor.value} extractor. The claim's Teach form is filled in below.`;
    showView("review");
    if (!(await verify()) || !state.report) return;
    const found = state.report.claims.find((c) => c.claim.quote === item.example.quote);
    if (found) focusClaim(found.claim.claim_id);
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

// ── learned lexicon ──────────────────────────────────────────────────────

async function refreshLessons() {
  const data = /** @type {{entries: Lesson[]}} */ (await api("/api/lexicon"));
  state.lessons = data.entries;
  renderLessons();
}

function renderLessons() {
  el.lessonCount.textContent = state.lessons.length ? String(state.lessons.length) : "";
  if (!state.lessons.length) {
    replace(el.lessons, h("p", { class: "hint" }, "Nothing taught yet. Choose Wrong evidence, Misread sentence or Accept convention on a claim and give Proven the ledger words for its reason."));
    return;
  }
  replace(el.lessons, ...state.lessons.map((lesson) => h("div", { class: "lesson" },
    h("div", {},
      h("p", { class: "lesson-rule" }, `“${lesson.triggers.join("” or “")}” → ${lesson.terms.join(", ")}`),
      h("p", { class: "hint" }, `${lesson.created_at.replace("T", " ").replace(/\+.*$/, "")} UTC · from “${lesson.provenance.quote}” · ${lesson.provenance.note}`)),
    h("button", {
      type: "button", class: "button small", "aria-label": `Remove lesson ${lesson.terms.join(", ")}`,
      onclick: () => removeLesson(lesson.id),
    }, "Remove"))));
}

/** @param {string} id */
async function removeLesson(id) {
  try {
    await api("/api/lexicon/remove", { id });
    await refreshLessons();
    state.lessonNotice = "Lesson removed. Claims re-checked without it.";
    await verify();
    refreshQueue();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

/** @param {VerifyReport} report */
function renderUnextracted(report) {
  /** @type {Child[]} */
  const parts = [];
  if (report.unextracted.length) {
    parts.push(h("h3", {}, "Not extracted"),
      h("p", { class: "hint" }, "These sentences state a figure but yielded no checkable claim. They are counted, not hidden."),
      h("ul", { class: "unextracted-list" }, ...report.unextracted.map((s) => h("li", {}, s.text))));
  }
  if (report.rejected.length) {
    parts.push(h("h3", {}, "Rejected proposals"),
      h("p", { class: "hint" }, "The extractor proposed these, and the text did not support them."),
      h("ul", { class: "unextracted-list" }, ...report.rejected.map((r) => h("li", {}, `${r.reason.replace(/_/g, " ")}: ${r.quote}`))));
  }
  replace(el.unextracted, parts.length ? h("div", { class: "claim-section" }, ...parts) : null);
}

/** @param {string} id */
function focusClaim(id) {
  const report = state.report;
  if (!report) return;
  const result = report.claims.find((c) => c.claim.claim_id === id);
  if (result && result.verdict === "PASS") state.filter = "all";
  state.active = id;
  renderAnnotated(report);
  renderLedger(report);
  renderClaims(report);
  document.getElementById(`claim-${id}`)?.scrollIntoView({ block: "nearest" });
  // Stacked layout (narrow screens): the detail pane is below the list, so bring it into view.
  if (el.detail.getBoundingClientRect().top > window.innerHeight * 0.6) el.detail.scrollIntoView({ block: "start" });
}

// ── benchmark ────────────────────────────────────────────────────────────

const PHRASINGS = /** @type {const} */ (["seen", "heldout", "paraphrase"]);
const PHRASING_LABEL = { seen: "Seen phrasing", heldout: "Held-out phrasing", paraphrase: "Paraphrase" };

/** @param {string} extractor @param {string} phrasing */
const benchKey = (extractor, phrasing) => `${extractor}:${phrasing}`;

async function runBenchmark() {
  const n = Math.max(11, Math.min(2000, Number(el.benchN.value) || 440));
  const extractor = el.benchExtractor.value || "rules";
  el.benchRun.disabled = true;
  try {
    for (const phrasing of PHRASINGS) {
      el.benchMeta.textContent = `Running ${n} ${el.benchSplit.value} closes with ${extractor}, ${phrasing} phrasing…`;
      const started = performance.now();
      state.bench[benchKey(extractor, phrasing)] = await api("/api/benchmark", { split: el.benchSplit.value, n, phrasing, extractor });
      el.benchMeta.textContent = `${phrasing} done in ${Math.round(performance.now() - started)} ms`;
      renderBenchmark();
    }
    const first = state.bench[benchKey(extractor, "seen")];
    el.benchMeta.textContent = `${first.extractor} · ${first.scenarios} closes · ${first.claims} claims per phrasing · split ${first.split}`;
    showError(null);
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    el.benchRun.disabled = false;
  }
}

function renderBenchmark() {
  state.benchExtractor = el.benchExtractor.value || "rules";
  /** @type {[string, (b: Benchmark) => Child, string][]} */
  const metrics = [
    ["Controls passed", (b) => `${b.controls.passed} / ${b.controls.n}`, "correct explanations left alone"],
    ["Controls failed", (b) => b.controls.fails, "must be 0 — a FAIL on correct work"],
    ["Defects flagged", (b) => `${b.defects.flagged} / ${b.defects.n}`, "not passed: FAIL or REVIEW"],
    ["Defects meeting requirement", (b) => `${b.defects.caught} / ${b.defects.n}`, "FAIL where the family requires FAIL"],
    ["Unsafe PASS", (b) => b.defects.unsafe_passes, "must be 0 — a PASS on wrong work"],
    ["Decided without a person", (b) => rate(b.coverage.decided_share), "coverage, reported separately"],
    ["Mean reward", (b) => b.mean_reward.toFixed(3), "the training signal, in [-1, 1]"],
  ];
  /** @param {string} phrasing @returns {Benchmark | undefined} */
  const current = (phrasing) => state.bench[benchKey(state.benchExtractor, phrasing)];
  replace(el.benchSummary,
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Measure"),
      ...PHRASINGS.map((c) => h("th", { scope: "col", class: "num" }, PHRASING_LABEL[c])),
      h("th", { scope: "col" }, "Meaning"))),
    h("tbody", {}, ...metrics.map(([label, get, meaning]) => h("tr", {},
      h("th", { scope: "row" }, label),
      ...PHRASINGS.map((c) => {
        const bench = current(c);
        return h("td", { class: "num" }, bench ? get(bench) : "—");
      }),
      h("td", { class: "muted wrap" }, meaning)))));

  for (const button of document.querySelectorAll("[data-phrasing]")) {
    button.setAttribute("aria-pressed", String(button.getAttribute("data-phrasing") === state.benchPhrasing));
  }
  const bench = current(state.benchPhrasing);
  if (!bench) {
    replace(el.benchFamilies, h("tbody", {}, h("tr", {}, h("td", { class: "empty" }, "Run the benchmark to see per-family results."))));
    return;
  }
  /** @param {number | null} v */
  const opt = (v) => (v === null ? "—" : rate(v));
  replace(el.benchFamilies,
    h("thead", {}, h("tr", {}, ...["Family", "Type", "Requirement", "n", "Met", "Finding raised", "Evidence recall", "PASS", "FAIL", "REVIEW"]
      .map((label, i) => h("th", { scope: "col", class: i >= 3 ? "num" : null }, label)))),
    h("tbody", {}, ...bench.families.map((row) => h("tr", {},
      h("th", { scope: "row", class: "mono" }, row.family),
      h("td", {}, row.kind),
      h("td", {}, row.requirement === "NOT_PASS" ? "not PASS" : row.requirement),
      h("td", { class: "num" }, row.n),
      h("td", { class: `num${row.met_rate < 0.9 ? " low" : ""}` }, rate(row.met_rate)),
      h("td", { class: "num" }, opt(row.codes_rate)),
      h("td", { class: "num" }, opt(row.evidence_recall)),
      h("td", { class: "num" }, row.verdicts.PASS),
      h("td", { class: "num" }, row.verdicts.FAIL),
      h("td", { class: "num" }, row.verdicts.REVIEW)))));
}

// ── views and wiring ─────────────────────────────────────────────────────

/** @type {Record<string, string>} */
const VIEW_NAME = { review: "Review", ledger: "Ledger", learned: "Learned", benchmark: "Benchmark" };

/** @param {string} view */
function showView(view) {
  for (const tab of document.querySelectorAll(".tab")) {
    if (tab.getAttribute("data-view") === view) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
  for (const section of /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll(".view"))) {
    section.hidden = section.id !== `view-${view}`;
  }
  const name = VIEW_NAME[view] || VIEW_NAME.review;
  el.crumbView.textContent = name;
  document.title = `Proven · ${name}`;
  if (view === "benchmark" && !state.bench[benchKey(el.benchExtractor.value || "rules", "seen")]) runBenchmark();
}

function wire() {
  el.toolbar.addEventListener("submit", (e) => { e.preventDefault(); state.lessonNotice = null; verify(); });
  el.scenario.addEventListener("change", () => loadScenario(el.scenario.value).catch((e) => showError(String(e.message || e))));
  el.edit.addEventListener("click", () => setEditing(!state.editing));
  el.editor.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") verify(); });
  el.upload.addEventListener("change", async () => {
    const file = el.upload.files && el.upload.files[0];
    if (!file) return;
    state.upload = { name: file.name, text: await file.text() };
    verify();
  });
  for (const button of document.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => {
      state.filter = button.getAttribute("data-filter") === "all" ? "all" : "exceptions";
      if (state.report) renderClaims(state.report);
    });
  }
  for (const tab of document.querySelectorAll(".tab")) {
    tab.addEventListener("click", () => showView(tab.getAttribute("data-view") || "review"));
  }
  for (const tab of document.querySelectorAll("[data-pane]")) {
    tab.addEventListener("click", () => {
      const wanted = tab.getAttribute("data-pane");
      state.pane = wanted === "explanation" || wanted === "key" ? wanted : "claims";
      showPane();
    });
  }
  el.benchForm.addEventListener("submit", (e) => { e.preventDefault(); runBenchmark(); });
  for (const button of document.querySelectorAll("[data-phrasing]")) {
    button.addEventListener("click", () => {
      const wanted = button.getAttribute("data-phrasing");
      state.benchPhrasing = wanted === "heldout" || wanted === "paraphrase" ? wanted : "seen";
      renderBenchmark();
    });
  }
  el.benchExtractor.addEventListener("change", renderBenchmark);
  el.queueRefresh.addEventListener("click", () => { refreshQueue(); });
  el.extractor.addEventListener("change", updateExtractorUi);
  el.model.addEventListener("input", () => { state.models[el.extractor.value] = el.model.value; });
}

async function init() {
  wire();
  try {
    const [config, list] = await Promise.all([
      api("/api/config").then((c) => /** @type {Config} */ (c)),
      api("/api/scenarios").then((s) => /** @type {{scenarios: ScenarioRef[]}} */ (s)),
    ]);
    state.config = config;
    state.scenarios = list.scenarios;
    replace(el.status,
      "Network ", h("strong", {}, config.network.allowed ? "allowed" : "off"),
      config.network.guard_installed ? " (enforced)" : "", ` · v${config.version}`);
    replace(el.extractor, ...config.extractors.map((x) =>
      h("option", { value: x.id, disabled: !x.available, title: x.reason || null }, x.available ? x.label : `${x.label} — unavailable`)));
    replace(el.benchExtractor, ...config.benchmark_extractors.map((id) =>
      h("option", { value: id }, id === "oracle" ? "Oracle (generator's own claims)" : "Rules")));
    updateExtractorUi();
    replace(el.scenario,
      h("optgroup", { label: "Showcase" }, ...list.scenarios.filter((s) => s.kind === "showcase").map((s) => h("option", { value: s.id }, s.title))),
      h("optgroup", { label: "Hand-written example" }, ...list.scenarios.filter((s) => s.kind === "example").map((s) => h("option", { value: s.id }, s.title))),
      h("optgroup", { label: "Synthetic, held-out split" }, ...list.scenarios.filter((s) => s.kind === "synthetic").map((s) => h("option", { value: s.id }, `${s.title} (${s.id})`))));
    renderBenchmark();
    await refreshLessons();
    refreshQueue();
    await loadScenario(list.scenarios[0].id);
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

init();
