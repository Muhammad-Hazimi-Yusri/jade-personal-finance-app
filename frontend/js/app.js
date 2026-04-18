/**
 * app.js — SPA router and navigation controller.
 *
 * Hash-based routing: the fragment after '#' (e.g. '/transactions')
 * determines which view module is loaded. Each view exports a
 * render(container) function.
 */

import { showToast } from './toast.js';

// Route map: hash fragment → lazy view loader
const routes = {
    '':                  () => import('./views/dashboard.js'),
    'transactions':      () => import('./views/transactions.js'),
    'transactions/new':  () => import('./views/transaction-form.js'),
    'transactions/edit': () => import('./views/transaction-form.js'),
    'upload':            () => import('./views/upload.js'),
    'budgets':           () => import('./views/budgets.js'),
    'reports':           () => import('./views/reports.js'),
    'trades':            () => import('./views/trades.js'),
    'trades/new':        () => import('./views/trade-form.js'),
    'trades/edit':       () => import('./views/trade-form.js'),
    'trades/view':       () => import('./views/trade-detail.js'),
    'analytics':         () => import('./views/trade-analytics.js'),
    'journal':           () => import('./views/journal.js'),
    'settings':          () => import('./views/settings.js'),
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
        // Try progressively shorter prefixes:
        // 'transactions/edit/5' → 'transactions/edit' → 'transactions'
        const parts = key.split('/');
        for (let i = parts.length - 1; i >= 1; i--) {
            const prefix = parts.slice(0, i).join('/');
            if (routes[prefix]) {
                loader = routes[prefix];
                break;
            }
        }
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
        showToast(`Failed to load view: ${err.message}`, 'error');
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

/**
 * Fetch /api/meta and reveal the demo banner if demo_mode is enabled.
 */
async function initDemoBanner() {
    try {
        const res = await fetch('/api/meta');
        const data = await res.json();
        if (data.demo_mode) {
            document.getElementById('demo-banner').hidden = false;
        }
    } catch (_) {
        // Non-fatal: banner stays hidden if fetch fails
    }
}

/**
 * Mobile sidebar drawer. On screens ≤ 900px the sidebar is hidden off-screen;
 * the hamburger toggles a `.sidebar--open` class, and the backdrop dismisses.
 * We also auto-close on route change so navigating from a nav link hides it.
 */
function initSidebarDrawer() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebar-toggle');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar || !toggle || !backdrop) return;

    const open = () => {
        sidebar.classList.add('sidebar--open');
        backdrop.hidden = false;
        toggle.setAttribute('aria-expanded', 'true');
    };
    const close = () => {
        sidebar.classList.remove('sidebar--open');
        backdrop.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
    };
    const isOpen = () => sidebar.classList.contains('sidebar--open');

    toggle.addEventListener('click', () => (isOpen() ? close() : open()));
    backdrop.addEventListener('click', close);

    // Close when a nav link is clicked (drawer shouldn't linger over content).
    sidebar.addEventListener('click', (e) => {
        const link = e.target.closest('.nav-link');
        if (link) close();
    });

    // Close on hash change so programmatic navigation (e.g. after save)
    // also dismisses the drawer.
    window.addEventListener('hashchange', close);

    // Close on Escape for keyboard users.
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isOpen()) close();
    });
}

// ---- Initialise ----
window.addEventListener('hashchange', handleRoute);
document.addEventListener('DOMContentLoaded', () => {
    initDemoBanner();
    initSidebarDrawer();
    // Default to dashboard if no hash present
    if (!window.location.hash || window.location.hash === '#') {
        window.location.hash = '#/';
    }
    handleRoute();
});
