/**
 * Idea Enhancer — Frontend Controller & API Adapter
 *
 * - Follows the agreed POST /search contract (request: { idea, top_k }).
 * - Vanilla JS, safe DOM construction (no HTML injection from data).
 * - Demo scenarios use fixed fixtures and are always labelled as demo data.
 * - Every request is tracked: switching mode or starting a new search
 *   cancels/ignores any older in-flight request, so stale results never render.
 * - Internal retrieval scores and sub-ranks are never displayed; only the ordered rank number is.
 */

import { MOCK_SCENARIOS, cloneFixture } from './mockData.js';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const API_BASE_URL = String(
  (typeof window !== 'undefined' && window.IDEA_ENHANCER_API_BASE_URL) || 'http://localhost:8000'
).replace(/\/+$/, '');
const REQUEST_TIMEOUT_MS = 10000;
const MIN_IDEA_CHARS = 10;
const MAX_IDEA_CHARS = 2000;
const DEFAULT_TOP_K = 5;
const MIN_TOP_K = 1;
const MAX_TOP_K = 20;

const SOURCE_LABELS = {
  rvce: 'Institutional archive',
  global: 'Open dataset',
  institutional_project: 'Institutional project',
  open_source_repository: 'Open-source repository',
  research_paper: 'Research paper'
};

const VERIFICATION_LABELS = {
  checked: { text: 'Text overlap found', tone: 'ok' },
  insufficient: { text: 'No shared terms found', tone: 'warn' }
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let activeRequest = null;   // { id, controller, mode, timedOut, cancelled }
let requestCounter = 0;
let cardSeq = 0;
let liveStatus = 'idle';    // 'idle' | 'ok' | 'failed' — only meaningful in live mode

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);

const searchForm = $('search-form');
const ideaInput = $('idea-input');
const topKInput = $('top-k-input');
const charCountDisplay = $('char-count');
const submitBtn = $('submit-btn');
const submitBtnText = $('submit-btn-text');
const submitBtnSpinner = $('submit-btn-spinner');
const submitBtnIcon = $('submit-btn-icon');

const themeToggle = $('theme-toggle');
const dataSourceSelect = $('data-source-select');
const headerModeDot = $('header-mode-dot');
const modeStatusPill = $('mode-status-pill');
const modeStatusText = $('mode-status-text');
const mockNoticeBanner = $('mock-notice-banner');
const mockFixtureQuery = $('mock-fixture-query');

const clientValidationError = $('client-validation-error');
const clientValidationText = $('client-validation-text');
const loadingSkeleton = $('loading-skeleton');
const errorBanner = $('error-banner');
const errorMessageEl = $('error-message');
const warningsContainer = $('warnings-container');
const warningsList = $('warnings-list');

const resultsContainer = $('results-container');
const resultsSummary = $('results-summary');
const resultsQuery = $('results-query');
const matchesList = $('matches-list');
const noMatchesBanner = $('no-matches-banner');
const noMatchesMessage = $('no-matches-message');

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function nonEmptyString(v) {
  return typeof v === 'string' && v.trim().length > 0;
}

function isHttpUrl(value) {
  if (typeof value !== 'string') return false;
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch (_) {
    return false;
  }
}

function currentMode() {
  return dataSourceSelect ? dataSourceSelect.value : 'mock-success';
}

function isMockMode(mode) {
  return typeof mode === 'string' && mode.startsWith('mock-');
}

class SearchError extends Error {
  constructor(message, kind, status) {
    super(message);
    this.name = 'SearchError';
    this.kind = kind;       // 'validation' | 'server' | 'unavailable' | 'timeout' | 'network' | 'malformed' | 'http'
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------
function applyTheme(theme, persist = false) {
  const dark = theme === 'dark';
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  if (themeToggle) {
    themeToggle.setAttribute('aria-pressed', String(dark));
    themeToggle.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
  }
  if (persist) {
    try { localStorage.setItem('idea-enhancer-theme', dark ? 'dark' : 'light'); } catch (_) {}
  }
}

function initTheme() {
  const initialTheme = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
  applyTheme(initialTheme);
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      applyTheme(nextTheme, true);
    });
  }
}

