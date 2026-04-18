/**
 * toast.js — Lightweight notification system.
 *
 * Singleton container appended to <body> on first call. Toasts stack
 * top-right, auto-dismiss after a timeout, and can be dismissed by click.
 *
 * Usage:
 *   import { showToast } from './toast.js';
 *   showToast('Category saved', 'success');
 *   showToast('Network error', 'error', 6000);
 *
 * Types: 'success' | 'error' | 'info' | 'warning'.
 */

const DEFAULT_DURATION_MS = 3500;
const CONTAINER_ID = 'toast-container';

function getContainer() {
    let el = document.getElementById(CONTAINER_ID);
    if (!el) {
        el = document.createElement('div');
        el.id = CONTAINER_ID;
        el.className = 'toast-container';
        el.setAttribute('role', 'status');
        el.setAttribute('aria-live', 'polite');
        document.body.appendChild(el);
    }
    return el;
}

/**
 * Show a toast notification.
 * @param {string} message
 * @param {'success'|'error'|'info'|'warning'} [type='info']
 * @param {number} [durationMs]  - Override the auto-dismiss timeout.
 */
export function showToast(message, type = 'info', durationMs = DEFAULT_DURATION_MS) {
    const container = getContainer();

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;

    const dismiss = () => {
        if (!toast.isConnected) return;
        toast.classList.add('toast--leaving');
        toast.addEventListener('transitionend', () => toast.remove(), { once: true });
        // Safety: force-remove after the CSS transition window
        setTimeout(() => toast.remove(), 400);
    };

    toast.addEventListener('click', dismiss);
    container.appendChild(toast);

    // Force reflow then add the enter class so the CSS transition runs
    // eslint-disable-next-line no-unused-expressions
    toast.offsetHeight;
    toast.classList.add('toast--visible');

    if (durationMs > 0) {
        setTimeout(dismiss, durationMs);
    }

    return dismiss;
}
