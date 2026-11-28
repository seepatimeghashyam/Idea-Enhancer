/**
 * Idea Enhancer — Results Page Logic
 * Handles search results display, enhancer panel, exports
 */

import { Auth } from './shared/auth.js';

const ResultsPage = {
  currentQuery: '',
  currentMode: 'hybrid',
  currentTopK: 5,
  currentTab: 'all',
  results: [],
  filteredResults: [],
  enhancerAbortController: null,
  comparisonModels: ['gemini-1.5-flash', 'openrouter:mistralai/mixtral-8x7b-instruct', 'huggingface:HuggingFaceH4/zephyr-7b-beta'],
  comparisonResults: {},

  init() {
    // Check auth
    if (!Auth.isLoggedIn()) {
      window.location.href = 'get-started.html';
      return;
    }

    // Parse URL params
    this.parseURLParams();

    // Load preferences
    const prefs = Auth.getPreferences();
    this.currentMode = prefs.defaultMode || 'hybrid';
    this.currentTopK = prefs.defaultTopK || 5;

    // Bind events
    this.bindEvents();

    // Fetch results
    this.fetchResults();
  },

  parseURLParams() {
    const params = new URLSearchParams(window.location.search);
    this.currentQuery = params.get('q') || '';
    this.currentMode = params.get('mode') || 'hybrid';
    this.currentTopK = parseInt(params.get('top_k')) || 5;

    // Update UI
    document.getElementById('results-query')?.textContent = 
      this.currentQuery ? `"${this.currentQuery}"` : '';
    document.getElementById('mode-text')?.textContent = 
      this.currentMode.charAt(0).toUpperCase() + this.currentMode.slice(1);
  },

  bindEvents() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
    });

    // Sort & Filter
    document.getElementById('sort-select')?.addEventListener('change', () => this.applyFilters());
    document.getElementById('source-filter')?.addEventListener('change', () => this.applyFilters());
    document.getElementById('domain-filter')?.addEventListener('change', () => this.applyFilters());
    document.getElementById('year-filter')?.addEventListener('input', () => this.debounce(() => this.applyFilters(), 300));
    document.getElementById('clear-filters')?.addEventListener('click', () => this.clearFilters());

    // Export
    document.getElementById('export-btn')?.addEventListener('click', () => this.toggleExportDropdown());
    document.querySelectorAll('#export-dropdown button').forEach(btn => {
      btn.addEventListener('click', () => this.exportResults(btn.dataset.format));
    });

    // Close export dropdown on outside click
    document.addEventListener('click', (e) => {
      const dropdown = document.getElementById('export-dropdown');
      const btn = document.getElementById('export-btn');
      if (dropdown && !dropdown.contains(e.target) && btn && !btn.contains(e.target)) {
        dropdown.classList.add('hidden');
      }
    });

    // Pagination
    document.getElementById('prev-page')?.addEventListener('click', () => this.changePage(-1));
    document.getElementById('next-page')?.addEventListener('click', () => this.changePage(1));

    // Refine search
    document.getElementById('refine-search-btn')?.addEventListener('click', () => {
      window.location.href = 'search.html';
    });

    // Enhancer panel
    document.getElementById('enhance-btn')?.addEventListener('click', () => this.openEnhancer());
    document.getElementById('close-enhancer')?.addEventListener('click', () => this.closeEnhancer());
    document.getElementById('close-enhancer-bottom')?.addEventListener('click', () => this.closeEnhancer());
    document.getElementById('enhancer-overlay')?.addEventListener('click', () => this.closeEnhancer());

    // Enhancer model change
    document.getElementById('enhancer-model')?.addEventListener('change', () => {
      // Model changed, ready for next enhancement
    });

    // Auth changes
    window.addEventListener('auth:change', (e) => {
      if (!e.detail.loggedIn) {
        window.location.href = 'get-started.html';
      }
    });
  },

  async fetchResults() {
    this.showLoading(true);

    try {
      const response = await fetch(`${window.IDEA_ENHANCER_API_BASE_URL || 'http://localhost:8000'}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          idea: this.currentQuery,
          top_k: this.currentTopK,
          mode: this.currentMode
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Search failed');
      }

      this.results = data.matches || [];
      this.applyFilters();
      this.renderModeNotice(data);
      this.renderProviderStatus(data);
      this.renderRecurringEvidence(data);
      this.populateDomainFilter();
      this.showLoading(false);
      this.showResults();

    } catch (err) {
      console.error('Fetch error:', err);
      this.showLoading(false);
      this.showError(err.message);
    }
  },

  showLoading(show) {
    const loading = document.getElementById('loading-state');
    const results = document.getElementById('results-container');
    if (loading) loading.classList.toggle('hidden', !show);
    if (results) results.classList.toggle('hidden', show);
  },

  showResults() {
    const loading = document.getElementById('loading-state');
    const results = document.getElementById('results-container');
    if (loading) loading.classList.add('hidden');
    if (results) results.classList.remove('hidden');
  },

  showError(message) {
    const container = document.getElementById('matches-container');
    if (container) {
      container.innerHTML = `
        <div class="surface-card rounded-2xl p-8 bg-white border border-slate-200/90 text-center">
          <div class="w-12 h-12 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto mb-4">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></path></svg>
          </div>
          <h3 class="text-lg font-bold text-slate-900 mb-2">Search Failed</h3>
          <p class="text-slate-600 mb-4">${message}</p>
          <button onclick="window.ResultsPage.fetchResults()" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm">Retry</button>
        </div>
      `;
    }
  },

  applyFilters() {
    let filtered = [...this.results];

    // Source filter
    const sourceFilter = document.getElementById('source-filter')?.value;
    if (sourceFilter && sourceFilter !== 'all') {
      filtered = filtered.filter(r => r.source_type === sourceFilter || r.source_provider === sourceFilter);
    }

    // Domain filter
    const domainFilter = document.getElementById('domain-filter')?.value;
    if (domainFilter && domainFilter !== 'all') {
      filtered = filtered.filter(r => r.domain === domainFilter);
    }

    // Year filter
    const yearFilter = document.getElementById('year-filter')?.value;
    if (yearFilter) {
      const year = parseInt(yearFilter);
      if (!isNaN(year)) {
        filtered = filtered.filter(r => r.year && parseInt(r.year) === year);
      }
    }

    // Tab filter
    if (this.currentTab === 'papers') {
      filtered = filtered.filter(r => r.source_type === 'research_paper' || r.candidate_type === 'paper');
    } else if (this.currentTab === 'repos') {
      filtered = filtered.filter(r => r.source_type === 'open_source_repository' || r.candidate_type === 'repository');
    } else if (this.currentTab === 'local') {
      filtered = filtered.filter(r => r.source_type === 'institutional_project' || r.candidate_type === 'local');
    }

    // Sort
    const sort = document.getElementById('sort-select')?.value;
    switch (sort) {
      case 'date':
        filtered.sort((a, b) => (b.year || 0) - (a.year || 0));
        break;
      case 'citations':
        filtered.sort((a, b) => (b.citation_count || 0) - (a.citation_count || 0));
        break;
      case 'stars':
        filtered.sort((a, b) => (b.stars || 0) - (a.stars || 0));
        break;
      default:
        // Relevance (original order)
        break;
    }

    this.filteredResults = filtered;
    this.renderResults();
    this.updateResultCount();
    this.updateClearFiltersVisibility();
  },

  switchTab(tab) {
    this.currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => {
      const isActive = btn.dataset.tab === tab;
      btn.setAttribute('aria-selected', isActive);
      if (isActive) {
        btn.className = 'tab-btn px-4 py-2 rounded-xl text-sm font-medium text-indigo-600 bg-indigo-50 whitespace-nowrap';
      } else {
        btn.className = 'tab-btn px-4 py-2 rounded-xl text-sm font-medium text-slate-600 hover:text-slate-900 whitespace-nowrap';
      }
    });
    this.applyFilters();
  },

  clearFilters() {
    document.getElementById('source-filter').value = 'all';
    document.getElementById('domain-filter').value = 'all';
    document.getElementById('year-filter').value = '';
    document.getElementById('sort-select').value = 'relevance';
    this.applyFilters();
  },

  updateClearFiltersVisibility() {
    const btn = document.getElementById('clear-filters');
    const hasFilters = 
      document.getElementById('source-filter').value !== 'all' ||
      document.getElementById('domain-filter').value !== 'all' ||
      document.getElementById('year-filter').value !== '' ||
      document.getElementById('sort-select').value !== 'relevance';
    btn.classList.toggle('hidden', !hasFilters);
  },

  renderResults() {
    const container = document.getElementById('matches-container');
    const emptyState = document.getElementById('empty-state');
    const pagination = document.getElementById('pagination');

    if (!container) return;

    if (this.filteredResults.length === 0) {
      container.innerHTML = '';
      emptyState?.classList.remove('hidden');
      pagination?.classList.add('hidden');
      return;
    }

    emptyState?.classList.add('hidden');
    pagination?.classList.remove('hidden');

    container.innerHTML = this.filteredResults.map((result, index) => this.renderResultCard(result, index)).join('');

    // Bind expand/collapse
    container.querySelectorAll('.expand-btn').forEach(btn => {
      btn.addEventListener('click', () => this.toggleExpand(btn.dataset.id));
    });

    // Bind save buttons
    container.querySelectorAll('.save-btn').forEach(btn => {
      btn.addEventListener('click', () => this.toggleSave(btn.dataset.id));
    });

    // Bind citation expand
    container.querySelectorAll('.citation-btn').forEach(btn => {
      btn.addEventListener('click', () => this.toggleCitations(btn.dataset.id));
    });
  },

  renderResultCard(result, index) {
    const isLocal = result.source_type === 'institutional_project' || result.candidate_type === 'local';
    const isPaper = result.source_type === 'research_paper' || result.candidate_type === 'paper';
    const isRepo = result.source_type === 'open_source_repository' || result.candidate_type === 'repository';
    
    const sourceIcons = {
      'institutional_project': '🏫',
      'research_paper': '📄',
      'open_source_repository': '💻',
      'paper': '📄',
      'repository': '💻'
    };

    const sourceLabels = {
      'institutional_project': 'Institutional Project',
      'research_paper': 'Research Paper',
      'open_source_repository': 'Open-Source Repository',
      'paper': 'Research Paper',
      'repository': 'Open-Source Repository'
    };

    const verificationLabels = {
      'checked': { text: 'Text overlap found', class: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
      'insufficient': { text: 'No shared terms found', class: 'bg-amber-50 text-amber-700 border-amber-200' },
      'unknown': { text: 'Not verified', class: 'bg-slate-50 text-slate-700 border-slate-200' }
    };

    const verification = verificationLabels[result.verification_status] || verificationLabels.unknown;
    const sourceIcon = sourceIcons[result.source_type] || sourceIcons[result.candidate_type] || '📄';
    const sourceLabel = sourceLabels[result.source_type] || sourceLabels[result.candidate_type] || 'Unknown';

    const cardId = `result-${result.candidate_id || result.project_id || index}`;

    return `
      <article 
        id="${cardId}" 
        class="surface-card rounded-2xl p-5 bg-white border border-slate-200/90 shadow-sm hover:shadow-md hover:border-slate-300 transition-all duration-200 animate-slide-up"
        style="animation-delay: ${index * 50}ms"
        role="listitem"
      >
        <!-- Header -->
        <div class="flex items-start gap-4">
          <div class="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0 font-bold text-sm">
            ${index + 1}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-lg">${sourceIcon}</span>
              <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 uppercase tracking-wider">
                ${sourceLabel}
              </span>
              ${result.citation_count ? `
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200">
                  <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></path></svg>
                  ${result.citation_count}
                </span>
              ` : ''}
              ${result.stars ? `
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 9.27l6.26-.01L12 2l1.18 6.88z"/></svg>
                  ${result.stars}
                </span>
              ` : ''}
            </div>
            <h3 class="font-bold text-slate-900 text-base mb-1 line-clamp-2">${result.title || 'Untitled'}</h3>
            <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500 mb-2">
              ${result.year ? `<span>📅 ${result.year}</span>` : ''}
              ${result.domain ? `<span>🏷️ ${result.domain}</span>` : ''}
              ${result.venue ? `<span>📚 ${this.truncate(result.venue, 30)}</span>` : ''}
              ${result.work_type ? `<span>📝 ${result.work_type}</span>` : ''}
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button class="save-btn p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-amber-500 transition-colors" data-id="${cardId}" aria-label="Save to history">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" /></path></svg>
            </button>
            <button class="expand-btn p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-indigo-600 transition-colors" data-id="${cardId}" aria-label="Expand details">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></path></svg>
            </button>
          </div>
        </div>

        <!-- Expandable Details -->
        <div id="${cardId}-details" class="hidden mt-4 pt-4 border-t border-slate-100 animate-slide-down">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h4 class="font-semibold text-slate-900 mb-2">Abstract / Description</h4>
              <p class="text-sm text-slate-600 leading-relaxed">${result.abstract || result.description || 'No description available.'}</p>
            </div>
            <div>
              <h4 class="font-semibold text-slate-900 mb-2">Details</h4>
              <dl class="space-y-2 text-sm">
                ${result.authors && result.authors.length ? `
                  <div>
                    <dt class="text-slate-500">Authors</dt>
                    <dd class="font-medium text-slate-900">${result.authors.slice(0, 3).join(', ')}${result.authors.length > 3 ? ' et al.' : ''}</dd>
                  </div>
                ` : ''}
                ${result.doi ? `
                  <div>
                    <dt class="text-slate-500">DOI</dt>
                    <dd class="font-medium text-indigo-600"><a href="https://doi.org/${result.doi}" target="_blank" rel="noopener" class="hover:underline">${result.doi}</a></dd>
                  </div>
                ` : ''}
                ${result.source_url ? `
                  <div>
                    <dt class="text-slate-500">Source</dt>
                    <dd class="font-medium text-indigo-600"><a href="${result.source_url}" target="_blank" rel="noopener" class="hover:underline truncate block max-w-xs">${result.source_url}</a></dd>
                  </div>
                ` : ''}
                ${result.tech_stack ? `
                  <div>
                    <dt class="text-slate-500">Tech Stack</dt>
                    <dd class="font-medium text-slate-900">${result.tech_stack}</dd>
                  </div>
                ` : ''}
                ${result.shared_elements && result.shared_elements.length ? `
                  <div>
                    <dt class="text-slate-500">Shared Concepts</dt>
                    <dd class="flex flex-wrap gap-1">${result.shared_elements.map(s => `<span class="px-2 py-0.5 rounded text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">${s}</span>`).join('')}</dd>
                  </div>
                ` : ''}
                ${result.shared_concepts && result.shared_concepts.length ? `
                  <div>
                    <dt class="text-slate-500">Shared Concepts</dt>
                    <dd class="flex flex-wrap gap-1">${result.shared_concepts.map(s => `<span class="px-2 py-0.5 rounded text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">${s}</span>`).join('')}</dd>
                  </div>
                ` : ''}
                ${result.distinctive_terms && result.distinctive_terms.length ? `
                  <div>
                    <dt class="text-slate-500">Distinctive Terms</dt>
                    <dd class="flex flex-wrap gap-1">${result.distinctive_terms.map(s => `<span class="px-2 py-0.5 rounded text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200">${s}</span>`).join('')}</dd>
                  </div>
                ` : ''}
                ${result.explanation ? `
                  <div>
                    <dt class="text-slate-500">Why This Matched</dt>
                    <dd class="text-slate-600 text-sm">${result.explanation}</dd>
                  </div>
                ` : ''}
              </dl>
            </div>
          </div>

          <!-- Verification Badge -->
          <div class="mt-4 flex items-center gap-3 p-3 rounded-xl border ${verification.class}">
            <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></path></svg>
            <span class="text-sm font-medium">${verification.text}</span>
          </div>

          <!-- Citations Expandable -->
          ${(result.citations && result.citations.length) || (result.references && result.references.length) ? `
            <div class="mt-4">
              <button class="citation-btn w-full text-left px-4 py-2 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium flex items-center justify-between" data-id="${cardId}" aria-expanded="false">
                <span>📚 Citations & References <span class="text-xs text-slate-500">(${ (result.citations?.length || 0) + (result.references?.length || 0) })</span></span>
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></path></svg>
              </button>
              <div id="${cardId}-citations" class="hidden mt-3 space-y-2">
                ${result.citations && result.citations.length ? `
                  <div>
                    <h5 class="font-semibold text-slate-900 mb-2 text-sm">Cited By (${result.citations.length})</h5>
                    <div class="space-y-1 max-h-40 overflow-y-auto">
                      ${result.citations.slice(0, 5).map(c => `
                        <div class="p-2 rounded-lg bg-white border border-slate-200 text-xs text-slate-600">
                          <div class="font-medium text-slate-900">${c.title || 'Untitled'}</div>
                          <div class="text-slate-500">${c.authors?.slice(0, 2).join(', ') || ''} ${c.year ? `(${c.year})` : ''}</div>
                        </div>
                      `).join('')}
                      ${result.citations.length > 5 ? `<div class="text-xs text-slate-500 text-center py-1">+${result.citations.length - 5} more</div>` : ''}
                    </div>
                  </div>
                ` : ''}
                ${result.references && result.references.length ? `
                  <div>
                    <h5 class="font-semibold text-slate-900 mb-2 text-sm">References (${result.references.length})</h5>
                    <div class="space-y-1 max-h-40 overflow-y-auto">
                      ${result.references.slice(0, 5).map(r => `
                        <div class="p-2 rounded-lg bg-white border border-slate-200 text-xs text-slate-600">
                          <div class="font-medium text-slate-900">${r.title || 'Untitled'}</div>
                          <div class="text-slate-500">${r.authors?.slice(0, 2).join(', ') || ''} ${r.year ? `(${r.year})` : ''}</div>
                        </div>
                      `).join('')}
                      ${result.references.length > 5 ? `<div class="text-xs text-slate-500 text-center py-1">+${result.references.length - 5} more</div>` : ''}
                    </div>
                  </div>
                ` : ''}
              </div>
            </div>
          ` : ''}

          <!-- Action Buttons -->
          <div class="mt-4 flex flex-wrap gap-2">
            ${result.source_url ? `
              <a href="${result.source_url}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium text-sm">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></path></svg>
                View Source
              </a>
            ` : ''}
            ${result.doi ? `
              <a href="https://doi.org/${result.doi}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium text-sm">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></path></svg>
                DOI
              </a>
            ` : ''}
            <button class="save-btn inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium text-sm" data-id="${cardId}">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" /></path></svg>
              Save
            </button>
          </div>
        </div>
      </article>
    `;
  },

  toggleExpand(cardId) {
    const details = document.getElementById(`${cardId}-details`);
    const btn = document.querySelector(`[data-id="${cardId}"].expand-btn`);
    if (details && btn) {
      const isOpen = details.classList.toggle('hidden');
      btn.setAttribute('aria-expanded', !isOpen);
      btn.innerHTML = isOpen 
        ? '<svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></path></svg>'
        : '<svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" /></path></svg>';
    }
  },

  toggleCitations(cardId) {
    const citations = document.getElementById(`${cardId}-citations`);
    const btn = document.querySelector(`[data-id="${cardId}"].citation-btn`);
    if (citations && btn) {
      const isOpen = citations.classList.toggle('hidden');
      btn.setAttribute('aria-expanded', !isOpen);
      btn.querySelector('svg').style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
    }
  },

  toggleSave(cardId) {
    // Find result and save to history
    const result = this.results.find(r => 
      `result-${r.candidate_id || r.project_id}` === cardId ||
      `result-${r.candidate_id || r.project_id || ''}` === cardId
    );
    if (result) {
      this.saveResultToHistory(result);
    }
  },

  saveResultToHistory(result) {
    // Implementation for saving individual result
    console.log('Save result:', result.title);
  },

  renderModeNotice(data) {
    const notice = document.getElementById('mode-notice');
    if (!notice) return;

    if (this.currentMode === 'local' || (data.state && data.state !== 'complete')) {
      notice.classList.remove('hidden');
      notice.innerHTML = `
        <span class="font-bold uppercase tracking-wider text-xs bg-amber-200 text-amber-950 px-2 py-0.5 rounded shrink-0">
          ${this.currentMode === 'local' ? 'Offline Demo' : data.state?.charAt(0).toUpperCase() + data.state?.slice(1)}
        </span>
        <p class="flex-1 min-w-0 leading-relaxed">
          ${this.currentMode === 'local' 
            ? 'Results from local historical project dataset. Links and records may not have been independently verified.'
            : 'Some discovery sources were unavailable; results may be incomplete.'}
        </p>
      `;
    } else {
      notice.classList.add('hidden');
    }
  },

  renderProviderStatus(data) {
    const container = document.getElementById('provider-status');
    if (!container || !data.providers) return;

    const providers = Object.entries(data.providers);
    const hasIssues = providers.some(([_, p]) => p.state !== 'success' && p.state !== 'empty');

    if (hasIssues) {
      container.classList.remove('hidden');
      container.innerHTML = providers.map(([name, p]) => `
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium ${
          p.state === 'success' ? 'bg-emerald-50 text-emerald-700' :
          p.state === 'empty' ? 'bg-amber-50 text-amber-700' :
          'bg-rose-50 text-rose-700'
        }">
          <span class="w-1.5 h-1.5 rounded-full ${
            p.state === 'success' ? 'bg-emerald-500' :
            p.state === 'empty' ? 'bg-amber-500' :
            'bg-rose-500'
          }" aria-hidden="true"></span>
          ${name}: ${p.state}${p.count ? ` (${p.count})` : ''}
        </span>
      `).join(' ');
    } else {
      container.classList.add('hidden');
    }
  },

  renderRecurringEvidence(data) {
    const container = document.getElementById('recurring-evidence');
    const list = document.getElementById('recurring-list');
    if (!container || !list || !data.recurring_evidence?.length) {
      container?.classList.add('hidden');
      return;
    }

    container.classList.remove('hidden');
    list.innerHTML = data.recurring_evidence.map(item => `
      <button class="evidence-chip px-3 py-1 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-medium border border-indigo-200/70 text-sm" 
              data-term="${item.term}">
        ${item.term} <span class="text-xs opacity-70">(${item.candidate_count})</span>
      </button>
    `).join('');

    // Bind click to filter
    list.querySelectorAll('.evidence-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        // Could filter results by this term
        console.log('Filter by:', btn.dataset.term);
      });
    });
  },

  populateDomainFilter() {
    const select = document.getElementById('domain-filter');
    if (!select) return;

    const domains = [...new Set(this.results.map(r => r.domain).filter(Boolean))].sort();
    const current = select.value;
    
    select.innerHTML = '<option value="all">All Domains</option>' + 
      domains.map(d => `<option value="${this.escapeHtml(d)}">${this.escapeHtml(d)}</option>`).join('');
    
    select.value = current;
  },

  toggleExportDropdown() {
    const dropdown = document.getElementById('export-dropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
  },

  async exportResults(format) {
    const dropdown = document.getElementById('export-dropdown');
    dropdown?.classList.add('hidden');

    try {
      const params = new URLSearchParams({
        format,
        mode: this.currentMode,
        idea: this.currentQuery,
        top_k: this.currentTopK.toString()
      });

      const response = await fetch(`${window.IDEA_ENHANCER_API_BASE_URL || 'http://localhost:8000'}/export?${params.toString()}`);
      
      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `idea-enhancer-results-${Date.now()}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export error:', err);
      alert('Export failed. Please try again.');
    }
  },

  openEnhancer() {
    const panel = document.getElementById('enhancer-panel');
    const overlay = document.getElementById('enhancer-overlay');
    if (panel) panel.classList.remove('translate-x-full');
    if (overlay) overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  },

  closeEnhancer() {
    const panel = document.getElementById('enhancer-panel');
    const overlay = document.getElementById('enhancer-overlay');
    if (panel) panel.classList.add('translate-x-full');
    if (overlay) overlay.classList.add('hidden');
    document.body.style.overflow = '';
  },

  debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
  },

  truncate(str, len) {
    return str.length > len ? str.slice(0, len) + '…' : str;
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  updateResultCount() {
    const countEl = document.getElementById('result-count');
    if (countEl) {
      countEl.textContent = `${this.filteredResults.length} result${this.filteredResults.length !== 1 ? 's' : ''}`;
    }
  }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  ResultsPage.init();
});

window.ResultsPage = ResultsPage;