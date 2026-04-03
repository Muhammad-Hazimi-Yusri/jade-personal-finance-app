/**
 * trade-analytics.js — Trading analytics dashboard (Phase 5.3).
 * KPI cards: win rate, profit factor, expectancy, max drawdown, and more.
 */

import { api } from '../api.js';
import { formatCurrency, escHtml } from '../utils.js';

// ---- Module-level state ----

let state = {
    accountId: '',
    strategyId: '',
    assetClass: '',
    startDate: '',
    endDate: '',
};

// ---- Render entry point ----

export async function render(container) {
    state = { accountId: '', strategyId: '', assetClass: '', startDate: '', endDate: '' };

    container.innerHTML = `
        <div class="page-header">
            <h1>Analytics</h1>
            <p class="text-secondary">Aggregate performance metrics across your trading activity.</p>
        </div>

        <!-- Filter bar -->
        <div class="card mb-4">
            <div class="flex gap-3 items-center" style="flex-wrap: wrap;">
                <select id="filter-account" style="min-width: 140px;">
                    <option value="">All accounts</option>
                </select>
                <select id="filter-strategy" style="min-width: 150px;">
                    <option value="">All strategies</option>
                </select>
                <select id="filter-asset-class" style="min-width: 130px;">
                    <option value="">All classes</option>
                    <option value="stocks">Stocks</option>
                    <option value="forex">Forex</option>
                    <option value="crypto">Crypto</option>
                    <option value="options">Options</option>
                </select>
                <input id="filter-start" type="date" style="width: 140px;" title="From date">
                <input id="filter-end"   type="date" style="width: 140px;" title="To date">
                <button id="btn-apply" class="btn btn-primary">Apply</button>
                <button id="btn-clear"  class="btn btn-ghost">Clear</button>
            </div>
        </div>

        <!-- Dashboard content -->
        <div id="analytics-content">
            <div class="loading" style="text-align: center; min-height: 200px;">Loading…</div>
        </div>
    `;

    attachListeners();
    await loadFilterData();
    await loadMetrics();
}

// ---- Event listeners ----

function attachListeners() {
    document.getElementById('btn-apply').addEventListener('click', async () => {
        state.accountId   = document.getElementById('filter-account').value;
        state.strategyId  = document.getElementById('filter-strategy').value;
        state.assetClass  = document.getElementById('filter-asset-class').value;
        state.startDate   = document.getElementById('filter-start').value;
        state.endDate     = document.getElementById('filter-end').value;
        await loadMetrics();
    });

    document.getElementById('btn-clear').addEventListener('click', async () => {
        state = { accountId: '', strategyId: '', assetClass: '', startDate: '', endDate: '' };
        document.getElementById('filter-account').value    = '';
        document.getElementById('filter-strategy').value   = '';
        document.getElementById('filter-asset-class').value = '';
        document.getElementById('filter-start').value      = '';
        document.getElementById('filter-end').value        = '';
        await loadMetrics();
    });
}

// ---- Load dropdown data ----

async function loadFilterData() {
    try {
        const [accData, stratData] = await Promise.all([
            api.get('/api/accounts/'),
            api.get('/api/strategies/'),
        ]);

        const accSel = document.getElementById('filter-account');
        (accData.accounts ?? []).forEach(acc => {
            const opt = document.createElement('option');
            opt.value = acc.id;
            opt.textContent = escHtml(acc.name);
            accSel.appendChild(opt);
        });

        const stratSel = document.getElementById('filter-strategy');
        (stratData.strategies ?? []).forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = escHtml(s.name);
            stratSel.appendChild(opt);
        });
    } catch (_) {
        // Non-fatal — dropdowns stay empty
    }
}

// ---- Load and render metrics ----

async function loadMetrics() {
    const content = document.getElementById('analytics-content');
    content.innerHTML = `<div class="loading" style="text-align: center; min-height: 200px;">Loading…</div>`;

    const params = new URLSearchParams();
    if (state.accountId)  params.set('account_id',  state.accountId);
    if (state.strategyId) params.set('strategy_id', state.strategyId);
    if (state.assetClass) params.set('asset_class', state.assetClass);
    if (state.startDate)  params.set('start_date',  state.startDate);
    if (state.endDate)    params.set('end_date',     state.endDate);

    const qs = params.toString();
    const url = '/api/reports/trading-performance' + (qs ? '?' + qs : '');

    let data;
    try {
        data = await api.get(url);
    } catch (err) {
        content.innerHTML = `
            <div class="error-state">
                <p>Failed to load analytics: ${escHtml(err.message ?? 'Unknown error')}</p>
            </div>`;
        return;
    }

    content.innerHTML = renderDashboard(data);
}

// ---- Dashboard HTML ----

