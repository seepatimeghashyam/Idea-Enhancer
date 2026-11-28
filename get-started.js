/**
 * Idea Enhancer — Get Started / Onboarding Flow
 */

import { Auth } from './shared/auth.js';

const Onboarding = {
  currentStep: 1,
  maxSteps: 3,

  init() {
    // Check if already logged in
    if (Auth.isLoggedIn()) {
      this.currentStep = 2;
      this.showStep(2);
      this.loadPreferences();
    } else {
      this.showStep(1);
      this.renderAuthForms();
    }

    this.bindEvents();
    this.updateProgress();
  },

  renderAuthForms() {
    const container = document.getElementById('auth-container');
    if (!container) return;

    const mode = new URLSearchParams(window.location.search).get('mode') || 'login';

    container.innerHTML = `
      <div class="surface-card rounded-2xl p-6 sm:p-8 bg-white border border-slate-200/90 shadow-md">
        <!-- Tab Navigation -->
        <div class="flex gap-1 mb-6 bg-slate-100 rounded-xl p-1" role="tablist">
          <button 
            role="tab" 
            class="auth-tab flex-1 px-4 py-2.5 text-sm font-semibold rounded-lg transition-all ${mode === 'login' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'}"
            data-mode="login"
            aria-selected="${mode === 'login'}"
            id="tab-login"
          >
            Sign In
          </button>
          <button 
            role="tab" 
            class="auth-tab flex-1 px-4 py-2.5 text-sm font-semibold rounded-lg transition-all ${mode === 'signup' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'}"
            data-mode="signup"
            aria-selected="${mode === 'signup'}"
            id="tab-signup"
          >
            Create Account
          </button>
        </div>

        <!-- Login Panel -->
        <form id="login-form" class="auth-panel space-y-4 ${mode !== 'login' ? 'hidden' : ''}" role="tabpanel" aria-labelledby="tab-login">
          <div id="login-error" class="hidden p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm"></div>
          
          <div>
            <label for="login-email" class="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input type="email" id="login-email" name="email" required autocomplete="email" class="w-full bg-white text-slate-900 border border-slate-300 rounded-xl px-4 py-3 placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:outline-none" placeholder="you@university.edu">
          </div>
          
          <div>
            <label for="login-password" class="block text-sm font-medium text-slate-700 mb-1">Password</label>
            <input type="password" id="login-password" name="password" required autocomplete="current-password" class="w-full bg-white text-slate-900 border border-slate-300 rounded-xl px-4 py-3 placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:outline-none" placeholder="••••••••">
          </div>
          
          <div class="flex items-center gap-3">
            <input type="checkbox" id="login-remember" class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500">
            <label for="login-remember" class="text-sm text-slate-700">Remember me for 30 days</label>
          </div>
          
          <button type="submit" class="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm transition-all shadow-md hover:shadow-lg shadow-indigo-600/25 hover:-translate-y-0.5">
            <span>Sign In</span>
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
          </button>
        </form>

        <!-- Signup Panel -->
        <form id="signup-form" class="auth-panel space-y-4 ${mode !== 'signup' ? 'hidden' : ''}" role="tabpanel" aria-labelledby="tab-signup">
          <div id="signup-error" class="hidden p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm"></div>
          
          <div>
            <label for="signup-name" class="block text-sm font-medium text-slate-700 mb-1">Name</label>
            <input type="text" id="signup-name" name="name" required autocomplete="name" class="w-full bg-white text-slate-900 border border-slate-300 rounded-xl px-4 py-3 placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:outline-none" placeholder="Alex Chen">
          </div>
          
          <div>
            <label for="signup-email" class="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input type="email" id="signup-email" name="email" required autocomplete="email" class="w-full bg-white text-slate-900 border border-slate-300 rounded-xl px-4 py-3 placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:outline-none" placeholder="you@university.edu">
          </div>
          
          <div>
            <label for="signup-password" class="block text-sm font-medium text-slate-700 mb-1">Password</label>
            <input type="password" id="signup-password" name="password" required autocomplete="new-password" minlength="6" class="w-full bg-white text-slate-900 border border-slate-300 rounded-xl px-4 py-3 placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:outline-none" placeholder="At least 6 characters">
          </div>
          
          <div>
            <label for="signup-confirm" class="block text-sm font-medium text-slate-700 mb-1">Confirm Password</label>
            <input type="password" id="signup-confirm" name="confirm" required autocomplete="new-password" class="w-full bg-white text-slate-900 border border-slate-300 rounded-xl px-4 py-3 placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:outline-none" placeholder="••••••••">
          </div>
          
          <button type="submit" class="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm transition-all shadow-md hover:shadow-lg shadow-indigo-600/25 hover:-translate-y-0.5">
            <span>Create Account</span>
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" /></svg>
          </button>
        </form>

        <p class="text-center text-xs text-slate-500 mt-6">
          Demo mode: any credentials work. Data stored locally in your browser.
        </p>
      </div>
    `;
  },

  bindEvents() {
    // Auth form submissions handled by Auth.js
    window.addEventListener('auth:change', (e) => {
      if (e.detail.loggedIn) {
        this.enableContinue('continue-to-prefs');
        // Auto-advance after short delay
        setTimeout(() => this.nextStep(), 500);
      }
    });

    // Continue buttons
    document.getElementById('continue-to-prefs')?.addEventListener('click', () => this.nextStep());
    document.getElementById('continue-to-ready')?.addEventListener('click', () => this.nextStep());
    document.getElementById('back-to-account')?.addEventListener('click', () => this.prevStep());

    // Preferences form
    document.getElementById('preferences-form')?.addEventListener('submit', (e) => {
      e.preventDefault();
      this.savePreferences();
    });
  },

  showStep(step) {
    // Hide all steps
    document.querySelectorAll('.onboarding-step').forEach(el => {
      el.classList.add('hidden');
    });
    
    // Show target step
    const target = document.getElementById(`step-${step}`);
    if (target) {
      target.classList.remove('hidden');
      // Trigger animation
      requestAnimationFrame(() => {
        target.style.opacity = '1';
        target.style.transform = 'translateY(0)';
      });
    }

    this.currentStep = step;
    this.updateProgress();
    this.updateNavigation();
  },

  nextStep() {
    if (this.currentStep < this.maxSteps) {
      this.showStep(this.currentStep + 1);
    }
  },

  prevStep() {
    if (this.currentStep > 1) {
      this.showStep(this.currentStep - 1);
    }
  },

  updateProgress() {
    // Update step indicators
    for (let i = 1; i <= this.maxSteps; i++) {
      const indicator = document.getElementById(`step-${i}-indicator`);
      const bar = document.getElementById(`progress-bar-${i}`);
      
      if (indicator) {
        if (i < this.currentStep) {
          indicator.className = 'w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-sm';
          indicator.innerHTML = '✓';
        } else if (i === this.currentStep) {
          indicator.className = 'w-10 h-10 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-sm';
          indicator.textContent = i;
        } else {
          indicator.className = 'w-10 h-10 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm';
          indicator.textContent = i;
        }
      }
      
      if (bar) {
        bar.className = `hidden md:block flex-1 h-1 transition-all duration-500 ${i < this.currentStep ? 'bg-emerald-500' : 'bg-slate-200'}`;
      }
    }
  },

  updateNavigation() {
    const backBtn = document.getElementById('back-to-account');
    const continueBtn = document.getElementById('continue-to-prefs') || document.getElementById('continue-to-ready');
    
    if (backBtn) {
      backBtn.classList.toggle('hidden', this.currentStep === 1);
    }
  },

  enableContinue(buttonId) {
    const btn = document.getElementById(buttonId);
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  },

  loadPreferences() {
    const prefs = Auth.getPreferences();
    
    document.getElementById('pref-default-mode')?.value = prefs.defaultMode || 'hybrid';
    document.getElementById('pref-default-topk')?.value = prefs.defaultTopK || 5;
    document.getElementById('pref-preferred-model')?.value = prefs.preferredModels?.[0] || 'gemini-1.5-flash';
    document.getElementById('pref-auto-enhance')?.checked = prefs.autoEnhance || false;
    document.getElementById('pref-auto-save')?.checked = prefs.autoSave !== false;
    document.getElementById('pref-analytics')?.checked = prefs.analytics || false;
    document.getElementById('pref-reduced-motion')?.checked = prefs.reducedMotion || false;
  },

  savePreferences() {
    const prefs = {
      defaultMode: document.getElementById('pref-default-mode')?.value || 'hybrid',
      defaultTopK: parseInt(document.getElementById('pref-default-topk')?.value) || 5,
      preferredModels: [document.getElementById('pref-preferred-model')?.value || 'gemini-1.5-flash'],
      autoEnhance: document.getElementById('pref-auto-enhance')?.checked || false,
      autoSave: document.getElementById('pref-auto-save')?.checked !== false,
      analytics: document.getElementById('pref-analytics')?.checked || false,
      reducedMotion: document.getElementById('pref-reduced-motion')?.checked || false
    };

    Auth.updatePreferences(prefs);
    this.nextStep();
  }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  Onboarding.init();
});

// Export for testing
window.Onboarding = Onboarding;