/**
 * Idea Enhancer — Authentication & Session Management
 * Demo auth using localStorage (no backend)
 */

const AUTH_KEY = 'idea-enhancer-auth';
const SESSION_KEY = 'idea-enhancer-session';

const Auth = {
  // Check if user is logged in
  isLoggedIn() {
    const session = this.getSession();
    return session && session.user && session.expires > Date.now();
  },

  // Get current session
  getSession() {
    try {
      const data = localStorage.getItem(SESSION_KEY);
      return data ? JSON.parse(data) : null;
    } catch (_) {
      return null;
    }
  },

  // Get current user
  getUser() {
    const session = this.getSession();
    return session?.user || null;
  },

  // Login (demo - accepts any credentials)
  login(email, password, remember = false) {
    if (!email || !password) {
      throw new Error('Email and password are required');
    }

    const user = {
      id: 'user_' + Date.now(),
      email: email.trim().toLowerCase(),
      name: email.split('@')[0],
      avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(email.split('@')[0])}&background=6366f1&color=fff&size=128`,
      createdAt: new Date().toISOString(),
      preferences: {
        theme: 'light',
        defaultMode: 'hybrid',
        defaultTopK: 5,
        preferredModels: ['gemini-1.5-flash'],
        autoSave: true
      }
    };

    const session = {
      user,
      token: 'demo_token_' + Math.random().toString(36).substr(2),
      expires: Date.now() + (remember ? 30 * 24 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000), // 30 days or 1 day
      createdAt: new Date().toISOString()
    };

    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    localStorage.setItem(AUTH_KEY, 'true');

    // Dispatch auth change event
    window.dispatchEvent(new CustomEvent('auth:change', { detail: { user, loggedIn: true } }));

    return { user, session };
  },

  // Signup (demo - same as login)
  signup(email, password, name) {
    return this.login(email, password, true);
  },

  // Logout
  logout() {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(AUTH_KEY);
    
    window.dispatchEvent(new CustomEvent('auth:change', { detail: { user: null, loggedIn: false } }));
  },

  // Update user preferences
  updatePreferences(prefs) {
    const session = this.getSession();
    if (session) {
      session.user.preferences = { ...session.user.preferences, ...prefs };
      localStorage.setItem(SESSION_KEY, JSON.stringify(session));
      window.dispatchEvent(new CustomEvent('auth:preferences', { detail: session.user.preferences }));
      return session.user.preferences;
    }
    return null;
  },

  // Get user preferences
  getPreferences() {
    const user = this.getUser();
    return user?.preferences || {
      theme: 'light',
      defaultMode: 'hybrid',
      defaultTopK: 5,
      preferredModels: ['gemini-1.5-flash'],
      autoSave: true
    };
  },

  // Require auth (redirect if not logged in)
  requireAuth(redirectTo = 'index.html') {
    if (!this.isLoggedIn()) {
      window.location.href = redirectTo + '?redirect=' + encodeURIComponent(window.location.pathname);
      return false;
    }
    return true;
  },

  // Initialize auth UI
  initAuthUI() {
    this.renderAuthSection();
    this.bindAuthEvents();
    
    // Listen for auth changes
    window.addEventListener('auth:change', () => this.renderAuthSection());
  },

  // Render auth section in header
  renderAuthSection() {
    const container = document.getElementById('auth-section');
    if (!container) return;

    const user = this.getUser();
    
    if (user) {
      container.innerHTML = `
        <div class="relative" id="user-menu-container">
          <button 
            id="user-menu-btn"
            type="button"
            class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-expanded="false"
            aria-haspopup="true"
            aria-label="User menu"
          >
            <img 
              src="${user.avatar}" 
              alt="" 
              class="w-7 h-7 rounded-full border border-slate-200"
              loading="lazy"
            >
            <span class="text-sm font-medium text-slate-700 hidden sm:block">${user.name}</span>
            <svg class="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          
          <div 
            id="user-menu-dropdown"
            class="hidden absolute right-0 top-full mt-2 w-56 bg-white rounded-xl border border-slate-200 shadow-lg py-1 z-50"
            role="menu"
            aria-orientation="vertical"
          >
            <div class="px-4 py-3 border-b border-slate-100">
              <p class="text-sm font-semibold text-slate-900">${user.name}</p>
              <p class="text-xs text-slate-500 truncate">${user.email}</p>
            </div>
            
            <a href="settings.html" class="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-indigo-600" role="menuitem">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              Settings
            </a>
            
            <a href="history.html" class="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-indigo-600" role="menuitem">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              History
            </a>
            
            <div class="border-t border-slate-100 my-1"></div>
            
            <button 
              id="logout-btn"
              class="flex items-center gap-2 w-full px-4 py-2 text-sm text-rose-600 hover:bg-rose-50 hover:text-rose-700" 
              role="menuitem"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
              Sign Out
            </button>
          </div>
        </div>
      `;
      
      this.bindUserMenu();
    } else {
      container.innerHTML = `
        <a href="index.html?mode=login" class="px-4 py-2 text-sm font-medium text-slate-700 hover:text-indigo-600 transition-colors">Sign In</a>
        <a href="index.html?mode=signup" class="inline-flex items-center justify-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm transition-all shadow-sm hover:shadow-md">
          <span>Get Started</span>
        </a>
      `;
    }
  },

  // Bind user menu events
  bindUserMenu() {
    const btn = document.getElementById('user-menu-btn');
    const dropdown = document.getElementById('user-menu-dropdown');
    const logoutBtn = document.getElementById('logout-btn');
    
    if (!btn || !dropdown) return;

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = dropdown.classList.toggle('hidden');
      btn.setAttribute('aria-expanded', !isOpen);
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!btn.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.add('hidden');
        btn.setAttribute('aria-expanded', 'false');
      }
    });

    // Close on escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        dropdown.classList.add('hidden');
        btn.setAttribute('aria-expanded', 'false');
      }
    });

    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => {
        this.logout();
        window.location.href = 'index.html';
      });
    }
  },

  // Bind auth form events
  bindAuthEvents() {
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const remember = document.getElementById('login-remember').checked;
        
        try {
          this.login(email, password, remember);
          const redirect = new URLSearchParams(window.location.search).get('redirect') || 'get-started.html';
          window.location.href = redirect;
        } catch (err) {
          this.showAuthError('login-error', err.message);
        }
      });
    }

    if (signupForm) {
      signupForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = document.getElementById('signup-name').value;
        const email = document.getElementById('signup-email').value;
        const password = document.getElementById('signup-password').value;
        const confirm = document.getElementById('signup-confirm').value;
        
        if (password !== confirm) {
          this.showAuthError('signup-error', 'Passwords do not match');
          return;
        }
        
        if (password.length < 6) {
          this.showAuthError('signup-error', 'Password must be at least 6 characters');
          return;
        }
        
        try {
          this.signup(email, password, name);
          window.location.href = 'get-started.html';
        } catch (err) {
          this.showAuthError('signup-error', err.message);
        }
      });
    }

    // Mode switch tabs
    document.querySelectorAll('.auth-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const mode = tab.dataset.mode;
        document.querySelectorAll('.auth-tab').forEach(t => {
          t.classList.toggle('active', t === tab);
          t.setAttribute('aria-selected', t === tab);
        });
        document.querySelectorAll('.auth-panel').forEach(p => {
          p.classList.toggle('hidden', p.id !== `auth-panel-${mode}`);
        });
        // Update URL without reload
        history.replaceState(null, '', `?mode=${mode}`);
      });
    });
  },

  // Show auth error
  showAuthError(elementId, message) {
    const el = document.getElementById(elementId);
    if (el) {
      el.textContent = message;
      el.classList.remove('hidden');
      setTimeout(() => el.classList.add('hidden'), 5000);
    }
  }
};

// Auto-init on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => Auth.initAuthUI());
} else {
  Auth.initAuthUI();
}

// Export for modules
window.Auth = Auth;