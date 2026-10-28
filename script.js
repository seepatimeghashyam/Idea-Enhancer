/**
 * Idea Enhancer — Frontend Controller & API Adapter
 * 
 * Features:
 * - Full compliance with docs/API_CONTRACT.md
 * - Light-themed research workspace with safe DOM construction
 * - Robust input validation (10–2000 chars, trimmed whitespace)
 * - Anti-duplicate submission locks and accessible loading states
 * - Dual mode: Contract-matching Mock Demos vs Live FastAPI backend
 * - Strictly represents RRF score as a ranking metric, never a percentage
 */

import {
  MOCK_SUCCESS_RESPONSE,
  MOCK_NO_MATCH_RESPONSE,
  MOCK_VALIDATION_ERROR_RESPONSE,
  MOCK_SERVER_ERROR_RESPONSE
} from './mockData.js';

// Configuration constants
const DEFAULT_API_BASE_URL = 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 10000;
const MIN_IDEA_CHARS = 10;
const MAX_IDEA_CHARS = 2000;

// Application state
let isSubmitting = false;

// DOM Elements
const searchForm = document.getElementById('search-form');
const ideaInput = document.getElementById('idea-input');
const topKInput = document.getElementById('top-k-input');
const charCountDisplay = document.getElementById('char-count');
const submitBtn = document.getElementById('submit-btn');
const submitBtnText = document.getElementById('submit-btn-text');
const submitBtnSpinner = document.getElementById('submit-btn-spinner');
const submitBtnIcon = document.getElementById('submit-btn-icon');

// Mode Selector & Status Indicators
const dataSourceSelect = document.getElementById('data-source-select');
const modeStatusPill = document.getElementById('mode-status-pill');
const modeStatusText = document.getElementById('mode-status-text');
const mockNoticeBanner = document.getElementById('mock-notice-banner');

// Feedback & Results Elements
const clientValidationError = document.getElementById('client-validation-error');
const clientValidationText = document.getElementById('client-validation-text');
const loadingSkeleton = document.getElementById('loading-skeleton');
const errorBanner = document.getElementById('error-banner');
const errorMessageEl = document.getElementById('error-message');
const warningsContainer = document.getElementById('warnings-container');
const warningsList = document.getElementById('warnings-list');

const resultsContainer = document.getElementById('results-container');
const resultsSummary = document.getElementById('results-summary');
const matchesList = document.getElementById('matches-list');
const noMatchesBanner = document.getElementById('no-matches-banner');
const noMatchesMessage = document.getElementById('no-matches-message');

// Sample Idea Quick Fill Buttons
const sampleIdeaBtn1 = document.getElementById('sample-idea-1');
const sampleIdeaBtn2 = document.getElementById('sample-idea-2');

/**
 * Initialize event listeners on page load
 */
function init() {
  if (ideaInput) {
    ideaInput.addEventListener('input', updateCharCount);
    updateCharCount();
  }

  if (searchForm) {
    searchForm.addEventListener('submit', handleFormSubmit);
  }

  if (dataSourceSelect) {
    dataSourceSelect.addEventListener('change', updateModeStatusDisplay);
    updateModeStatusDisplay();
  }

  if (sampleIdeaBtn1) {
    sampleIdeaBtn1.addEventListener('click', () => {
      ideaInput.value = 'An IoT-based crop disease detection system using Raspberry Pi and CNNs to monitor foliar infections in real time.';
      updateCharCount();
      clearFeedback();
      ideaInput.focus();
    });
  }

  if (sampleIdeaBtn2) {
    sampleIdeaBtn2.addEventListener('click', () => {
      ideaInput.value = 'A quantum teleportation device for household pets using acoustic levitation and subatomic resonant harmonic feedback.';
      updateCharCount();
      clearFeedback();
      ideaInput.focus();
    });
  }
}

/**
 * Update real-time character count and visual indicators
 */
function updateCharCount() {
  const currentLength = ideaInput.value.length;
  charCountDisplay.textContent = `${currentLength} / ${MAX_IDEA_CHARS} characters`;

  if (currentLength > MAX_IDEA_CHARS) {
    charCountDisplay.className = 'text-xs font-bold text-rose-600';
  } else if (currentLength > 0 && currentLength < MIN_IDEA_CHARS) {
    charCountDisplay.className = 'text-xs font-semibold text-amber-600';
  } else {
    charCountDisplay.className = 'text-xs font-medium text-slate-400';
  }
}