function init() {
  initTheme();
  ideaInput.addEventListener('input', updateCharCount);
  updateCharCount();

  searchForm.addEventListener('submit', handleFormSubmit);
  dataSourceSelect.addEventListener('change', handleModeChange);
  updateModeIndicators();

  const editIdeaBtn = $('edit-idea-btn');
  if (editIdeaBtn) {
    editIdeaBtn.addEventListener('click', () => {
      ideaInput.focus();
      const end = ideaInput.value.length;
      try { ideaInput.setSelectionRange(end, end); } catch (_) { /* not supported: ignore */ }
    });
  }

  const samples = [
    ['sample-idea-1', 'An IoT-based crop disease detection system using Raspberry Pi and CNNs to monitor foliar infections in real time.'],
    ['sample-idea-2', 'A quantum teleportation device for household pets using acoustic levitation and subatomic resonant harmonic feedback.']
  ];
  samples.forEach(([id, text]) => {
    const btn = $(id);
    if (!btn) return;
    btn.addEventListener('click', () => {
      ideaInput.value = text;
      updateCharCount();
      clearFeedback();
      ideaInput.focus();
    });
  });
}

// ---------------------------------------------------------------------------
// Character counter (counts the trimmed text, which is what gets validated/sent)
// ---------------------------------------------------------------------------
function updateCharCount() {
  const len = ideaInput.value.trim().length;
  charCountDisplay.textContent = `${len} / ${MAX_IDEA_CHARS} characters`;

  let tone = 'text-slate-500';
  if (len > MAX_IDEA_CHARS) tone = 'text-rose-700 font-bold';
  else if (len > 0 && len < MIN_IDEA_CHARS) tone = 'text-amber-700 font-semibold';
  charCountDisplay.className = `text-xs font-medium ${tone}`;
}

// ---------------------------------------------------------------------------
// Mode indicators (header dot, status pill, demo banner)
// ---------------------------------------------------------------------------
const PILL_BASE = 'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border shrink-0';
const TONES = {
  amber:  { pill: 'bg-amber-50 text-amber-900 border-amber-300',     dot: 'bg-amber-500' },
  indigo: { pill: 'bg-indigo-50 text-indigo-900 border-indigo-200',  dot: 'bg-indigo-500' },
  green:  { pill: 'bg-emerald-50 text-emerald-900 border-emerald-300', dot: 'bg-emerald-600' },
  rose:   { pill: 'bg-rose-50 text-rose-900 border-rose-200',        dot: 'bg-rose-500' }
};

function updateModeIndicators() {
  const mode = currentMode();
  let tone = TONES.amber;
  let text = 'Demo data — not real results';

  if (!isMockMode(mode)) {
    if (liveStatus === 'ok') {
      tone = TONES.green;
      text = 'Live search — results from the backend';
    } else if (liveStatus === 'failed') {
      tone = TONES.rose;
      text = 'Live search — last request failed';
    } else {
      tone = TONES.indigo;
      text = 'Live search selected — not yet contacted';
    }
  }

  modeStatusPill.className = `${PILL_BASE} ${tone.pill}`;
  if (modeStatusPill.firstElementChild) {
    modeStatusPill.firstElementChild.className = `w-2 h-2 rounded-full ${tone.dot}`;
    modeStatusPill.firstElementChild.setAttribute('aria-hidden', 'true');
  }
  modeStatusText.textContent = text;
  if (headerModeDot) headerModeDot.className = `w-2 h-2 rounded-full ${tone.dot}`;
}

/**
 * Switching mode cancels any in-flight request and discards everything that
 * was on screen, so results from one mode can never appear under another.
 */
function handleModeChange() {
  cancelActiveRequest();
  liveStatus = 'idle';
  clearFeedback();
  clearResults();
  setLoadingState(false);
  updateModeIndicators();
}

function cancelActiveRequest() {
  if (!activeRequest) return;
  activeRequest.cancelled = true;
  activeRequest.controller.abort();
  activeRequest = null;
}

