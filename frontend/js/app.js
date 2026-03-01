/**
 * app.js — SPA router and navigation controller.
 *
 * Hash-based routing: the fragment after '#' (e.g. '/transactions')
 * determines which view module is loaded. Each view exports a
 * render(container) function.
 */

// Route map: hash fragment → lazy view loader
const routes = {
    '':               () => import('./views/dashboard.js'),
    'transactions':   () => import('./views/transactions.js'),
    'upload':         () => import('./views/upload.js'),
    'budgets':        () => import('./views/budgets.js'),
    'trades':         () => import('./views/trades.js'),
    'trades/new':     () => import('./views/trade-form.js'),
    'analytics':      () => import('./views/trade-analytics.js'),
    'journal':        () => import('./views/journal.js'),
    'settings':       () => import('./views/settings.js'),
};

const app = document.getElementById('app');

/**
 * Parse the current hash into a route key.
 * '#/transactions' → 'transactions'
 * '#/'             → ''
 * ''               → ''
 */
function getRouteKey() {
    const hash = window.location.hash;          // e.g. '#/transactions'
    const path = hash.replace(/^#\/?/, '');     // e.g. 'transactions'
    return path;
}

/**
 * Load and render the view that matches the current route.
 * Falls back to the dashboard for unknown routes.
 */
async function handleRoute() {
    const key = getRouteKey();

    // Find exact match first, then check prefix matches for nested routes
    let loader = routes[key];
    if (!loader) {
        // Try prefix: 'trades/123' → 'trades'
        const prefix = key.split('/')[0];
        loader = routes[prefix];
    }
    if (!loader) {
        loader = routes[''];  // fallback: dashboard
    }

    // Show loading state while importing the module
    app.innerHTML = '<div class="loading">Loading…</div>';

    try {
        const module = await loader();
        await module.render(app);
    } catch (err) {
        console.error('Route error:', err);
        app.innerHTML = `
            <div class="error-state">
                <strong>Something went wrong</strong>
                <p class="mt-2">${err.message}</p>
            </div>`;
    }

    updateActiveNav(key);
}

/**
 * Highlight the nav link that matches the current route.
 */
function updateActiveNav(key) {
    const links = document.querySelectorAll('.nav-link');
    links.forEach(link => {
        const route = link.dataset.route ?? '';
        // Match: exact, or 'trades' matches 'trades/new' etc.
        const isActive = route === key || (route && key.startsWith(route + '/'));
        link.classList.toggle('active', isActive);
    });
}

// ---- Initialise ----
window.addEventListener('hashchange', handleRoute);
document.addEventListener('DOMContentLoaded', () => {
    // Default to dashboard if no hash present
    if (!window.location.hash || window.location.hash === '#') {
        window.location.hash = '#/';
    }
    handleRoute();
});
