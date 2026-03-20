/**
 * transactions.js — Transactions list view (Phase 1.6 + 2.5).
 * Paginated, sortable, filterable transaction list.
 * Supports post-import review mode with highlighted rows.
 */

import { api } from '../api.js';
import { formatCurrency, formatDateShort, escHtml } from '../utils.js';

// ---- Module-level state (reset on each render call) ----

let state = {
    page: 1,
    sort: 'date',
    order: 'desc',
    search: '',
    category: '',
    startDate: '',
    endDate: '',
};

let categoriesCache = [];
let searchTimer = null;

/** @type {Set<number>|null} IDs of recently imported transactions */
let importIds = null;
/** Whether to filter to only imported transactions (true) or show all with highlights (false) */
let importReviewMode = false;

// ---- Import review helpers ----

function loadImportReview() {
    const raw = sessionStorage.getItem('import_review');
    if (!raw) { importIds = null; importReviewMode = false; return; }
    try {
        const data = JSON.parse(raw);
        if (data.ids && data.ids.length > 0) {
            importIds = new Set(data.ids);
            importReviewMode = !!data.reviewMode;
        } else {
            importIds = null;
            importReviewMode = false;
        }
    } catch {
        importIds = null;
        importReviewMode = false;
    }
}

function saveImportReview() {
    if (!importIds || importIds.size === 0) {
        sessionStorage.removeItem('import_review');
        return;
    }
    sessionStorage.setItem('import_review', JSON.stringify({
        ids: [...importIds],
        reviewMode: importReviewMode,
    }));
}

function dismissImportReview() {
    importIds = null;
    importReviewMode = false;
    sessionStorage.removeItem('import_review');
    const banner = document.getElementById('import-review-banner');
    if (banner) banner.remove();
    loadTransactions();
}

function showAllTransactions() {
    importReviewMode = false;
    saveImportReview();
    state.page = 1;
    state.sort = 'date';
    state.order = 'desc';
    renderBanner();
    loadTransactions();
}

// ---- Render entry point ----

export async function render(container) {
    // Reset state for fresh navigation
    state = { page: 1, sort: 'date', order: 'desc',
              search: '', category: '', startDate: '', endDate: '' };
    categoriesCache = [];

    // Check for pending import review
    loadImportReview();

    // In review mode, sort by newest first (created_at)
    if (importReviewMode) {
        state.sort = 'created_at';
        state.order = 'desc';
    }

    container.innerHTML = `
        <div class="page-header flex items-center justify-between">
            <div>
                <h1>Transactions</h1>
                <p class="text-secondary">Browse, search, and filter your transactions.</p>
            </div>
            <a href="#/transactions/new" class="btn btn-primary">+ Add Transaction</a>
        </div>

        <div id="banner-slot"></div>

        <!-- Filter bar -->
        <div class="card mb-4" id="filter-card">
            <div class="flex gap-3 items-center" style="flex-wrap: wrap;">
                <input id="filter-search" type="search" placeholder="Search name, notes…"
                    style="flex: 1; min-width: 160px;" value="">
                <select id="filter-cat" style="min-width: 160px;">
                    <option value="">All categories</option>
                </select>
                <input id="filter-start" type="date" style="width: 148px;" title="From date">
                <input id="filter-end" type="date" style="width: 148px;" title="To date">
                <button id="btn-clear" class="btn btn-ghost">Clear</button>
            </div>
        </div>

        <!-- Table card -->
        <div class="card" id="table-card">
            <div class="table-container">
                <table id="tx-table">
                    <thead>
                        <tr>
                            <th data-col="date" class="sortable">Date</th>
                            <th data-col="name" class="sortable">Name</th>
                            <th data-col="category" class="sortable">Category</th>
                            <th data-col="amount" class="sortable align-right">Amount</th>
                        </tr>
                    </thead>
                    <tbody id="tx-body">
                        <tr><td colspan="4" class="loading" style="text-align:center;">Loading…</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Pagination -->
            <div id="pagination" class="flex items-center justify-between mt-4"
                 style="padding-top: var(--space-4); border-top: 1px solid var(--color-border);">
            </div>
        </div>
    `;

    renderBanner();
    addSortableHeaderStyles();
    attachListeners();

    await loadCategories();
    await loadTransactions();
}

// ---- Import review banner ----

