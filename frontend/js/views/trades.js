/**
 * trades.js — Trade log view (Phase 4.6).
 * Filterable, paginated table of all trades.
 */

import { api } from '../api.js';
import { formatCurrency, formatDateShort, escHtml } from '../utils.js';

// ---- Module-level state (reset on each render call) ----

let state = {
    page: 1,
    accountId: '',
    assetClass: '',
    symbol: '',
    strategyId: '',
    isOpen: '',
    direction: '',
};

let accountsCache = [];
let strategiesCache = [];
let symbolTimer = null;

// ---- Render entry point ----

export async function render(container) {
    // Reset state for fresh navigation
    state = {
        page: 1,
        accountId: '',
        assetClass: '',
        symbol: '',
        strategyId: '',
        isOpen: '',
        direction: '',
    };
    accountsCache = [];
    strategiesCache = [];

    container.innerHTML = `
        <div class="page-header flex items-center justify-between">
            <div>
                <h1>Trade Log</h1>
                <p class="text-secondary">Browse and filter your trading journal.</p>
            </div>
            <a href="#/trades/new" class="btn btn-primary">+ New Trade</a>
        </div>

        <!-- Filter bar -->
        <div class="card mb-4">
            <div class="flex gap-3 items-center" style="flex-wrap: wrap;">
                <select id="filter-account" style="min-width: 140px;">
                    <option value="">All accounts</option>
                </select>
                <select id="filter-asset-class" style="min-width: 130px;">
                    <option value="">All classes</option>
                    <option value="stocks">Stocks</option>
                    <option value="forex">Forex</option>
                    <option value="crypto">Crypto</option>
                    <option value="options">Options</option>
                </select>
                <input id="filter-symbol" type="search" placeholder="Symbol (e.g. AAPL)"
                    style="width: 160px;" value="">
                <select id="filter-strategy" style="min-width: 140px;">
                    <option value="">All strategies</option>
                </select>
                <select id="filter-status" style="min-width: 120px;">
                    <option value="">All trades</option>
                    <option value="1">Open</option>
                    <option value="0">Closed</option>
                </select>
                <select id="filter-direction" style="min-width: 110px;">
                    <option value="">Both sides</option>
                    <option value="long">Long</option>
                    <option value="short">Short</option>
                </select>
                <button id="btn-clear" class="btn btn-ghost">Clear</button>
            </div>
        </div>

        <!-- Table card -->
        <div class="card" id="table-card">
            <div class="table-container">
                <table id="trades-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Symbol</th>
                            <th>Class</th>
                            <th>Dir</th>
                            <th class="align-right">Entry Price</th>
                            <th class="align-right">P&amp;L (net)</th>
                            <th>Status</th>
                            <th>Strategy</th>
                            <th>Tags</th>
                        </tr>
                    </thead>
                    <tbody id="trades-body">
                        <tr><td colspan="9" class="loading" style="text-align:center;">Loading…</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Pagination -->
            <div id="pagination" class="flex items-center justify-between mt-4"
                 style="padding-top: var(--space-4); border-top: 1px solid var(--color-border);">
            </div>
        </div>
    `;

    attachListeners();
    await loadFilterData();
    await loadTrades();
}

// ---- Data loading ----

async function loadFilterData() {
    try {
        const [accData, stratData] = await Promise.all([
            api.get('/api/accounts/'),
            api.get('/api/strategies/'),
        ]);

        accountsCache = accData.accounts ?? [];
        strategiesCache = stratData.strategies ?? [];

        const accSel = document.getElementById('filter-account');
        if (accSel) {
            accountsCache.forEach(acc => {
                const opt = document.createElement('option');
                opt.value = acc.id;
                opt.textContent = acc.name;
                accSel.appendChild(opt);
            });
        }

        const stratSel = document.getElementById('filter-strategy');
        if (stratSel) {
            strategiesCache.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                stratSel.appendChild(opt);
            });
        }
    } catch {
        // Non-fatal — dropdowns just won't have dynamic options
    }
}