// ---------------------------------------------------------------------------
// Clearing UI state
// ---------------------------------------------------------------------------
function clearFeedback() {
  clientValidationError.classList.add('hidden');
  clientValidationText.textContent = '';
  errorBanner.classList.add('hidden');
  errorMessageEl.textContent = '';
  warningsContainer.classList.add('hidden');
  warningsList.replaceChildren();
}

function clearResults() {
  resultsContainer.classList.add('hidden');
  matchesList.replaceChildren();
  noMatchesBanner.classList.add('hidden');
  noMatchesMessage.textContent = '';
  resultsQuery.classList.add('hidden');
  resultsQuery.textContent = '';
  mockNoticeBanner.classList.add('hidden');
  mockFixtureQuery.textContent = '';
  resultsSummary.textContent = 'Search results';
}

function showClientValidationError(message) {
  clientValidationText.textContent = message;
  clientValidationError.classList.remove('hidden');
}

function showErrorBanner(message) {
  errorMessageEl.textContent = message;
  errorBanner.classList.remove('hidden');
  errorBanner.scrollIntoView({ block: 'nearest' });
}

function showWarnings(list) {
  warningsList.replaceChildren();
  const items = list.filter(nonEmptyString);
  if (items.length === 0) {
    warningsContainer.classList.add('hidden');
    return;
  }
  items.forEach((text) => warningsList.appendChild(el('li', null, text)));
  warningsContainer.classList.remove('hidden');
}

function setLoadingState(loading) {
  submitBtn.disabled = loading;
  searchForm.setAttribute('aria-busy', loading ? 'true' : 'false');
  loadingSkeleton.setAttribute('aria-busy', loading ? 'true' : 'false');
  submitBtnText.textContent = loading ? 'Investigating…' : 'Investigate idea';
  submitBtnSpinner.classList.toggle('hidden', !loading);
  if (submitBtnIcon) submitBtnIcon.classList.toggle('hidden', loading);
  loadingSkeleton.classList.toggle('hidden', !loading);
}

// ---------------------------------------------------------------------------
// top_k handling
// ---------------------------------------------------------------------------
function normalizeTopK(raw) {
  const text = String(raw ?? '').trim();
  const n = text === '' ? NaN : Number(text);

  if (!Number.isFinite(n)) {
    return { value: DEFAULT_TOP_K, notice: `The number of matches was not a valid number, so the default of ${DEFAULT_TOP_K} was used.` };
  }
  let value = n;
  let notice = null;
  if (!Number.isInteger(value)) {
    value = Math.floor(value);
    notice = `The number of matches must be a whole number, so it was rounded down to ${Math.max(value, MIN_TOP_K)}.`;
  }
  if (value < MIN_TOP_K) {
    value = MIN_TOP_K;
    notice = `The number of matches was raised to the minimum of ${MIN_TOP_K}.`;
  } else if (value > MAX_TOP_K) {
    value = MAX_TOP_K;
    notice = `The number of matches was lowered to the maximum of ${MAX_TOP_K}.`;
  }
  return { value, notice };
}

