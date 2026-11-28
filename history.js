/**
 * Idea Enhancer — History Page Logic
 * Manages search history, saved results, exports
 */

import { Auth } from './shared/auth.js';

const HistoryPage = {
  searches: [],
  savedResults: [],
  currentFilter: 'all',
  searchQuery: '',
  sortOrder: 'date-desc',

  init() {
    // Check auth
    if (!Auth.isLoggedIn()) {
      window.location.href = 'get-started.html';
      return;
    }

    this.loadData();
    this.bindEvents();
    this.render();
    this.updateStats();
  },

  loadData() {
    try {
      const historyData = localStorage.getItem('idea-enhancer-history');
      this.searches = historyData ? JSON.parse(historyData) : [];

      const savedData = localStorage.getItem('idea-enhancer-saved');
      this.savedResults = savedData ? JSON.parse(savedData) : [];
    } catch (_) {
      this.searches = [];
      this.savedResults = [];
    }
  },

  bindEvents() {
    // Filter
    document.getElementById('history-filter-mode')?.addEventListener('change', (e) => {
      this.currentFilter = e.target.value;
      this.render();
    });

    // Search
    document.getElementById('history-search')?.addEventListener('input', (e) => {
      this.searchQuery = e.target.value.toLowerCase();
      this.debounce(() => this.render(), 200);
    });

    // Sort
    document.getElementById('history-sort')?.addEventListener('change', (e) => {
      this.sortOrder = e.target.value;
      this.render();
    });

    // Export
    document.getElementById('export-history-btn')?.addEventListener('click', () => this.exportHistory());

    // Clear all
    document.getElementById('clear-all-history')?.addEventListener('click', () => this.clearAllHistory());

    // Auth changes
    window.addEventListener('auth:change', (e) => {
      if (!e.detail.loggedIn) {
        window.location.href = 'get-started.html';
      }
    });
  },

  getFilteredSearches() {
    let filtered = [...this.searches];

    // Mode filter
    if (this.currentFilter !== 'all') {
      filtered = filtered.filter(s => s.mode === this.currentFilter);
    }

    // Text search
    if (this.searchQuery) {
      filtered = filtered.filter(s => 
        s.idea.toLowerCase().includes(this.searchQuery) ||
        s.mode.toLowerCase().includes(this.searchQuery)
      );
    }

    // Sort
    filtered.sort((a, b) => {
      const dateA = new Date(a.timestamp).getTime();
      const dateB = new Date(b.timestamp).getTime();
      
      switch (this.sortOrder) {
        case 'date-asc':
          return dateA - dateB;
        case 'results-desc':
          return (b.resultCount || 0) - (a.resultCount || 0);
        default: // date-desc
          return dateB - dateA;
      }
    });

    return filtered;
  },

  render() {
    const timeline = document.getElementById('history-timeline');
    const empty = document.getElementById('history-empty');
    
    if (!timeline || !empty) return;

    const filtered = this.getFilteredSearches();

    if (filtered.length === 0) {
      timeline.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }

    empty.classList.add('hidden');

    // Group by date
    const grouped = this.groupByDate(filtered);
    
    timeline.innerHTML = Object.entries(grouped).map(([date, searches]) => `
      <div class="timeline-day">
        <div class="timeline-date">${this.formatDateHeader(date)}</div>
        <div class="timeline-items space-y-4">
          ${searches.map(search => this.renderSearchCard(search)).join('')}
        </div>
      </div>
    `).join('');

    // Bind events
    this.bindCardEvents();
  },

  groupByDate(searches) {
    const grouped = {};
    searches.forEach(search => {
      const date = new Date(search.timestamp).toDateString();
      if (!grouped[date]) grouped[date] = [];
      grouped[date].push(search);
    });
    return grouped;
  },

  formatDateHeader(dateStr) {
    const date = new Date(dateStr);
    const today = new Date().toDateString();
    const yesterday = new Date(Date.now() - 86400000).toDateString();
    
    if (dateStr === today) return 'Today';
    if (dateStr === yesterday) return 'Yesterday';
    return date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  },

  renderSearchCard(search) {
    const modeColors = {
      hybrid: 'bg-purple-50 text-purple-700 border-purple-200',
      local: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      live: 'bg-emerald-50 text-emerald-700 border-emerald-200'
    };

    const modeLabels = {
      hybrid: 'Hybrid',
      local: 'Local',
      live: 'Live'
    };

    const modeClass = modeColors[search.mode] || modeColors.hybrid;
    const modeLabel = modeLabels[search.mode] || search.mode;

    const time = new Date(search.timestamp).toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });

    const isSaved = this.savedResults.some(s => s.id === search.id);

    return `
      <article class="surface-card rounded-2xl p-5 bg-white border border-slate-200/90 hover:shadow-md hover:border-slate-300 transition-all duration-200 animate-slide-up" data-id="${search.id}">
        <div class="flex items-start gap-4">
          <div class="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center shrink-0">
            <svg class="w-6 h-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></path></svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-2">
              <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold ${modeClass} uppercase tracking-wider">
                ${modeLabel}
              </span>
              <span class="text-xs text-slate-500">${time}</span>
              ${search.saved ? `
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
                  Saved
                </span>
              ` : ''}
            </div>
            <h3 class="font-bold text-slate-900 text-base mb-1 line-clamp-2">${this.truncate(search.idea, 120)}</h3>
            <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500">
              <span>📊 ${search.resultCount || 0} results</span>
              <span>🔢 Top-${search.topK || 5}</span>
            </div>
          </div>
          <div class="flex flex-col items-end gap-2 shrink-0">
            <button class="reload-search-btn px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-medium text-xs border border-indigo-200/70" data-id="${search.id}">
              <svg class="w-3 h-3 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></path></svg>
              Search Again
            </button>
            <button class="save-toggle-btn px-3 py-1.5 rounded-lg ${search.saved ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-slate-50 text-slate-700 border-slate-200'} font-medium text-xs border" data-id="${search.id}">
              ${search.saved ? 
                '<svg class="w-3 h-3 inline mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg> Saved' :
                '<svg class="w-3 h-3 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" /></path></svg> Save'}
            </button>
            <button class="delete-history-btn p-2 rounded-lg hover:bg-rose-50 text-slate-500 hover:text-rose-600 transition-colors" data-id="${search.id}" aria-label="Delete from history">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></path></svg>
            </button>
          </div>
        </div>
      </article>
    `;
  },

  bindCardEvents() {
    // Reload search
    document.querySelectorAll('.reload-search-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        const search = this.searches.find(s => s.id === id);
        if (search) {
          const params = new URLSearchParams({
            q: search.idea,
            mode: search.mode,
            top_k: search.topK.toString()
          });
          window.location.href = `results.html?${params.toString()}`;
        }
      });
    });

    // Save/unsave
    document.querySelectorAll('.save-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        this.toggleSave(id);
      });
    });

    // Delete
    document.querySelectorAll('.delete-history-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        this.deleteSearch(id);
      });
    });
  },

  toggleSave(id) {
    const search = this.searches.find(s => s.id === id);
    if (!search) return;

    const savedIndex = this.savedResults.findIndex(s => s.id === id);
    
    if (savedIndex >= 0) {
      // Unsave
      this.savedResults.splice(savedIndex, 1);
      search.saved = false;
    } else {
      // Save
      this.savedResults.unshift({ ...search, savedAt: new Date().toISOString() });
      search.saved = true;
    }

    this.saveData();
    this.render();
    this.updateStats();
  },

  deleteSearch(id) {
    if (!confirm('Remove this search from history?')) return;

    this.searches = this.searches.filter(s => s.id !== id);
    this.savedResults = this.savedResults.filter(s => s.id !== id);
    
    this.saveData();
    this.render();
    this.updateStats();
  },

  clearAllHistory() {
    if (!confirm('Clear ALL search history? This cannot be undone.')) return;
    if (!confirm('Are you sure? This will also remove all saved results.')) return;

    this.searches = [];
    this.savedResults = [];
    this.saveData();
    this.render();
    this.updateStats();
  },

  saveData() {
    try {
      localStorage.setItem('idea-enhancer-history', JSON.stringify(this.searches));
      localStorage.setItem('idea-enhancer-saved', JSON.stringify(this.savedResults));
    } catch (_) {
      // Storage full
    }
  },

  exportHistory() {
    const data = {
      exportedAt: new Date().toISOString(),
      searches: this.searches,
      savedResults: this.savedResults
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `idea-enhancer-history-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  },

  updateStats() {
    const totalSearches = this.searches.length;
    const uniqueTerms = new Set(this.searches.flatMap(s => s.idea.toLowerCase().split(/\s+/).filter(w => w.length > 3))).size;
    const savedResults = this.savedResults.length;
    const domains = new Set(this.searches.map(s => s.mode)).size;

    document.getElementById('stat-total-searches').textContent = totalSearches;
    document.getElementById('stat-unique-terms').textContent = uniqueTerms;
    document.getElementById('stat-saved-results').textContent = savedResults;
    document.getElementById('stat-domains').textContent = domains;
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
  }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  HistoryPage.init();
});

window.HistoryPage = HistoryPage;