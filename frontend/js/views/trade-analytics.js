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

// Equity chart instance — cleaned up on each reload
let _chart = null;
let _resizeObserver = null;
// P&L distribution histogram — Chart.js instance, destroyed before each reload
let _histChart = null;
// R-multiple distribution histogram — Chart.js instance, destroyed before each reload
let _rDistChart = null;
// Win rate by strategy chart — Chart.js instance, destroyed before each reload
let _strategyChart = null;
// Discipline vs P&L scatter — Chart.js instance, destroyed before each reload
let _disciplineChart = null;

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
    if (data.summary.total_closed_trades > 0) {
        await Promise.all([
            loadEquityCurve(),
            loadPnlDistribution(),
            loadRDistribution(),
            loadWinRateByStrategy(),
            loadDisciplineScatter(),
        ]);
    }
}

// ---- Equity curve chart ----

async function loadEquityCurve() {
    if (_resizeObserver) { _resizeObserver.disconnect(); _resizeObserver = null; }
    if (_chart) { _chart.remove(); _chart = null; }

    const container = document.getElementById('equity-chart');
    if (!container) return;

    const params = new URLSearchParams();
    if (state.accountId)  params.set('account_id',  state.accountId);
    if (state.strategyId) params.set('strategy_id', state.strategyId);
    if (state.assetClass) params.set('asset_class', state.assetClass);
    if (state.startDate)  params.set('start_date',  state.startDate);
    if (state.endDate)    params.set('end_date',     state.endDate);

    const qs = params.toString();
    let points;
    try {
        const data = await api.get('/api/reports/equity-curve' + (qs ? '?' + qs : ''));
        points = data.points ?? [];
    } catch (err) {
        container.innerHTML = `<div class="error-state" style="min-height:0;padding:var(--space-3);">Unable to load equity curve: ${escHtml(err.message ?? 'Unknown error')}</div>`;
        return;
    }

    if (points.length === 0) {
        container.innerHTML = `<p class="text-muted" style="padding:var(--space-4);font-size:13px;">No data for the selected filters.</p>`;
        return;
    }

    if (typeof LightweightCharts === 'undefined') {
        container.innerHTML = `<p class="text-muted" style="padding:var(--space-4);font-size:13px;">Chart library not available.</p>`;
        return;
    }

    _chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 300,
        layout: {
            background: { color: '#1A1D27' },
            textColor: '#9CA3AF',
        },
        grid: {
            vertLines: { color: '#2E3140' },
            horzLines: { color: '#2E3140' },
        },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderColor: '#2E3140' },
        timeScale: { borderColor: '#2E3140' },
    });

    const series = _chart.addAreaSeries({
        lineColor: '#00A86B',
        topColor: 'rgba(0,168,107,0.3)',
        bottomColor: 'rgba(0,168,107,0.0)',
        priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    series.setData(points);
    _chart.timeScale().fitContent();

    _resizeObserver = new ResizeObserver(entries => {
        if (!_chart) return;
        _chart.applyOptions({ width: entries[0].contentRect.width });
    });
    _resizeObserver.observe(container);
}

// ---- P&L distribution histogram ----

async function loadPnlDistribution() {
    if (_histChart) { _histChart.destroy(); _histChart = null; }

    const container = document.getElementById('pnl-dist-chart');
    if (!container) return;

    const params = new URLSearchParams();
    if (state.accountId)  params.set('account_id',  state.accountId);
    if (state.strategyId) params.set('strategy_id', state.strategyId);
    if (state.assetClass) params.set('asset_class', state.assetClass);
    if (state.startDate)  params.set('start_date',  state.startDate);
    if (state.endDate)    params.set('end_date',     state.endDate);

    const qs = params.toString();
    let bins;
    try {
        const data = await api.get('/api/reports/pnl-distribution' + (qs ? '?' + qs : ''));
        bins = data.bins ?? [];
    } catch (err) {
        container.innerHTML = `<div class="error-state" style="min-height:0;padding:var(--space-3);">Unable to load P&L distribution: ${escHtml(err.message ?? 'Unknown error')}</div>`;
        return;
    }

    if (bins.length === 0) {
        container.innerHTML = `<p class="text-muted" style="padding:var(--space-4);font-size:13px;">No data for the selected filters.</p>`;
        return;
    }

    // Colour each bar by sign of its midpoint
    function _binColor(midpoint) {
        if (midpoint < 0) return '#EF4444';
        if (midpoint > 0) return '#10B981';
        return '#F59E0B';
    }

    // Ensure canvas exists inside the container
    let canvas = container.querySelector('canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'pnl-dist-canvas';
        container.innerHTML = '';
        container.appendChild(canvas);
    }

    Chart.defaults.color = '#9CA3AF';
    Chart.defaults.borderColor = '#2E3140';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

    _histChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: bins.map(b => b.label),
            datasets: [{
                label: 'Trades',
                data: bins.map(b => b.count),
                backgroundColor: bins.map(b => _binColor(b.midpoint)),
                borderColor:     bins.map(b => _binColor(b.midpoint)),
                borderWidth: 1,
                borderRadius: 3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title(items) { return items[0].label; },
                        label(item) {
                            const n = item.parsed.y;
                            return `${n} trade${n === 1 ? '' : 's'}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, font: { size: 11 } },
                },
                y: {
                    grid: { color: '#2E3140' },
                    ticks: { stepSize: 1, precision: 0 },
                    beginAtZero: true,
                },
            },
        },
    });
}

async function loadRDistribution() {
    if (_rDistChart) { _rDistChart.destroy(); _rDistChart = null; }

    const container = document.getElementById('r-dist-chart');
    if (!container) return;

    const params = new URLSearchParams();
    if (state.accountId)  params.set('account_id',  state.accountId);
    if (state.strategyId) params.set('strategy_id', state.strategyId);
    if (state.assetClass) params.set('asset_class', state.assetClass);
    if (state.startDate)  params.set('start_date',  state.startDate);
    if (state.endDate)    params.set('end_date',     state.endDate);

    const qs = params.toString();
    let bins;
    try {
        const data = await api.get('/api/reports/r-distribution' + (qs ? '?' + qs : ''));
        bins = data.bins ?? [];
    } catch (err) {
        container.innerHTML = `<div class="error-state" style="min-height:0;padding:var(--space-3);">Unable to load R-multiple distribution: ${escHtml(err.message ?? 'Unknown error')}</div>`;
        return;
    }

    if (bins.length === 0) {
        container.innerHTML = `<p class="text-muted" style="padding:var(--space-4);font-size:13px;">No R-multiple data for the selected filters. Set a risk amount on trades to enable this chart.</p>`;
        return;
    }

    function _binColor(midpoint) {
        if (midpoint < 0) return '#EF4444';
        if (midpoint > 0) return '#10B981';
        return '#F59E0B';
    }

    let canvas = container.querySelector('canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'r-dist-canvas';
        container.innerHTML = '';
        container.appendChild(canvas);
    }

    Chart.defaults.color = '#9CA3AF';
    Chart.defaults.borderColor = '#2E3140';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

    _rDistChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: bins.map(b => b.label),
            datasets: [{
                label: 'Trades',
                data: bins.map(b => b.count),
                backgroundColor: bins.map(b => _binColor(b.midpoint)),
                borderColor:     bins.map(b => _binColor(b.midpoint)),
                borderWidth: 1,
                borderRadius: 3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title(items) { return items[0].label; },
                        label(item) {
                            const n = item.parsed.y;
                            return `${n} trade${n === 1 ? '' : 's'}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, font: { size: 11 } },
                },
                y: {
                    grid: { color: '#2E3140' },
                    ticks: { stepSize: 1, precision: 0 },
                    beginAtZero: true,
                },
            },
        },
    });
}