// ---------------------------------------------------------------------------
// Submit flow
// ---------------------------------------------------------------------------
async function handleFormSubmit(event) {
  event.preventDefault();
  if (activeRequest) return;

  const mode = currentMode();
  clearFeedback();
  clearResults();

  const idea = ideaInput.value.trim();

  // Demo error scenarios replay a fixed error regardless of the typed idea,
  // so they are exempt from client-side length checks (otherwise unreachable).
  const replaysFixedError = mode === 'mock-val-error' || mode === 'mock-server-error';

  if (!replaysFixedError) {
    if (idea.length < MIN_IDEA_CHARS) {
      showClientValidationError(`Your description needs at least ${MIN_IDEA_CHARS} characters (currently ${idea.length}).`);
      ideaInput.focus();
      return;
    }
    if (idea.length > MAX_IDEA_CHARS) {
      showClientValidationError(`Your description must not exceed ${MAX_IDEA_CHARS} characters (currently ${idea.length}).`);
      ideaInput.focus();
      return;
    }
  }

  const { value: topK, notice: topKNotice } = normalizeTopK(topKInput.value);
  topKInput.value = String(topK);
  const clientNotices = topKNotice ? [topKNotice] : [];

  const req = {
    id: ++requestCounter,
    mode,
    controller: new AbortController(),
    timedOut: false,
    cancelled: false
  };
  activeRequest = req;
  setLoadingState(true);

  try {
    const data = await fetchSearch(req, idea, topK);
    if (req.cancelled || activeRequest !== req) return;

    const parsed = parseSuccessPayload(data, topK);
    if (!isMockMode(mode)) liveStatus = 'ok';
    renderSuccess(parsed, { mode, idea, topK, clientNotices });
  } catch (error) {
    if (req.cancelled || activeRequest !== req) return;
    if (!isMockMode(mode)) liveStatus = 'failed';
    clearResults();
    showWarnings(clientNotices);
    showErrorBanner(describeError(error));
  } finally {
    if (activeRequest === req) {
      activeRequest = null;
      setLoadingState(false);
      updateModeIndicators();
    }
  }
}

// ---------------------------------------------------------------------------
// API adapter: POST /search (live) or fixed demo scenario
// ---------------------------------------------------------------------------
function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const t = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(t);
      reject(new DOMException('Aborted', 'AbortError'));
    }
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

