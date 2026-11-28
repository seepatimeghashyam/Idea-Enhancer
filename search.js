/**
 * Idea Enhancer — Search Page Logic
 * Handles search form, mode selection, recent history, API calls
 */

import { Auth } from './shared/auth.js';

const SearchPage = {
  currentMode: 'hybrid',
  recentSearches: [],
  abortController: null,

  // Sample ideas for quick-fill
  samples: {
    'iot-crop': 'An IoT-based crop disease detection system using Raspberry Pi 4 and MobileNetV2 CNN to monitor foliar infections in real-time with LoRaWAN connectivity for remote farms, including automated alerting via SMS and dashboard visualization.',
    'quantum-pet': 'Quantum teleportation device for household pets using acoustic levitation and superconducting qubits to enable instantaneous relocation of small animals within a residential environment, with safety monitoring via IoT sensors.',
    'swarm-robot': 'AI-assisted swarm robotics with ant colony optimization for dynamic exploration and mapping of unknown environments, using ESP32-based agents with Ultra-Wideband localization and decentralized consensus protocols.',
    'fpga-aes': 'FPGA-based AES-256 encryption system for hardware security and data protection in embedded IoT devices, implemented on Xilinx Artix-7 with side-channel attack countermeasures and real-time key rotation.'
  },

  init() {
    // Check auth
    if (!Auth.isLoggedIn()) {
      window.location.href = 'get-started.html';
      return;
    }

    // Load preferences
    const prefs = Auth.getPreferences();
    this.currentMode = prefs.defaultMode || 'hybrid';
    this.updateModeUI(this.currentMode);

    // Load recent searches
    this.loadRecentSearches();

    // Bind events
    this.bindEvents();

    // Focus input
    setTimeout(() => {
      document.getElementById('idea-input')?.focus();
    }, 100);
  },

  bindEvents() {
    // Mode buttons
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
    });

    // Form submission
    document.getElementById('search-form')?.addEventListener('submit', (e) => this.handleSubmit(e));

    // Textarea events
    const textarea = document.getElementById('idea-input');
    textarea?.addEventListener('input', () => this.updateCharCount());
    textarea?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        document.getElementById('search-form')?.dispatchEvent(new Event('submit'));
      }
    });

    // Clear button
    document.getElementById('clear-btn')?.addEventListener('click', () => {
      textarea.value = '';
      this.updateCharCount();
      textarea.focus();
    });

    // Voice button (placeholder)
    document.getElementById('voice-btn')?.addEventListener('click', () => {
      this.startVoiceInput();
    });

    // Sample buttons
    document.querySelectorAll('[data-sample]').forEach(btn => {
      btn.addEventListener('click', () => this.fillSample(btn.dataset.sample));
    });

    // Clear history
    document.getElementById('clear-history-btn')?.addEventListener('click', () => this.clearHistory());

    // Auth changes
    window.addEventListener('auth:change', (e) => {
      if (!e.detail.loggedIn) {
        window.location.href = 'get-started.html';
      }
    });
  },

  setMode(mode) {
    this.currentMode = mode;
    this.updateModeUI(mode);
    document.getElementById('search-mode').value = mode;
  },

  updateModeUI(mode) {
    // Update buttons
    document.querySelectorAll('.mode-btn').forEach(btn => {
      const isActive = btn.dataset.mode === mode;
      btn.setAttribute('aria-checked', isActive);
      if (isActive) {
        btn.className = 'mode-btn px-4 py-2.5 rounded-xl text-sm font-medium text-indigo-600 bg-white shadow-sm transition-all';
      } else {
        btn.className = 'mode-btn px-4 py-2.5 rounded-xl text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors';
      }
    });

    // Update badge
    const badge = document.getElementById('mode-badge');
    const labels = {
      hybrid: 'Hybrid Search',
      local: 'Local Only',
      live: 'Live Research'
    };
    if (badge) badge.textContent = labels[mode] || 'Hybrid Search';

    // Show/hide privacy notice
    const privacy = document.getElementById('privacy-notice');
    if (privacy) {
      privacy.classList.toggle('hidden', mode === 'local');
    }

    // Update hint text
    const hint = document.getElementById('idea-hint');
    if (hint) {
      const hints = {
        hybrid: 'Minimum 10 characters, maximum 2000. Specific hardware, models, and domain produce better matches. Auto-routes to local or live.',
        local: 'Minimum 10 characters, maximum 2000. Searches only the local historical project dataset (2,000+ records).',
        live: 'Minimum 10 characters, maximum 2000. Queries OpenAlex, GitHub, Semantic Scholar, arXiv, CrossRef. Your idea text is sent to these public APIs.'
      };
      hint.textContent = hints[mode] || hints.hybrid;
    }
  },

  updateCharCount() {
    const textarea = document.getElementById('idea-input');
    const countEl = document.getElementById('char-count');
    if (textarea && countEl) {
      const len = textarea.value.length;
      countEl.textContent = `${len} / 2000 characters`;
      countEl.classList.toggle('text-rose-500', len > 1900);
      countEl.classList.toggle('text-slate-500', len <= 1900);
    }
  },

  fillSample(key) {
    const textarea = document.getElementById('idea-input');
    if (textarea && this.samples[key]) {
      textarea.value = this.samples[key];
      this.updateCharCount();
      textarea.focus();
      
      // Scroll to textarea
      textarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  },

  startVoiceInput() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Voice input is not supported in this browser. Try Chrome or Edge.');
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    const btn = document.getElementById('voice-btn');
    const textarea = document.getElementById('idea-input');
    let finalTranscript = '';

    btn.classList.add('bg-indigo-100', 'text-indigo-600');
    btn.innerHTML = '<svg class="w-5 h-5 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></path></svg>';

    recognition.onresult = (event) => {
      let interimTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interimTranscript += transcript;
        }
      }
      textarea.value = finalTranscript + interimTranscript;
      this.updateCharCount();
    };

    recognition.onerror = (event) => {
      console.warn('Speech recognition error:', event.error);
    };

    recognition.onend = () => {
      btn.classList.remove('bg-indigo-100', 'text-indigo-600');
      btn.innerHTML = '<svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></path></svg>';
    };

    recognition.start();
  },

  async handleSubmit(e) {
    e.preventDefault();

    const textarea = document.getElementById('idea-input');
    const idea = textarea?.value.trim() || '';
    const topK = parseInt(document.getElementById('top-k-input')?.value) || 5;
    const mode = this.currentMode;

    // Client-side validation
    if (idea.length < 10) {
      this.showValidationError('Please enter at least 10 characters describing your idea.');
      return;
    }
    if (idea.length > 2000) {
      this.showValidationError('Idea must be 2000 characters or less.');
      return;
    }

    this.hideValidationError();
    this.setLoading(true);

    // Cancel any in-flight request
    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();

    try {
      // Save to history if enabled
      const prefs = Auth.getPreferences();
      if (prefs.autoSave !== false) {
        this.saveToHistory(idea, mode, topK);
      }

      // Navigate to results page with query params
      const params = new URLSearchParams({
        q: idea,
        mode: mode,
        top_k: topK.toString()
      });
      
      window.location.href = `results.html?${params.toString()}`;
      
    } catch (err) {
      console.error('Search error:', err);
      this.showValidationError('Search failed. Please try again.');
    } finally {
      this.setLoading(false);
    }
  },

  setLoading(loading) {
    const btn = document.getElementById('submit-btn');
    const spinner = document.getElementById('submit-btn-spinner');
    const icon = document.getElementById('submit-btn-icon');
    const text = document.getElementById('submit-btn-text');

    if (btn) btn.disabled = loading;
    if (spinner) spinner.classList.toggle('hidden', !loading);
    if (icon) icon.classList.toggle('hidden', loading);
    if (text) text.textContent = loading ? 'Searching...' : 'Investigate Idea';
  },

  showValidationError(message) {
    const container = document.getElementById('client-validation-error');
    const text = document.getElementById('client-validation-text');
    if (container && text) {
      text.textContent = message;
      container.classList.remove('hidden');
    }
  },

  hideValidationError() {
    const container = document.getElementById('client-validation-error');
    if (container) container.classList.add('hidden');
  },

  loadRecentSearches() {
    try {
      const data = localStorage.getItem('idea-enhancer-history');
      this.recentSearches = data ? JSON.parse(data) : [];
      this.renderRecentSearches();
    } catch (_) {
      this.recentSearches = [];
    }
  },

  renderRecentSearches() {
    const container = document.getElementById('recent-list');
    const section = document.getElementById('recent-searches');
    if (!container || !section) return;

    if (this.recentSearches.length === 0) {
      section.classList.add('hidden');
      return;
    }

    section.classList.remove('hidden');
    container.innerHTML = this.recentSearches
      .slice(0, 5)
      .map((search, i) => `
        <button 
          type="button" 
          class="recent-search-chip px-3 py-1.5 rounded-lg bg-slate-50 text-slate-700 hover:bg-slate-100 font-medium border border-slate-200/70 text-xs truncate max-w-[200px]"
          data-index="${i}"
          title="${search.idea}"
        >
          ${this.truncate(search.idea, 50)}
        </button>
      `).join('');

    // Bind click events
    container.querySelectorAll('.recent-search-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.index);
        const search = this.recentSearches[idx];
        if (search) {
          document.getElementById('idea-input').value = search.idea;
          this.updateCharCount();
          this.setMode(search.mode);
          document.getElementById('top-k-input').value = search.topK;
        }
      });
    });
  },

  saveToHistory(idea, mode, topK) {
    const search = {
      id: Date.now().toString(),
      idea,
      mode,
      topK,
      timestamp: new Date().toISOString()
    };

    this.recentSearches.unshift(search);
    this.recentSearches = this.recentSearches.slice(0, 50); // Keep last 50

    try {
      localStorage.setItem('idea-enhancer-history', JSON.stringify(this.recentSearches));
    } catch (_) {
      // Storage full or unavailable
    }

    this.renderRecentSearches();
  },

  clearHistory() {
    if (confirm('Clear all recent searches? This cannot be undone.')) {
      this.recentSearches = [];
      localStorage.removeItem('idea-enhancer-history');
      this.renderRecentSearches();
    }
  },

  truncate(str, len) {
    return str.length > len ? str.slice(0, len) + '…' : str;
  }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  SearchPage.init();
});

window.SearchPage = SearchPage;