// ---- Win rate by strategy chart ----

async function loadWinRateByStrategy() {
    if (_strategyChart) { _strategyChart.destroy(); _strategyChart = null; }

    const container = document.getElementById('strategy-chart');
    if (!container) return;

    const params = new URLSearchParams();
    if (state.accountId)  params.set('account_id',  state.accountId);
    if (state.strategyId) params.set('strategy_id', state.strategyId);
    if (state.assetClass) params.set('asset_class', state.assetClass);
    if (state.startDate)  params.set('start_date',  state.startDate);
    if (state.endDate)    params.set('end_date',     state.endDate);

    const qs = params.toString();
    let strategies;
    try {
        const data = await api.get('/api/reports/win-rate-by-strategy' + (qs ? '?' + qs : ''));
        strategies = data.strategies ?? [];
    } catch (err) {
        container.innerHTML = `<div class="error-state" style="min-height:0;padding:var(--space-3);">Unable to load win rate by strategy: ${escHtml(err.message ?? 'Unknown error')}</div>`;
        return;
    }

    if (strategies.length === 0) {
        container.innerHTML = `<p class="text-muted" style="padding:var(--space-4);font-size:13px;">No strategy data for the selected filters.</p>`;
        return;
    }

    function _barColor(winRate) {
        if (winRate >= 60) return '#10B981';
        if (winRate >= 40) return '#F59E0B';
        return '#EF4444';
    }

    const height = Math.max(200, strategies.length * 52);
    container.style.height = height + 'px';

    let canvas = container.querySelector('canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'strategy-canvas';
        container.innerHTML = '';
        container.appendChild(canvas);
    }

    Chart.defaults.color = '#9CA3AF';
    Chart.defaults.borderColor = '#2E3140';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

    _strategyChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: strategies.map(s => s.strategy_name),
            datasets: [{
                label: 'Win Rate',
                data: strategies.map(s => s.win_rate),
                backgroundColor: strategies.map(s => _barColor(s.win_rate)),
                borderColor:     strategies.map(s => _barColor(s.win_rate)),
                borderWidth: 1,
                borderRadius: 3,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title(items) { return items[0].label; },
                        label(item) {
                            const s = strategies[item.dataIndex];
                            return `${s.wins}W / ${s.losses}L / ${s.total} trades — ${s.win_rate}%`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    min: 0,
                    max: 100,
                    grid: { color: '#2E3140' },
                    ticks: { callback: v => v + '%', font: { size: 11 } },
                    title: { display: true, text: 'Win Rate (%)', color: '#6B7280', font: { size: 11 } },
                },
                y: {
                    grid: { display: false },
                    ticks: { font: { size: 12 } },
                },
            },
        },
    });
}

