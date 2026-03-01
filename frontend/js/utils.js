/**
 * utils.js — Shared formatting helpers for Jade.
 *
 * All currency is GBP, 2 decimal places.
 * All dates are ISO 8601 strings from the API.
 */

/**
 * Format a numeric amount as a GBP currency string.
 * Negative values are wrapped in a <span class="text-danger"> element.
 * Positive values are wrapped in a <span class="text-success"> element.
 *
 * @param {number} amount
 * @param {boolean} [coloured=true] - Apply success/danger colour class
 * @returns {string} HTML string, e.g. '<span class="text-success">£12.50</span>'
 */
export function formatCurrency(amount, coloured = true) {
    const abs = Math.abs(amount);
    const formatted = `£${abs.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`;
    const sign = amount < 0 ? '−' : '';  // typographic minus
    const value = `${sign}${formatted}`;

    if (!coloured) return value;

    const cls = amount >= 0 ? 'text-success' : 'text-danger';
    return `<span class="${cls} mono">${value}</span>`;
}

/**
 * Format an ISO 8601 date string as a human-readable date.
 * e.g. '2024-01-15T12:20:18Z' → '15 Jan 2024'
 *
 * @param {string} isoString
 * @returns {string}
 */
export function formatDate(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * Format an ISO 8601 date string as a short date.
 * e.g. '2024-01-15T12:20:18Z' → '15/01/24'
 *
 * @param {string} isoString
 * @returns {string}
 */
export function formatDateShort(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

/**
 * Escape a string for safe insertion as HTML text content.
 * Use this when building template literals that include user data.
 *
 * @param {string} str
 * @returns {string}
 */
export function escHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