/**
 * Synchronize the mode pill indicator with the selected source option
 */
function updateModeStatusDisplay() {
  const mode = dataSourceSelect ? dataSourceSelect.value : 'mock-success';

  if (mode === 'live') {
    modeStatusPill.className = 'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 shrink-0';
    modeStatusPill.firstElementChild.className = 'w-2 h-2 rounded-full bg-emerald-500 animate-pulse';
    modeStatusText.textContent = 'Live Backend Active';
    if (mockNoticeBanner) {
      mockNoticeBanner.classList.add('hidden');
    }
  } else {
    modeStatusPill.className = 'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 shrink-0';
    modeStatusPill.firstElementChild.className = 'w-2 h-2 rounded-full bg-amber-500';
    modeStatusText.textContent = 'Demo Fixture Active';
  }
}

/**
 * Clear existing feedback, errors, and warnings
 */
function clearFeedback() {
  clientValidationError.classList.add('hidden');
  clientValidationText.textContent = '';
  errorBanner.classList.add('hidden');
  errorMessageEl.textContent = '';
  noMatchesBanner.classList.add('hidden');
  warningsContainer.classList.add('hidden');
  warningsList.innerHTML = '';
}

/**
 * Main form submission handler with validation guards and lockouts
 */
async function handleFormSubmit(event) {
  event.preventDefault();

  if (isSubmitting) {
    return;
  }

  clearFeedback();

  // 1. Client-side input validation
  const rawIdea = ideaInput.value;
  const trimmedIdea = rawIdea.trim();

  if (trimmedIdea.length < MIN_IDEA_CHARS) {
    showClientValidationError(`Proposal description must contain at least ${MIN_IDEA_CHARS} characters (currently ${trimmedIdea.length}).`);
    ideaInput.focus();
    return;
  }

  if (trimmedIdea.length > MAX_IDEA_CHARS) {
    showClientValidationError(`Proposal description must not exceed ${MAX_IDEA_CHARS} characters (currently ${trimmedIdea.length}).`);
    ideaInput.focus();
    return;
  }

  // 2. Validate top_k parameter
  let topK = parseInt(topKInput.value, 10);
  if (isNaN(topK) || topK < 1) {
    topK = 5;
    topKInput.value = '5';
  } else if (topK > 20) {
    topK = 20;
    topKInput.value = '20';
  }

  // 3. Set loading state to prevent duplicate submissions
  setLoadingState(true);

  try {
    const selectedMode = dataSourceSelect ? dataSourceSelect.value : 'live';
    const response = await fetchSearch(trimmedIdea, topK, selectedMode);
    handleSearchResponse(response, selectedMode);
  } catch (error) {
    handleSearchError(error);
  } finally {
    setLoadingState(false);
  }
}

/**
 * Show inline client validation error
 */
function showClientValidationError(message) {
  clientValidationText.textContent = message;
  clientValidationError.classList.remove('hidden');
}

/**
 * Toggle the loading state, updating button and skeleton visibility
 */
function setLoadingState(loading) {
  isSubmitting = loading;
  submitBtn.disabled = loading;

  if (loading) {
    submitBtnText.textContent = 'Investigating…';
    submitBtnSpinner.classList.remove('hidden');
    if (submitBtnIcon) submitBtnIcon.classList.add('hidden');
    loadingSkeleton.classList.remove('hidden');
    resultsContainer.classList.add('hidden');
  } else {
    submitBtnText.textContent = 'Investigate Idea';
    submitBtnSpinner.classList.add('hidden');
    if (submitBtnIcon) submitBtnIcon.classList.remove('hidden');
    loadingSkeleton.classList.add('hidden');
  }
}

/**
 * API Adapter: executes live POST /search or returns mock scenario
 */