// ---- Discipline vs P&L scatter chart ----

async function loadDisciplineScatter() {
    if (_disciplineChart) { _disciplineChart.destroy(); _disciplineChart = null; }

    const container = document.getElementById('discipline-scatter-chart');
    if (!container) return;

    const params = new URLSearchParams();
    if (state.accountId)  params.set('account_id',  state.accountId);
    if (state.strategyId) params.set('strategy_id', state.strategyId);
    if (state.assetClass) params.set('asset_class', state.assetClass);
    if (state.startDate)  params.set('start_date',  state.startDate);
    if (state.endDate)    params.set('end_date',     state.endDate);

    const qs = params.toString();
    let points;
    try {
        const data = await api.get('/api/reports/discipline-scatter' + (qs ? '?' + qs : ''));
        points = data.points ?? [];
    } catch (err) {
        container.innerHTML = `<div class="error-state" style="min-height:0;padding:var(--space-3);">Unable to load discipline scatter: ${escHtml(err.message ?? 'Unknown error')}</div>`;
        return;
    }

    if (points.length === 0) {
        container.innerHTML = `<p class="text-muted" style="padding:var(--space-4);font-size:13px;">No discipline data for the selected filters. Record rules followed % on trades to enable this chart.</p>`;
        return;
    }

    function _pointColor(pnl) {
        if (pnl > 0) return '#10B981';
        if (pnl < 0) return '#EF4444';
        return '#F59E0B';
    }

    let canvas = container.querySelector('canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'discipline-scatter-canvas';
        container.innerHTML = '';
        container.appendChild(canvas);
    }

    Chart.defaults.color = '#9CA3AF';
    Chart.defaults.borderColor = '#2E3140';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

    _disciplineChart = new Chart(canvas.getContext('2d'), {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Trades',
                data: points,
                backgroundColor: points.map(p => _pointColor(p.y)),
                borderColor:     points.map(p => _pointColor(p.y)),
                borderWidth: 1,
                pointRadius: 5,
                pointHoverRadius: 7,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title(items) {
                            const p = points[items[0].dataIndex];
                            return `${escHtml(p.symbol ?? '—')} — ${p.exit_date}`;
                        },
                        label(item) {
                            const p = points[item.dataIndex];
                            const pnlStr = (p.y >= 0 ? '+' : '') + '£' + p.y.toFixed(2);
                            const rStr = (p.r_multiple !== null && p.r_multiple !== undefined)
                                ? `  ${p.r_multiple >= 0 ? '+' : ''}${p.r_multiple.toFixed(2)}R`
                                : '';
                            return [
                                `Discipline: ${p.x.toFixed(0)}%`,
                                `P&L: ${pnlStr}${rStr}`,
                            ];
                        },
                    },
                },
            },
            scales: {
                x: {
                    min: 0,
                    max: 100,
                    grid: { color: '#2E3140' },
                    ticks: { callback: v => v + '%', font: { size: 11 } },
                    title: { display: true, text: 'Rules Followed (%)', color: '#6B7280', font: { size: 11 } },
                },
                y: {
                    grid: { color: '#2E3140' },
                    ticks: { callback: v => '£' + v.toFixed(0), font: { size: 11 } },
                    title: { display: true, text: 'Net P&L (£)', color: '#6B7280', font: { size: 11 } },
                },
            },
        },
    });
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

        <!-- Equity curve -->
        <div class="card mb-4" id="equity-curve-card">
            <div class="card-title">Equity Curve</div>
            <div id="equity-chart" style="height: 300px; margin-top: var(--space-4);"></div>
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

        <!-- P&L Distribution histogram -->
        <div class="card mb-4">
            <div class="card-title">P&amp;L Distribution</div>
            <div id="pnl-dist-chart" style="position: relative; height: 260px; margin-top: var(--space-4);">
                <canvas id="pnl-dist-canvas"></canvas>
            </div>
        </div>

        <!-- R-Multiple Distribution histogram -->
        <div class="card mb-4">
            <div class="card-title">R-Multiple Distribution</div>
            <div id="r-dist-chart" style="position: relative; height: 260px; margin-top: var(--space-4);">
                <canvas id="r-dist-canvas"></canvas>
            </div>
        </div>

        <!-- Win Rate by Strategy -->
        <div class="card mb-4">
            <div class="card-title">Win Rate by Strategy</div>
            <div id="strategy-chart" style="position: relative; margin-top: var(--space-4);"></div>
        </div>

        <!-- Discipline vs P&L Scatter -->
        <div class="card mb-4">
            <div class="card-title">Discipline vs Performance</div>
            <div id="discipline-scatter-chart" style="position: relative; height: 320px; margin-top: var(--space-4);">
                <canvas id="discipline-scatter-canvas"></canvas>
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