function renderDashboard(data) {
    const { summary, metrics } = data;
    const total = summary.total_closed_trades;

    if (total === 0) {
        return `
            <div class="empty-state">
                <p class="text-muted">No closed trades match the selected filters.</p>
                <p class="text-secondary" style="font-size: 13px;">Close some trades to see performance metrics here.</p>
            </div>`;
    }

    return `
        <!-- Summary strip -->
        <div class="card mb-4">
            <div class="flex gap-4 items-center" style="flex-wrap: wrap;">
                ${summaryPill('Closed trades', total)}
                ${summaryPill('Wins',      summary.winning_trades,  'text-success')}
                ${summaryPill('Losses',    summary.losing_trades,   'text-danger')}
                ${summaryPill('Breakeven', summary.breakeven_trades)}
            </div>
        </div>

        <!-- Primary KPIs -->
        <div class="card mb-4">
            <div class="card-title">Core metrics</div>
            <div class="grid-4" style="margin-top: var(--space-4);">
                ${kpiCard('Win Rate',       winRateHtml(metrics.win_rate))}
                ${kpiCard('Profit Factor',  profitFactorHtml(metrics.profit_factor))}
                ${kpiCard('Expectancy',     expectancyHtml(metrics.expectancy))}
                ${kpiCard('Max Drawdown',   drawdownHtml(metrics.max_drawdown_pct))}
            </div>
        </div>

        <!-- Secondary KPIs -->
        <div class="card mb-4">
            <div class="card-title">R & streaks</div>
            <div class="grid-4" style="margin-top: var(--space-4);">
                ${kpiCard('Avg R-Multiple',      rMultipleHtml(metrics.avg_r_multiple))}
                ${kpiCard('Discipline Score',    disciplineHtml(metrics.discipline_score))}
                ${kpiCard('Max Win Streak',      streakHtml(metrics.max_consecutive_wins, 'wins'))}
                ${kpiCard('Max Loss Streak',     streakHtml(metrics.max_consecutive_losses, 'losses'))}
            </div>
        </div>

        <!-- Trade P&L breakdown -->
        <div class="card">
            <div class="card-title">P&amp;L breakdown</div>
            <div class="grid-4" style="margin-top: var(--space-4);">
                ${kpiCard('Avg Win',      moneyHtml(metrics.avg_win,      true))}
                ${kpiCard('Avg Loss',     moneyHtml(metrics.avg_loss,     false))}
                ${kpiCard('Largest Win',  moneyHtml(metrics.largest_win,  true))}
                ${kpiCard('Largest Loss', moneyHtml(metrics.largest_loss, false))}
            </div>
        </div>
    `;
}

// ---- Formatting helpers ----

const DASH = '<span class="text-muted">—</span>';

function kpiCard(label, valueHtml) {
    return `
        <div class="kpi-card">
            <div class="kpi-card__label">${label}</div>
            <div class="kpi-card__value">${valueHtml}</div>
        </div>`;
}

function summaryPill(label, value, cls = '') {
    return `
        <div class="flex gap-2 items-center">
            <span class="text-muted" style="font-size: 13px;">${label}:</span>
            <span class="mono ${cls}" style="font-size: 15px; font-weight: 600;">${value}</span>
        </div>`;
}

function winRateHtml(v) {
    if (v === null || v === undefined) return DASH;
    const cls = v >= 50 ? 'text-success' : v >= 40 ? 'text-warning' : 'text-danger';
    return `<span class="${cls}">${v.toFixed(1)}%</span>`;
}

function profitFactorHtml(v) {
    if (v === null || v === undefined) return DASH;
    // If losses were zero the backend may return a very large number
    if (v > 999) return `<span class="text-success">∞</span>`;
    const cls = v >= 1 ? 'text-success' : 'text-danger';
    return `<span class="${cls}">${v.toFixed(2)}</span>`;
}

function expectancyHtml(v) {
    if (v === null || v === undefined) return DASH;
    return formatCurrency(v, true);
}

function drawdownHtml(v) {
    if (v === null || v === undefined) return DASH;
    const cls = v <= 5 ? 'text-success' : v <= 15 ? 'text-warning' : 'text-danger';
    return `<span class="${cls}">${v.toFixed(1)}%</span>`;
}

function rMultipleHtml(v) {
    if (v === null || v === undefined) return DASH;
    const cls = v >= 0 ? 'text-success' : 'text-danger';
    return `<span class="${cls}">${v.toFixed(2)}R</span>`;
}

function disciplineHtml(v) {
    if (v === null || v === undefined) return DASH;
    const cls = v >= 80 ? 'text-success' : v >= 60 ? 'text-warning' : 'text-danger';
    return `<span class="${cls}">${v.toFixed(0)}%</span>`;
}

function streakHtml(v, _type) {
    if (v === null || v === undefined || v === 0) return `<span class="text-muted">0</span>`;
    return `<span>${v}</span>`;
}

function moneyHtml(v, isPositive) {
    if (v === null || v === undefined) return DASH;
    return formatCurrency(v, true);
}