async function fetchSearch(idea, topK, mode) {
  // Scenario A: Mock Matches Found
  if (mode === 'mock-success') {
    await simulateDelay(600);
    return { ...MOCK_SUCCESS_RESPONSE, query: idea };
  }

  // Scenario B: Mock Zero Matches Found
  if (mode === 'mock-no-match') {
    await simulateDelay(600);
    return { ...MOCK_NO_MATCH_RESPONSE, query: idea };
  }

  // Scenario C: Mock Validation Error (422)
  if (mode === 'mock-val-error') {
    await simulateDelay(400);
    const err = new Error(MOCK_VALIDATION_ERROR_RESPONSE.message);
    err.status = 422;
    err.errorData = MOCK_VALIDATION_ERROR_RESPONSE;
    throw err;
  }

  // Scenario D: Mock Server Error (500)
  if (mode === 'mock-server-error') {
    await simulateDelay(400);
    const err = new Error(MOCK_SERVER_ERROR_RESPONSE.message);
    err.status = 500;
    err.errorData = MOCK_SERVER_ERROR_RESPONSE;
    throw err;
  }

  // Live Backend Call: POST /search
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(`${DEFAULT_API_BASE_URL}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ idea, top_k: topK }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      const err = new Error((data && data.message) || `HTTP error ${res.status}`);
      err.status = res.status;
      err.errorData = data;
      throw err;
    }

    return data;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      const timeoutErr = new Error('The search request timed out. Please check if your FastAPI backend is running on http://localhost:8000.');
      timeoutErr.isTimeout = true;
      throw timeoutErr;
    }
    throw error;
  }
}

/**
 * Helper to simulate network latency for mock demonstrations
 */
function simulateDelay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Handle successful API response envelope and orchestrate rendering
 */
function handleSearchResponse(data, mode) {
  if (!data || data.status !== 'success') {
    showErrorBanner(data?.message || 'Unexpected response format from search service.');
    return;
  }

  // Toggle Mock Demonstration Banner based on mode
  if (mockNoticeBanner) {
    if (mode && mode.startsWith('mock-')) {
      mockNoticeBanner.classList.remove('hidden');
    } else {
      mockNoticeBanner.classList.add('hidden');
    }
  }

  // Render warnings if returned by server (e.g. top_k clamped)
  if (Array.isArray(data.warnings) && data.warnings.length > 0) {
    warningsList.innerHTML = '';
    data.warnings.forEach(warningText => {
      const li = document.createElement('li');
      li.textContent = warningText;
      warningsList.appendChild(li);
    });
    warningsContainer.classList.remove('hidden');
  }

  const matches = Array.isArray(data.matches) ? data.matches : [];

  if (matches.length === 0) {
    // Zero-matches scenario
    resultsContainer.classList.remove('hidden');
    resultsSummary.textContent = '0 Relevant Matches Found';
    matchesList.innerHTML = '';
    
    noMatchesMessage.textContent = data.message || 'No close match was found in the available dataset.';
    noMatchesBanner.classList.remove('hidden');
    return;
  }

  // Matches found
  resultsSummary.textContent = `${matches.length} Prior-Art Record${matches.length === 1 ? '' : 's'} Discovered`;
  renderMatchCards(matches);
  resultsContainer.classList.remove('hidden');
}

/**
 * Safe DOM rendering of research-grade match cards
 */
function renderMatchCards(matches) {
  matchesList.innerHTML = '';

  matches.forEach(match => {
    const card = document.createElement('article');
    card.className = 'surface-card rounded-2xl p-6 bg-white border border-slate-200/90 flex flex-col gap-4.5 animate-fade-in-up';

    // 1. Header Row: Rank Badge, Title, Verification Badge
    const headerRow = document.createElement('div');
    headerRow.className = 'flex flex-wrap items-start justify-between gap-3';

    const titleGroup = document.createElement('div');
    titleGroup.className = 'flex items-start gap-3.5 flex-1 min-w-[260px]';

    // Rank Badge
    const rankBadge = document.createElement('span');
    rankBadge.className = 'inline-flex items-center justify-center px-3 py-1 text-xs font-bold rounded-xl bg-indigo-50 text-indigo-700 border border-indigo-200/80 shrink-0 shadow-sm';
    rankBadge.textContent = `#${match.rank || '-'}`;

    const titleContainer = document.createElement('div');
    const title = document.createElement('h3');
    title.className = 'text-lg font-bold text-slate-900 leading-snug tracking-tight';
    title.textContent = match.title || 'Untitled Project Record';
    titleContainer.appendChild(title);

    // Meta subrow (Source Type, Domain, Year)
    const metaSubRow = document.createElement('div');
    metaSubRow.className = 'flex flex-wrap items-center gap-2 mt-1.5 text-xs text-slate-500';

    if (match.source_type) {
      const sourceTag = document.createElement('span');
      sourceTag.className = 'uppercase tracking-wider font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded text-[10px] border border-slate-200';
      sourceTag.textContent = match.source_type === 'rvce' ? 'RVCE Archive' : match.source_type;
      metaSubRow.appendChild(sourceTag);
    }

    if (match.domain) {
      const domainSpan = document.createElement('span');
      domainSpan.className = 'font-medium text-slate-600';
      domainSpan.textContent = `• ${match.domain}`;
      metaSubRow.appendChild(domainSpan);
    }

    if (match.year) {
      const yearSpan = document.createElement('span');
      yearSpan.className = 'text-slate-400 font-normal';
      yearSpan.textContent = `• ${match.year}`;
      metaSubRow.appendChild(yearSpan);
    }

    titleContainer.appendChild(metaSubRow);
    titleGroup.appendChild(rankBadge);
    titleGroup.appendChild(titleContainer);

    // Verification Status Badge
    const statusBadge = document.createElement('div');
    statusBadge.className = 'shrink-0';
    const statusText = document.createElement('span');
    statusText.className = 'inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-full border';

    const statusDot = document.createElement('span');
    statusDot.className = 'w-1.5 h-1.5 rounded-full';

    if (match.verification_status === 'checked') {
      statusText.className += ' bg-emerald-50 text-emerald-800 border-emerald-200';
      statusDot.className += ' bg-emerald-500';
      statusText.appendChild(statusDot);
      statusText.appendChild(document.createTextNode('Evidence Checked'));
    } else if (match.verification_status === 'insufficient') {
      statusText.className += ' bg-amber-50 text-amber-800 border-amber-200';
      statusDot.className += ' bg-amber-500';
      statusText.appendChild(statusDot);
      statusText.appendChild(document.createTextNode('Insufficient Evidence'));
    } else {
      statusText.className += ' bg-slate-50 text-slate-700 border-slate-200';
      statusText.textContent = match.verification_status || 'Unchecked';
    }
    statusBadge.appendChild(statusText);

    headerRow.appendChild(titleGroup);
    headerRow.appendChild(statusBadge);
    card.appendChild(headerRow);

    // 2. Abstract / Description Excerpt
    if (match.description_excerpt) {
      const excerptContainer = document.createElement('div');
      excerptContainer.className = 'bg-[#FAF9F5] border-l-4 border-indigo-400/80 p-3.5 rounded-r-xl text-xs sm:text-sm text-slate-700 leading-relaxed font-normal';
      
      const excerptText = document.createElement('p');
      excerptText.textContent = match.description_excerpt;
      excerptContainer.appendChild(excerptText);
      card.appendChild(excerptContainer);
    }

    // 3. Shared Elements (Detected Concepts)
    if (Array.isArray(match.shared_elements) && match.shared_elements.length > 0) {
      const overlapSection = document.createElement('div');
      overlapSection.className = 'flex flex-col gap-1.5 pt-1';

      const overlapLabel = document.createElement('span');
      overlapLabel.className = 'text-xs font-bold text-slate-600 uppercase tracking-wider text-[10px]';
      overlapLabel.textContent = 'Detected Shared Concepts:';
      overlapSection.appendChild(overlapLabel);

      const tagsContainer = document.createElement('div');
      tagsContainer.className = 'flex flex-wrap gap-1.5';

      match.shared_elements.forEach(term => {
        const tag = document.createElement('span');
        tag.className = 'bg-amber-50 text-amber-900 border border-amber-200 px-2.5 py-0.5 rounded-lg text-xs font-medium';
        tag.textContent = term;
        tagsContainer.appendChild(tag);
      });

      overlapSection.appendChild(tagsContainer);
      card.appendChild(overlapSection);
    }

    // 4. Technology Stack Badges
    if (Array.isArray(match.technologies) && match.technologies.length > 0) {
      const techSection = document.createElement('div');
      techSection.className = 'flex flex-wrap items-center gap-1.5';

      const techLabel = document.createElement('span');
      techLabel.className = 'text-[10px] font-bold text-slate-600 uppercase tracking-wider mr-1';
      techLabel.textContent = 'Tech Stack:';
      techSection.appendChild(techLabel);

      match.technologies.forEach(tech => {
        const badge = document.createElement('span');
        badge.className = 'bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md text-xs font-medium border border-slate-200';
        badge.textContent = tech;
        techSection.appendChild(badge);
      });

      card.appendChild(techSection);
    }

    // 5. Card Footer: Ranking Details & Provenance Link
    const footer = document.createElement('div');
    footer.className = 'flex flex-wrap items-center justify-between gap-3 pt-3 mt-1 border-t border-slate-100 text-xs text-slate-500';

    // RRF Score and Retrieval Metrics Container
    const metricsGroup = document.createElement('div');
    metricsGroup.className = 'flex flex-wrap items-center gap-3';

    // RRF score pill — clearly labeled as rank value, never a percentage
    const rrfPill = document.createElement('div');
    rrfPill.className = 'inline-flex items-center gap-1.5 bg-indigo-50/80 px-2.5 py-1 rounded-lg border border-indigo-200/80 text-indigo-900 font-medium';
    
    const rrfLabel = document.createElement('span');
    rrfLabel.className = 'text-[10px] uppercase font-bold text-indigo-600';
    rrfLabel.textContent = 'RRF Score';

    const rrfValue = document.createElement('span');
    rrfValue.className = 'font-mono font-bold text-indigo-800';
    rrfValue.textContent = typeof match.rrf_score === 'number' ? match.rrf_score.toFixed(4) : (match.rrf_score || '-');

    rrfPill.appendChild(rrfLabel);
    rrfPill.appendChild(rrfValue);
    metricsGroup.appendChild(rrfPill);

    if (match.bm25_rank != null) {
      const bm25Span = document.createElement('span');
      bm25Span.className = 'text-slate-500 font-medium';
      bm25Span.textContent = `BM25: #${match.bm25_rank}`;
      metricsGroup.appendChild(bm25Span);
    }

    if (match.vector_rank != null) {
      const vectorSpan = document.createElement('span');
      vectorSpan.className = 'text-slate-500 font-medium';
      vectorSpan.textContent = `Vector: #${match.vector_rank}`;
      metricsGroup.appendChild(vectorSpan);
    }

    footer.appendChild(metricsGroup);

    // Provenance Link (rendered only if valid HTTP/HTTPS URL provided)
    if (match.source_url && isValidHttpUrl(match.source_url)) {
      const link = document.createElement('a');
      link.href = match.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.className = 'inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 hover:underline font-semibold text-xs transition-colors';
      link.textContent = 'View Source Record ↗';
      footer.appendChild(link);
    }

    card.appendChild(footer);
    matchesList.appendChild(card);
  });
}