function renderBanner() {
    const slot = document.getElementById('banner-slot');
    if (!slot) return;

    // Clear any existing banner
    slot.innerHTML = '';

    if (!importIds || importIds.size === 0) return;

    const count = importIds.size;

    if (importReviewMode) {
        slot.innerHTML = `
            <div class="import-review-banner" id="import-review-banner">
                <div class="import-review-banner__text">
                    Reviewing <strong>${count}</strong> imported transaction${count !== 1 ? 's' : ''}
                </div>
                <div class="import-review-banner__actions">
                    <button class="btn btn-ghost btn-sm" id="btn-show-all">Show All Transactions</button>
                    <button class="btn btn-ghost btn-sm" id="btn-dismiss-review">Dismiss</button>
                </div>
            </div>
        `;
    } else {
        slot.innerHTML = `
            <div class="import-review-banner import-review-banner--highlight" id="import-review-banner">
                <div class="import-review-banner__text">
                    <strong>${count}</strong> recently imported transaction${count !== 1 ? 's' : ''} highlighted
                </div>
                <div class="import-review-banner__actions">
                    <button class="btn btn-ghost btn-sm" id="btn-dismiss-review">Dismiss</button>
                </div>
            </div>
        `;
    }

    // Attach banner button listeners
    const btnShowAll = document.getElementById('btn-show-all');
    if (btnShowAll) btnShowAll.addEventListener('click', showAllTransactions);

    const btnDismiss = document.getElementById('btn-dismiss-review');
    if (btnDismiss) btnDismiss.addEventListener('click', dismissImportReview);
}

// ---- Data loading ----

async function loadCategories() {
    try {
        const data = await api.get('/api/categories/');
        categoriesCache = data.categories ?? [];
        const sel = document.getElementById('filter-cat');
        if (!sel) return;
        categoriesCache.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.name;
            opt.textContent = cat.display_name;
            sel.appendChild(opt);
        });
    } catch {
        // Non-fatal — filter still works, category names just show raw values
    }
}

async function loadTransactions() {
    const tbody = document.getElementById('tx-body');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="4" class="loading" style="text-align:center; padding: var(--space-7);">Loading…</td></tr>`;
    updateSortHeaders();

    const params = new URLSearchParams({ page: state.page, per_page: 50,
                                         sort: state.sort, order: state.order });
    if (state.search)    params.set('search',     state.search);
    if (state.category)  params.set('category',   state.category);
    if (state.startDate) params.set('start_date', state.startDate);
    if (state.endDate)   params.set('end_date',   state.endDate);

    // In review mode, filter to only imported IDs
    if (importReviewMode && importIds && importIds.size > 0) {
        params.set('ids', [...importIds].join(','));
    }

    try {
        const data = await api.get(`/api/transactions?${params}`);
        renderRows(data.transactions ?? []);
        renderPagination(data.pagination ?? {});
    } catch (err) {
        tbody.innerHTML = `
            <tr><td colspan="4">
                <div class="error-state" style="margin: var(--space-4);">
                    <strong>Failed to load transactions</strong>
                    <p class="mt-2">${escHtml(err.message)}</p>
                </div>
            </td></tr>`;
        document.getElementById('pagination').innerHTML = '';
    }
}

// ---- Rendering helpers ----

function categoryDisplayName(name) {
    const cat = categoriesCache.find(c => c.name === name);
    return cat ? escHtml(cat.display_name) : escHtml(name ?? '—');
}

function renderRows(transactions) {
    const tbody = document.getElementById('tx-body');
    if (!tbody) return;

    if (transactions.length === 0) {
        const msg = importReviewMode
            ? 'No imported transactions found.'
            : 'No transactions found. Try adjusting your filters.';
        tbody.innerHTML = `
            <tr><td colspan="4">
                <div class="empty-state" style="min-height: 160px;">
                    ${msg}
                </div>
            </td></tr>`;
        return;
    }

    const shouldHighlight = importIds && importIds.size > 0 && !importReviewMode;

    tbody.innerHTML = transactions.map(tx => {
        const isImported = shouldHighlight && importIds.has(tx.id);
        const rowClass = isImported ? 'tx-row-clickable tx-row--imported' : 'tx-row-clickable';
        const newBadge = isImported ? '<span class="badge-new">NEW</span>' : '';
        return `
            <tr data-id="${tx.id}" class="${rowClass}">
                <td class="mono text-muted" style="white-space: nowrap;">${formatDateShort(tx.date)}${newBadge}</td>
                <td>${escHtml(tx.name)}</td>
                <td><span class="badge badge-neutral">${categoryDisplayName(tx.category)}</span></td>
                <td class="td-right">${formatCurrency(tx.amount)}</td>
            </tr>
        `;
    }).join('');

    // Click row to edit
    tbody.querySelectorAll('tr[data-id]').forEach(row => {
        row.addEventListener('click', () => {
            window.location.hash = `#/transactions/edit/${row.dataset.id}`;
        });
    });
}