async function loadTrades() {
    const tbody = document.getElementById('trades-body');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="9" class="loading" style="text-align:center; padding: var(--space-7);">Loading…</td></tr>`;

    const params = new URLSearchParams({ page: state.page, per_page: 50 });
    if (state.accountId)  params.set('account_id',  state.accountId);
    if (state.assetClass) params.set('asset_class', state.assetClass);
    if (state.symbol)     params.set('symbol',      state.symbol.trim().toUpperCase());
    if (state.strategyId) params.set('strategy_id', state.strategyId);
    if (state.isOpen !== '') params.set('is_open',  state.isOpen);
    if (state.direction)  params.set('direction',   state.direction);

    try {
        const data = await api.get(`/api/trades/?${params}`);
        renderRows(data.trades ?? []);
        renderPagination(data);
    } catch (err) {
        tbody.innerHTML = `
            <tr><td colspan="9">
                <div class="error-state" style="margin: var(--space-4);">
                    <strong>Failed to load trades</strong>
                    <p class="mt-2">${escHtml(err.message)}</p>
                </div>
            </td></tr>`;
        const pag = document.getElementById('pagination');
        if (pag) pag.innerHTML = '';
    }
}

// ---- Rendering helpers ----

function strategyName(id) {
    if (!id) return '—';
    const s = strategiesCache.find(s => s.id === id);
    return s ? escHtml(s.name) : '—';
}

function renderRows(trades) {
    const tbody = document.getElementById('trades-body');
    if (!tbody) return;

    if (trades.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="9">
                <div class="empty-state" style="min-height: 160px;">
                    No trades found. Try adjusting your filters or <a href="#/trades/new">add your first trade</a>.
                </div>
            </td></tr>`;
        return;
    }

    tbody.innerHTML = trades.map(trade => {
        const dirClass = trade.direction === 'long' ? 'text-success' : 'text-danger';
        const dirLabel = trade.direction ? trade.direction.charAt(0).toUpperCase() + trade.direction.slice(1) : '—';

        const pnlHtml = trade.is_open
            ? '<span class="text-muted">—</span>'
            : (trade.pnl_net !== null && trade.pnl_net !== undefined
                ? formatCurrency(trade.pnl_net)
                : '<span class="text-muted">—</span>');

        const statusHtml = trade.is_open
            ? '<span class="badge badge-warning">Open</span>'
            : '<span class="badge badge-neutral">Closed</span>';

        const assetBadge = trade.asset_class
            ? `<span class="badge badge-neutral">${escHtml(trade.asset_class)}</span>`
            : '—';

        const tags = (trade.tags ?? []).slice(0, 3);
        const tagsHtml = tags.length
            ? tags.map(t => `<span class="badge badge-neutral" style="font-size:11px;">${escHtml(t.name)}</span>`).join(' ')
            : '';

        return `
            <tr data-id="${trade.id}">
                <td class="mono text-muted" style="white-space: nowrap;">${formatDateShort(trade.entry_date)}</td>
                <td class="mono" style="font-weight:500;">${escHtml(trade.symbol)}</td>
                <td>${assetBadge}</td>
                <td><span class="${dirClass}" style="font-weight:500;">${dirLabel}</span></td>
                <td class="td-right mono">${formatCurrency(trade.entry_price, false)}</td>
                <td class="td-right mono">${pnlHtml}</td>
                <td>${statusHtml}</td>
                <td class="text-secondary" style="font-size:13px;">${strategyName(trade.strategy_id)}</td>
                <td style="max-width:160px;">${tagsHtml}</td>
            </tr>
        `;
    }).join('');

    // TODO Phase 4.7: Click row to navigate to trade detail view
}

function renderPagination({ total, page, per_page, pages }) {
    const el = document.getElementById('pagination');
    if (!el) return;

    if (!total) {
        el.innerHTML = '';
        return;
    }

    const has_prev = page > 1;
    const has_next = page < pages;
    const start = (page - 1) * per_page + 1;
    const end   = Math.min(page * per_page, total);

    el.innerHTML = `
        <button id="btn-prev" class="btn btn-ghost" ${has_prev ? '' : 'disabled'}>← Prev</button>
        <span class="text-muted" style="font-size: 13px;">
            ${start}–${end} of ${total} trades
            &nbsp;·&nbsp; Page ${page} of ${pages}
        </span>
        <button id="btn-next" class="btn btn-ghost" ${has_next ? '' : 'disabled'}>Next →</button>
    `;

    document.getElementById('btn-prev').addEventListener('click', () => {
        state.page--;
        loadTrades();
    });
    document.getElementById('btn-next').addEventListener('click', () => {
        state.page++;
        loadTrades();
    });
}

// ---- Event listeners ----

function attachListeners() {
    // Account filter
    document.getElementById('filter-account').addEventListener('change', e => {
        state.accountId = e.target.value;
        state.page = 1;
        loadTrades();
    });

    // Asset class filter
    document.getElementById('filter-asset-class').addEventListener('change', e => {
        state.assetClass = e.target.value;
        state.page = 1;
        loadTrades();
    });

    // Symbol filter (debounced 300ms)
    document.getElementById('filter-symbol').addEventListener('input', e => {
        clearTimeout(symbolTimer);
        symbolTimer = setTimeout(() => {
            state.symbol = e.target.value.trim();
            state.page = 1;
            loadTrades();
        }, 300);
    });

    // Strategy filter
    document.getElementById('filter-strategy').addEventListener('change', e => {
        state.strategyId = e.target.value;
        state.page = 1;
        loadTrades();
    });

    // Status filter (open/closed)
    document.getElementById('filter-status').addEventListener('change', e => {
        state.isOpen = e.target.value;
        state.page = 1;
        loadTrades();
    });

    // Direction filter
    document.getElementById('filter-direction').addEventListener('change', e => {
        state.direction = e.target.value;
        state.page = 1;
        loadTrades();
    });

    // Clear all filters
    document.getElementById('btn-clear').addEventListener('click', () => {
        state = { ...state, page: 1, accountId: '', assetClass: '', symbol: '', strategyId: '', isOpen: '', direction: '' };
        document.getElementById('filter-account').value = '';
        document.getElementById('filter-asset-class').value = '';
        document.getElementById('filter-symbol').value = '';
        document.getElementById('filter-strategy').value = '';
        document.getElementById('filter-status').value = '';
        document.getElementById('filter-direction').value = '';
        loadTrades();
    });
}
