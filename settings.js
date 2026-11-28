/**
 * Idea Enhancer — Settings Page Logic
 * Manages preferences, API keys, providers
 */

import { Auth } from './shared/auth.js';

const SettingsPage = {
  providers: [
    { id: 'openalex', name: 'OpenAlex', description: '200M+ scholarly works, papers, authors, institutions', icon: '📚', enabled: true, free: true },
    { id: 'github', name: 'GitHub', description: 'Code repositories, stars, forks, topics, languages', icon: '💻', enabled: true, free: true },
    { id: 'semantic-scholar', name: 'Semantic Scholar', description: 'AI-powered paper search, citations, TLDRs, influential citations', icon: '🧠', enabled: false, free: true },
    { id: 'arxiv', name: 'arXiv', description: '2M+ preprints in physics, CS, math, engineering', icon: '📄', enabled: false, free: true },
    { id: 'crossref', name: 'CrossRef', description: '140M+ DOI records, bibliographic metadata, citations', icon: '🔗', enabled: false, free: true },
    { id: 'core', name: 'CORE', description: 'Open access papers, full text access', icon: '📖', enabled: false, free: true }
  ],

  init() {
    // Check auth
    if (!Auth.isLoggedIn()) {
      window.location.href = 'get-started.html';
      return;
    }

    this.loadSettings();
    this.bindEvents();
    this.renderProviders();
  },

  loadSettings() {
    const prefs = Auth.getPreferences();
    
    // Search preferences
    document.getElementById('set-default-mode').value = prefs.defaultMode || 'hybrid';
    document.getElementById('set-default-topk').value = prefs.defaultTopK || 5;
    document.getElementById('set-auto-save').checked = prefs.autoSave !== false;
    document.getElementById('set-reduced-motion').checked = prefs.reducedMotion || false;

    // Model preferences
    document.getElementById('set-default-model').value = prefs.preferredModels?.[0] || 'gemini-1.5-flash';
    document.getElementById('set-auto-enhance').checked = prefs.autoEnhance || false;

    // API keys (from localStorage)
    const apiKeys = JSON.parse(localStorage.getItem('idea-enhancer-api-keys') || '{}');
    document.getElementById('api-gemini').value = apiKeys.gemini || '';
    document.getElementById('api-openrouter').value = apiKeys.openrouter || '';
    document.getElementById('api-huggingface').value = apiKeys.huggingface || '';
    document.getElementById('api-groq').value = apiKeys.groq || '';

    // Analytics
    document.getElementById('analytics-optin').checked = prefs.analytics || false;

    // Providers
    const providerSettings = JSON.parse(localStorage.getItem('idea-enhancer-providers') || '{}');
    this.providers = this.providers.map(p => ({
      ...p,
      enabled: providerSettings[p.id]?.enabled ?? p.enabled
    }));
  },

  bindEvents() {
    // Save settings
    document.getElementById('save-settings-btn')?.addEventListener('click', () => this.saveSettings());

    // Search prefs form
    document.getElementById('search-prefs-form')?.addEventListener('submit', (e) => e.preventDefault());
    document.getElementById('model-prefs-form')?.addEventListener('submit', (e) => e.preventDefault());

    // API key test buttons
    document.getElementById('test-gemini')?.addEventListener('click', () => this.testApiKey('gemini'));
    document.getElementById('test-openrouter')?.addEventListener('click', () => this.testApiKey('openrouter'));
    document.getElementById('test-huggingface')?.addEventListener('click', () => this.testApiKey('huggingface'));
    document.getElementById('test-groq')?.addEventListener('click', () => this.testApiKey('groq'));

    // Provider toggles (delegated)
    document.getElementById('providers-list')?.addEventListener('change', (e) => {
      if (e.target.type === 'checkbox') {
        const providerId = e.target.dataset.provider;
        this.toggleProvider(providerId, e.target.checked);
      }
    });

    // Clear all data
    document.getElementById('clear-all-data-btn')?.addEventListener('click', () => this.clearAllData());

    // Export all data
    document.getElementById('export-all-data-btn')?.addEventListener('click', () => this.exportAllData());

    // Auth changes
    window.addEventListener('auth:change', (e) => {
      if (!e.detail.loggedIn) {
        window.location.href = 'get-started.html';
      }
    });
  },

  renderProviders() {
    const container = document.getElementById('providers-list');
    if (!container) return;

    container.innerHTML = this.providers.map(p => `
      <div class="surface-card rounded-2xl p-5 bg-white border border-slate-200/90 hover:shadow-md hover:border-slate-300 transition-all duration-200">
        <div class="flex items-start gap-4">
          <div class="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0 text-2xl">
            ${p.icon}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <h3 class="font-bold text-slate-900">${p.name}</h3>
              ${p.free ? '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Free</span>' : ''}
            </div>
            <p class="text-sm text-slate-600">${p.description}</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer shrink-0">
            <input type="checkbox" class="sr-only peer" data-provider="${p.id}" ${p.enabled ? 'checked' : ''}>
            <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
          </label>
        </div>
      </div>
    `).join('');
  },

  toggleProvider(id, enabled) {
    const provider = this.providers.find(p => p.id === id);
    if (provider) {
      provider.enabled = enabled;
    }
  },

  async testApiKey(provider) {
    const inputId = `api-${provider}`;
    const btnId = `test-${provider}`;
    const input = document.getElementById(inputId);
    const btn = document.getElementById(btnId);
    
    if (!input || !btn) return;

    const key = input.value.trim();
    if (!key) {
      alert('Please enter an API key first');
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Testing...';
    btn.classList.add('opacity-50');

    try {
      let testUrl, headers;
      
      switch (provider) {
        case 'gemini':
          testUrl = `https://generativelanguage.googleapis.com/v1beta/models?key=${key}`;
          break;
        case 'openrouter':
          testUrl = 'https://openrouter.ai/api/v1/models';
          headers = { 'Authorization': `Bearer ${key}` };
          break;
        case 'huggingface':
          testUrl = 'https://huggingface.co/api/whoami';
          headers = { 'Authorization': `Bearer ${key}` };
          break;
        case 'groq':
          testUrl = 'https://api.groq.com/openai/v1/models';
          headers = { 'Authorization': `Bearer ${key}` };
          break;
      }

      const response = await fetch(testUrl, { headers });
      
      if (response.ok) {
        btn.textContent = '✓ Valid';
        btn.classList.remove('bg-white', 'border-slate-200', 'text-slate-700', 'hover:bg-slate-50');
        btn.classList.add('bg-emerald-50', 'border-emerald-200', 'text-emerald-700');
        setTimeout(() => this.resetTestButton(btn), 2000);
      } else {
        btn.textContent = '✗ Invalid';
        btn.classList.remove('bg-white', 'border-slate-200', 'text-slate-700', 'hover:bg-slate-50');
        btn.classList.add('bg-rose-50', 'border-rose-200', 'text-rose-700');
        setTimeout(() => this.resetTestButton(btn), 2000);
      }
    } catch (err) {
      btn.textContent = '✗ Error';
      btn.classList.remove('bg-white', 'border-slate-200', 'text-slate-700', 'hover:bg-slate-50');
      btn.classList.add('bg-rose-50', 'border-rose-200', 'text-rose-700');
      setTimeout(() => this.resetTestButton(btn), 2000);
    }
  },

  resetTestButton(btn) {
    btn.disabled = false;
    btn.textContent = 'Test';
    btn.classList.remove('bg-emerald-50', 'border-emerald-200', 'text-emerald-700', 'bg-rose-50', 'border-rose-200', 'text-rose-700');
    btn.classList.add('bg-white', 'border-slate-200', 'text-slate-700', 'hover:bg-slate-50');
  },

  saveSettings() {
    const prefs = {
      // Search
      defaultMode: document.getElementById('set-default-mode').value,
      defaultTopK: parseInt(document.getElementById('set-default-topk').value),
      autoSave: document.getElementById('set-auto-save').checked,
      reducedMotion: document.getElementById('set-reduced-motion').checked,

      // Model
      preferredModels: [document.getElementById('set-default-model').value],
      autoEnhance: document.getElementById('set-auto-enhance').checked,

      // Analytics
      analytics: document.getElementById('analytics-optin').checked
    };

    Auth.updatePreferences(prefs);

    // API Keys
    const apiKeys = {
      gemini: document.getElementById('api-gemini').value,
      openrouter: document.getElementById('api-openrouter').value,
      huggingface: document.getElementById('api-huggingface').value,
      groq: document.getElementById('api-groq').value
    };
    localStorage.setItem('idea-enhancer-api-keys', JSON.stringify(apiKeys));

    // Providers
    const providerSettings = {};
    this.providers.forEach(p => {
      providerSettings[p.id] = { enabled: p.enabled };
    });
    localStorage.setItem('idea-enhancer-providers', JSON.stringify(providerSettings));

    // Show success
    this.showToast('Settings saved successfully!');
  },

  showToast(message) {
    // Create toast
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-6 right-6 z-50 px-6 py-3 rounded-xl bg-indigo-600 text-white font-medium shadow-lg animate-slide-up';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.classList.add('animate-fade-out');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  },

  clearAllData() {
    if (!confirm('This will delete ALL local data: history, saved results, preferences, API keys, and provider settings. Are you sure?')) return;
    if (!confirm('This action CANNOT be undone. Please confirm again.')) return;

    localStorage.clear();
    this.showToast('All local data cleared. Reloading...');
    setTimeout(() => window.location.reload(), 1000);
  },

  exportAllData() {
    const data = {
      exportedAt: new Date().toISOString(),
      preferences: Auth.getPreferences(),
      history: JSON.parse(localStorage.getItem('idea-enhancer-history') || '[]'),
      savedResults: JSON.parse(localStorage.getItem('idea-enhancer-saved') || '[]'),
      apiKeys: JSON.parse(localStorage.getItem('idea-enhancer-api-keys') || '{}'),
      providers: this.providers
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `idea-enhancer-backup-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    this.showToast('Data exported successfully!');
  }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  SettingsPage.init();
});

window.SettingsPage = SettingsPage;