async function fetchSearch(req, idea, topK) {
  const scenario = MOCK_SCENARIOS[req.mode];

  if (scenario) {
    await delay(scenario.delay, req.controller.signal);
    const payload = cloneFixture(scenario.payload);
    if (scenario.kind === 'error') {
      throw errorFromResponse(scenario.status, payload);
    }
    return payload;
  }

  if (req.mode !== 'live') {
    throw new SearchError('Unknown search mode selected.', 'malformed');
  }

  const timer = setTimeout(() => {
    req.timedOut = true;
    req.controller.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    let res;
    try {
      res = await fetch(`${API_BASE_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ idea, top_k: topK }),
        signal: req.controller.signal
      });
    } catch (err) {
      if (err && err.name === 'AbortError') {
        if (req.timedOut) throw new SearchError('timeout', 'timeout');
        throw err; // cancelled by the user (mode switch)
      }
      throw new SearchError('network', 'network');
    }

    // Keep the timeout armed while the body downloads.
    let data = null;
    try {
      const text = await res.text();
      data = text ? JSON.parse(text) : null;
    } catch (err) {
      if (err && err.name === 'AbortError') {
        if (req.timedOut) throw new SearchError('timeout', 'timeout');
        throw err;
      }
      data = null; // non-JSON body
    }

    if (!res.ok) throw errorFromResponse(res.status, data);
    return data;
  } finally {
    clearTimeout(timer);
  }
}

function extractServerMessage(data) {
  if (!isPlainObject(data)) return null;
  if (nonEmptyString(data.message)) return data.message.trim();
  // FastAPI default validation shape: { detail: [{ msg, loc }] } or { detail: "..." }
  if (nonEmptyString(data.detail)) return data.detail.trim();
  if (Array.isArray(data.detail)) {
    const msgs = data.detail
      .map((d) => (isPlainObject(d) && nonEmptyString(d.msg) ? d.msg.trim() : null))
      .filter(Boolean);
    if (msgs.length) return msgs.join(' ');
  }
  return null;
}

function errorFromResponse(status, data) {
  const serverMessage = extractServerMessage(data);

  if (status === 400 || status === 422) {
    return new SearchError(serverMessage || 'The server rejected the submitted idea. Please check it and try again.', 'validation', status);
  }
  if (status === 404) {
    return new SearchError('The search service could not be found at the configured address.', 'http', status);
  }
  if (status === 429) {
    return new SearchError('Too many requests were sent. Please wait a moment and try again.', 'http', status);
  }
  if (status === 503) {
    return new SearchError('The search service is temporarily unavailable or its index is not ready. Please try again shortly.', 'unavailable', status);
  }
  if (status === 502 || status === 504) {
    return new SearchError('The search service could not be reached by its gateway. Please try again shortly.', 'unavailable', status);
  }
  if (status >= 500) {
    return new SearchError('The search service ran into an internal error. Please try again.', 'server', status);
  }
  if (status >= 400) {
    return new SearchError(serverMessage || `The request was rejected (HTTP ${status}).`, 'http', status);
  }
  return new SearchError(`Unexpected response (HTTP ${status}).`, 'malformed', status);
}

function describeError(error) {
  if (error instanceof SearchError) {
    switch (error.kind) {
      case 'timeout':
        return `The search took longer than ${REQUEST_TIMEOUT_MS / 1000} seconds and was stopped. Please try again.`;
      case 'network':
        return 'Unable to reach the search service. Check your connection and that the backend is running, or switch to a demo mode to explore the interface.';
      case 'malformed':
        return error.message || 'The search service returned a response this page could not understand.';
      default:
        return error.message;
    }
  }
  return 'Something unexpected went wrong while searching. Please try again.';
}

// ---------------------------------------------------------------------------
// Response validation
// ---------------------------------------------------------------------------
function parseSuccessPayload(data, topK) {
  if (!isPlainObject(data)) {
    throw new SearchError('The search service returned an empty or unreadable response.', 'malformed');
  }
  if (data.status === 'error') {
    throw new SearchError(extractServerMessage(data) || 'The search service reported an error.', 'server');
  }
  if (data.status !== 'success') {
    throw new SearchError('The search service returned a response in an unexpected format.', 'malformed');
  }
  const bad = () => new SearchError('The search service returned results in an unexpected format.', 'malformed');

  // Required success-envelope fields: query, result_count, matches, warnings (message: string|null).
  if (typeof data.query !== 'string') throw bad();
  if (!Array.isArray(data.matches)) throw bad();
  if (!Number.isInteger(data.result_count) || data.result_count < 0) throw bad();
  // Checked against the raw match list, before any client-side filtering or top_k trimming.
  if (data.result_count !== data.matches.length) throw bad();
  if (!Array.isArray(data.warnings) || !data.warnings.every((w) => typeof w === 'string')) throw bad();
  if (data.message !== null && data.message !== undefined && typeof data.message !== 'string') throw bad();

  const notices = [];
  const usable = data.matches.filter(
    (m) => isPlainObject(m) && (nonEmptyString(m.title) || nonEmptyString(m.description_excerpt))
  );

  if (data.matches.length > 0 && usable.length === 0) {
    throw new SearchError('The search service returned results in an unexpected format.', 'malformed');
  }
  const skipped = data.matches.length - usable.length;
  if (skipped > 0) {
    notices.push(skipped === 1 ? '1 incomplete result could not be displayed.' : `${skipped} incomplete results could not be displayed.`);
  }

  let matches = usable;
  if (matches.length > topK) {
    matches = matches.slice(0, topK);
    notices.push(`The service returned more results than requested; showing the top ${topK}.`);
  }

  const serverWarnings = data.warnings.filter(nonEmptyString);

  return {
    matches,
    message: nonEmptyString(data.message) ? data.message.trim() : null,
    warnings: [...notices, ...serverWarnings],
    fixtureQuery: nonEmptyString(data.query) ? data.query : null
  };
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function renderSuccess(parsed, { mode, idea, clientNotices }) {
  const isMock = isMockMode(mode);

  showWarnings([...clientNotices, ...parsed.warnings]);

  if (isMock) {
    mockFixtureQuery.textContent = parsed.fixtureQuery ? `Sample idea in this fixture: “${parsed.fixtureQuery}”.` : '';
    mockNoticeBanner.classList.remove('hidden');
    resultsQuery.classList.add('hidden');
  } else {
    mockNoticeBanner.classList.add('hidden');
    const shown = idea.length > 160 ? `${idea.slice(0, 157)}…` : idea;
    resultsQuery.textContent = `Results for: “${shown}”`;
    resultsQuery.classList.remove('hidden');
  }

  const count = parsed.matches.length;
  matchesList.replaceChildren();

  if (count === 0) {
    resultsSummary.textContent = 'No close matches found';
    noMatchesMessage.textContent = parsed.message || 'No close match was found in the available dataset.';
    noMatchesBanner.classList.remove('hidden');
  } else {
    noMatchesBanner.classList.add('hidden');
    resultsSummary.textContent = `${count} similar project${count === 1 ? '' : 's'} found`;
    parsed.matches.forEach((m, i) => matchesList.appendChild(buildMatchCard(m, i, isMock)));
  }

  resultsContainer.classList.remove('hidden');
  resultsSummary.focus({ preventScroll: false });
}

function buildBadge(label, tone) {
  const tones = {
    ok:      ['bg-emerald-50 text-emerald-900 border-emerald-300', 'bg-emerald-600'],
    warn:    ['bg-amber-50 text-amber-900 border-amber-300', 'bg-amber-500'],
    neutral: ['bg-slate-50 text-slate-800 border-slate-300', 'bg-slate-500']
  };
  const [classes, dotClass] = tones[tone] || tones.neutral;
  const badge = el('span', `inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-full border ${classes}`);
  const dot = el('span', `w-1.5 h-1.5 rounded-full ${dotClass}`);
  dot.setAttribute('aria-hidden', 'true');
  badge.appendChild(dot);
  badge.appendChild(document.createTextNode(label));
  return badge;
}

function buildTagSection(label, items, tagClass) {
  const clean = items.map((t) => (typeof t === 'string' ? t.trim() : t == null ? '' : String(t))).filter(Boolean);
  if (clean.length === 0) return null;
  const section = el('div', 'flex flex-col gap-1.5');
  section.appendChild(el('span', 'text-xs font-bold text-slate-700 uppercase tracking-wider', label));
  const row = el('ul', 'flex flex-wrap gap-1.5 list-none p-0 m-0');
  clean.forEach((t) => {
    const li = el('li', `${tagClass} px-2.5 py-0.5 rounded-lg text-xs sm:text-sm font-medium break-words max-w-full`, t);
    row.appendChild(li);
  });
  section.appendChild(row);
  return section;
}

function buildMatchCard(match, index, isMock) {
  const card = el('li', 'surface-card rounded-2xl p-5 sm:p-6 bg-white flex flex-col gap-4 animate-fade-in-up min-w-0');

  // Header: rank, title, meta, verification
  const header = el('div', 'flex flex-col sm:flex-row sm:items-start justify-between gap-3');
  const titleGroup = el('div', 'flex items-start gap-3 min-w-0 flex-1');

  const rankNum = typeof match.rank === 'number' && Number.isFinite(match.rank) ? match.rank : index + 1;
  const rankBadge = el('span', 'inline-flex items-center justify-center min-w-[2.5rem] px-2.5 py-1 text-sm font-bold rounded-xl bg-indigo-50 text-indigo-800 border border-indigo-200 shrink-0', `#${rankNum}`);
  rankBadge.setAttribute('aria-label', `Rank ${rankNum}`);

  const titleBox = el('div', 'min-w-0');
  titleBox.appendChild(el('h3', 'text-lg sm:text-xl font-bold text-slate-900 leading-snug tracking-tight break-words', nonEmptyString(match.title) ? match.title.trim() : 'Untitled project record'));

  const meta = el('div', 'flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-sm text-slate-600');
  if (!isMock && nonEmptyString(match.source_type)) {
    const label = SOURCE_LABELS[match.source_type] || match.source_type;
    meta.appendChild(el('span', 'font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded text-xs border border-slate-300', label));
  }
  if (nonEmptyString(match.domain)) meta.appendChild(el('span', 'font-medium', match.domain));
  if (typeof match.year === 'number' && Number.isFinite(match.year)) meta.appendChild(el('span', null, String(match.year)));
  // Add separators visually via gap only; keep reading order simple for screen readers.
  titleBox.appendChild(meta);

  titleGroup.appendChild(rankBadge);
  titleGroup.appendChild(titleBox);

  const status = VERIFICATION_LABELS[match.verification_status];
  const statusWrap = el('div', 'shrink-0');
  if (isMock) {
    statusWrap.appendChild(buildBadge('Illustrative demo record', 'neutral'));
  } else {
    statusWrap.appendChild(status ? buildBadge(status.text, status.tone) : buildBadge('Not verified', 'neutral'));
  }

  header.appendChild(titleGroup);
  header.appendChild(statusWrap);
  card.appendChild(header);

  // Excerpt
  if (nonEmptyString(match.description_excerpt)) {
    const excerpt = el('div', 'bg-[#FAF9F5] border-l-4 border-indigo-400 p-3.5 sm:p-4 rounded-r-xl');
    excerpt.appendChild(el('p', 'text-sm sm:text-base text-slate-800 leading-relaxed break-words', match.description_excerpt.trim()));
    card.appendChild(excerpt);
  }

  // Shared concepts stay visible: they are the quickest way to see why a record is related.
  const shared = Array.isArray(match.shared_elements)
    ? buildTagSection('Shared concepts', match.shared_elements, 'bg-amber-50 text-amber-900 border border-amber-300')
    : null;
  if (shared) card.appendChild(shared);

  // Secondary information (technologies, source) sits behind a disclosure control.
  const detailsId = `match-details-${++cardSeq}`;
  const details = el('div', 'flex flex-col gap-3 pt-3 border-t border-slate-200 text-sm');

  const tech = Array.isArray(match.technologies)
    ? buildTagSection('Technologies', match.technologies, 'bg-slate-100 text-slate-800 border border-slate-300')
    : null;
  if (tech) {
    details.appendChild(tech);
  }

  const sourceRow = el('div', 'flex flex-col gap-1');
  sourceRow.appendChild(el('span', 'text-xs font-bold text-slate-700 uppercase tracking-wider', 'Source'));
  const sourceVal = el('div', 'text-slate-800');
  if (isMock) {
    sourceVal.appendChild(el('span', 'italic text-slate-700', 'Illustrative demo record — not a real source and not verified.'));
  } else {
    const label = nonEmptyString(match.source_type) ? (SOURCE_LABELS[match.source_type] || match.source_type) : null;
    if (label) sourceVal.appendChild(el('span', 'font-medium mr-3', label));
    if (isHttpUrl(match.source_url)) {
      const link = el('a', 'inline-flex items-center gap-1 text-indigo-700 hover:text-indigo-900 underline underline-offset-2 font-semibold break-all', 'Open source URL');
      link.href = match.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.appendChild(el('span', 'sr-only', ' (opens in a new tab)'));
      const arrow = el('span', null, '↗');
      arrow.setAttribute('aria-hidden', 'true');
      link.appendChild(arrow);
      sourceVal.appendChild(link);
    } else {
      sourceVal.appendChild(el('span', 'italic text-slate-600', 'No public source link available'));
    }
  }
  sourceRow.appendChild(sourceVal);
  details.appendChild(sourceRow);

  const panel = el('div');
  panel.id = detailsId;
  panel.hidden = true;
  panel.appendChild(details);

  const toggle = el('button', 'self-start inline-flex items-center gap-1.5 px-3 py-1.5 -ml-1 rounded-lg text-sm font-semibold text-indigo-700 hover:bg-indigo-50 border border-transparent hover:border-indigo-200');
  toggle.type = 'button';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-controls', detailsId);
  const toggleText = el('span', null, 'Show details');
  const toggleHint = el('span', 'sr-only', ` for ${nonEmptyString(match.title) ? match.title.trim() : 'this record'}`);
  const chevron = el('span', 'inline-block transition-transform', '▾');
  chevron.setAttribute('aria-hidden', 'true');
  toggle.append(toggleText, toggleHint, chevron);
  toggle.addEventListener('click', () => {
    const expanded = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!expanded));
    panel.hidden = expanded;
    toggleText.textContent = expanded ? 'Show details' : 'Hide details';
    chevron.style.transform = expanded ? '' : 'rotate(180deg)';
  });

  card.appendChild(toggle);
  card.appendChild(panel);
  return card;
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
