/**
 * Idea Enhancer — Client-Side Router with View Transitions
 * Hash-based routing: #/search, #/results, #/history, etc.
 */

const Router = {
  routes: new Map(),
  currentRoute: null,
  transitioning: false,

  // Define a route
  add(path, handler) {
    this.routes.set(path, handler);
  },

  // Navigate to a route
  navigate(path, options = {}) {
    if (this.transitioning) return Promise.resolve();
    
    const hash = path.startsWith('#') ? path : '#' + path;
    const fullHash = window.location.hash;
    
    if (fullHash === hash && !options.force) return Promise.resolve();
    
    this.transitioning = true;
    
    // Use View Transitions API if available
    if (document.startViewTransition && !options.noTransition) {
      return this._navigateWithTransition(hash, options);
    }
    
    return this._navigateDirect(hash, options);
  },

  // Navigate with View Transitions
  async _navigateWithTransition(hash, options) {
    return new Promise((resolve) => {
      const transition = document.startViewTransition(async () => {
        window.location.hash = hash;
        await this._handleRouteChange(hash);
      });
      
      transition.finished.then(() => {
        this.transitioning = false;
        resolve();
      }).catch(() => {
        this.transitioning = false;
        resolve();
      });
    });
  },

  // Direct navigation (fallback)
  async _navigateDirect(hash, options) {
    window.location.hash = hash;
    await this._handleRouteChange(hash);
    this.transitioning = false;
  },

  // Handle route change
  async _handleRouteChange(hash) {
    const path = hash.replace(/^#/, '') || '/';
    const [routePath, ...params] = path.split('?');
    
    // Find matching route
    let handler = this.routes.get(routePath);
    let matchedPath = routePath;
    
    // Check for parameterized routes
    if (!handler) {
      for (const [route, h] of this.routes) {
        const regex = this._routeToRegex(route);
        const match = routePath.match(regex);
        if (match) {
          handler = h;
          matchedPath = route;
          break;
        }
      }
    }
    
    this.currentRoute = { path: routePath, matchedPath, params: params.join('?') };
    
    if (handler) {
      try {
        await handler(this.currentRoute);
      } catch (err) {
        console.error('Route handler error:', err);
      }
    }
    
    // Update active nav links
    this._updateActiveLinks(routePath);
    
    // Scroll to top
    window.scrollTo(0, 0);
    
    // Dispatch route change event
    window.dispatchEvent(new CustomEvent('route:change', { detail: this.currentRoute }));
  },

  // Convert route pattern to regex
  _routeToRegex(pattern) {
    const regexPattern = pattern
      .replace(/\*/g, '.*')
      .replace(/:(\w+)/g, '([^/]+)');
    return new RegExp(`^${regexPattern}$`);
  },

  // Update active navigation links
  _updateActiveLinks(currentPath) {
    document.querySelectorAll('[data-nav-link]').forEach(link => {
      const href = link.getAttribute('href');
      if (href) {
        const linkPath = href.replace(/^#/, '') || '/';
        const isActive = linkPath === currentPath || 
          (currentPath.startsWith(linkPath) && linkPath !== '/');
        link.classList.toggle('text-indigo-600', isActive);
        link.classList.toggle('font-semibold', isActive);
        link.setAttribute('aria-current', isActive ? 'page' : 'false');
      }
    });
  },

  // Start router (listen for hash changes)
  start() {
    window.addEventListener('hashchange', () => {
      if (!this.transitioning) {
        this._handleRouteChange(window.location.hash);
      }
    });
    
    // Initial route
    this._handleRouteChange(window.location.hash);
  },

  // Get current route info
  getCurrentRoute() {
    return this.currentRoute;
  },

  // Generate URL for a route
  url(path, params = {}) {
    let url = '#' + path;
    const query = new URLSearchParams(params).toString();
    if (query) url += '?' + query;
    return url;
  }
};

// Helper: Create nav link with proper attributes
function createNavLink(path, text, options = {}) {
  const url = Router.url(path);
  const isActive = Router.currentRoute?.path === path || 
    (Router.currentRoute?.path?.startsWith(path) && path !== '/');
  
  return `
    <a 
      href="${url}" 
      data-nav-link="${path}"
      class="hover:text-indigo-600 transition-colors py-1 relative after:absolute after:bottom-0 after:left-0 after:w-0 after:h-0.5 after:bg-indigo-600 after:transition-all hover:after:w-full ${isActive ? 'text-indigo-600 font-semibold' : ''}"
      aria-current="${isActive ? 'page' : 'false'}"
      ${options.external ? 'target="_blank" rel="noopener"' : ''}
    >
      ${text}
    </a>
  `;
}

// Export for modules
window.Router = Router;
window.createNavLink = createNavLink;