/**
 * Handle HTTP or network errors gracefully without exposing raw stack traces
 */
function handleSearchError(error) {
  resultsContainer.classList.add('hidden');

  if (error.status === 422 && error.errorData) {
    const detailMsg = error.errorData.message || 'The idea submission failed validation on the server.';
    showErrorBanner(detailMsg);
    return;
  }

  if (error.status === 500) {
    showErrorBanner('The search service encountered an internal error. Please check your query or try again.');
    return;
  }

  if (error.status === 503) {
    showErrorBanner('The search service is temporarily unavailable. Check that the search index has been initialized.');
    return;
  }

  if (error.isTimeout) {
    showErrorBanner('The search request timed out. Please check if your FastAPI backend is running on http://localhost:8000.');
    return;
  }

  // Generic network error (e.g. server down or refused connection)
  showErrorBanner('Unable to reach the Idea Enhancer backend. Ensure the FastAPI server is running on http://localhost:8000, or switch to Mock Demo mode above to test the interface.');
}

/**
 * Display top error alert banner
 */
function showErrorBanner(message) {
  errorMessageEl.textContent = message;
  errorBanner.classList.remove('hidden');
}

/**
 * Safely validate whether a string is an authentic HTTP or HTTPS URL
 */
function isValidHttpUrl(string) {
  try {
    const url = new URL(string);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch (_) {
    return false;
  }
}

// Bootstrap application on DOM ready
document.addEventListener('DOMContentLoaded', init);