function renderPagination(pg) {
    const el = document.getElementById('pagination');
    if (!el) return;

    if (!pg.total) {
        el.innerHTML = '';
        return;
    }

    const start = (pg.page - 1) * pg.per_page + 1;
    const end   = Math.min(pg.page * pg.per_page, pg.total);

    el.innerHTML = `
        <button id="btn-prev" class="btn btn-ghost" ${pg.has_prev ? '' : 'disabled'}>← Prev</button>
        <span class="text-muted" style="font-size: 13px;">
            ${start}–${end} of ${pg.total} transactions
            &nbsp;·&nbsp; Page ${pg.page} of ${pg.total_pages}
        </span>
        <button id="btn-next" class="btn btn-ghost" ${pg.has_next ? '' : 'disabled'}>Next →</button>
    `;

    document.getElementById('btn-prev').addEventListener('click', () => {
        state.page--;
        loadTransactions();
    });
    document.getElementById('btn-next').addEventListener('click', () => {
        state.page++;
        loadTransactions();
    });
}

// ---- Sort headers ----

function updateSortHeaders() {
    document.querySelectorAll('#tx-table thead th[data-col]').forEach(th => {
        const col = th.dataset.col;
        const existing = th.querySelector('.sort-indicator');
        if (existing) existing.remove();

        if (col === state.sort) {
            const span = document.createElement('span');
            span.className = 'sort-indicator';
            span.textContent = state.order === 'asc' ? ' ↑' : ' ↓';
            span.style.color = 'var(--color-primary)';
            th.appendChild(span);
            th.style.color = 'var(--color-primary)';
        } else {
            th.style.color = '';
        }
    });
}

// ---- Event listeners ----

function attachListeners() {
    // Sort header clicks
    document.querySelectorAll('#tx-table thead th[data-col]').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.col;
            if (col === state.sort) {
                state.order = state.order === 'desc' ? 'asc' : 'desc';
            } else {
                state.sort  = col;
                state.order = 'desc';
            }
            state.page = 1;
            loadTransactions();
        });
    });

    // Search (debounced 300ms)
    document.getElementById('filter-search').addEventListener('input', e => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.search = e.target.value.trim();
            state.page = 1;
            loadTransactions();
        }, 300);
    });

    // Category select
    document.getElementById('filter-cat').addEventListener('change', e => {
        state.category = e.target.value;
        state.page = 1;
        loadTransactions();
    });

    // Date range
    document.getElementById('filter-start').addEventListener('change', e => {
        state.startDate = e.target.value;
        state.page = 1;
        loadTransactions();
    });
    document.getElementById('filter-end').addEventListener('change', e => {
        state.endDate = e.target.value;
        state.page = 1;
        loadTransactions();
    });

    // Clear filters
    document.getElementById('btn-clear').addEventListener('click', () => {
        state = { ...state, page: 1, search: '', category: '',
                  startDate: '', endDate: '' };
        document.getElementById('filter-search').value = '';
        document.getElementById('filter-cat').value = '';
        document.getElementById('filter-start').value = '';
        document.getElementById('filter-end').value = '';
        loadTransactions();
    });
}

// ---- One-time style injection for sortable headers ----

function addSortableHeaderStyles() {
    if (document.getElementById('tx-sort-styles')) return;
    const style = document.createElement('style');
    style.id = 'tx-sort-styles';
    style.textContent = `
        #tx-table thead th[data-col] {
            cursor: pointer;
            user-select: none;
        }
        #tx-table thead th[data-col]:hover {
            color: var(--color-text);
        }
    `;
    document.head.appendChild(style);
}
