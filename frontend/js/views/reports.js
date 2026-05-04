/**
 * reports.js — Spending reports view (Phase 3.8).
 * Compares spending between the current and previous month,
 * with a category-level breakdown chart and comparison table.
 */

import { api } from '../api.js';
import { formatCurrency, escHtml } from '../utils.js';
import { createDateRangeSelector, getPresetRange } from '../components/date-range-selector.js';

// Module state
let data = null;
let categories = [];
let chart = null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _destroyChart() {
    chart?.destroy();
    chart = null;
}

function _categoryDisplayName(name) {
    const cat = categories.find(c => c.name === name);
    return cat ? (cat.icon ? cat.icon + ' ' : '') + cat.display_name : name;
}

function _changeClass(change) {
    if (change > 0) return 'change-positive';   // spending UP = bad
    if (change < 0) return 'change-negative';    // spending DOWN = good
    return 'change-neutral';
}

function _changeArrow(change) {
    if (change > 0) return '▲';
    if (change < 0) return '▼';
    return '—';
}

function _formatPct(pct) {
    if (pct === null || pct === undefined) return 'New';
    return `${pct > 0 ? '+' : ''}${pct}%`;
}

function _formatAxis(value) {
    return '£' + Number(value).toLocaleString('en-GB');
}

// ---------------------------------------------------------------------------
// Render entry point
// ---------------------------------------------------------------------------

export async function render(container) {
    _destroyChart();

    container.innerHTML = `
        <div class="page-header">
            <h1>Spending Reports</h1>
            <p>Compare spending between periods</p>
        </div>

        <div id="report-date-range-mount"></div>

        <div id="report-loading" class="loading">Loading report…</div>
        <div id="report-error" class="error-state" style="display:none"></div>
        <div id="report-empty" class="empty-state" style="display:none">
            <p class="text-muted">No spending data to compare. Import transactions or wait until next month for comparison data.</p>
        </div>

        <div id="report-content" style="display:none">
            <div class="report-kpi-grid" id="report-kpis"></div>

            <div class="card">
                <div class="card-title">Spending by Category — <span id="report-period-label"></span></div>
                <div class="chart-wrap">
                    <canvas id="chart-comparison"></canvas>
                </div>
                <p id="chart-empty" class="text-muted" style="display:none;text-align:center;margin-top:16px;">No category data to chart.</p>
            </div>

            <div class="card mt-4">
                <div class="card-title">Category Breakdown</div>
                <table class="report-table">
                    <thead>
                        <tr>
                            <th>Category</th>
                            <th style="text-align:right" id="th-current">This Month</th>
                            <th style="text-align:right" id="th-previous">Last Month</th>
                            <th style="text-align:right">Change</th>
                            <th style="text-align:right">%</th>
                        </tr>
                    </thead>
                    <tbody id="report-table-body"></tbody>
                    <tfoot id="report-table-foot"></tfoot>
                </table>
            </div>
        </div>
    `;

    // Mount date range selector
    const mount = document.getElementById('report-date-range-mount');
    const selector = createDateRangeSelector({
        onChange: async (startDate, endDate, label) => {
            await refreshReport(startDate, endDate);
        },
        initialPreset: 'this_month',
        id: 'report-date-range',
    });
    mount.appendChild(selector);

    // Initial load with default preset
    const initial = getPresetRange('this_month');
    await loadReport(initial.startDate, initial.endDate);
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadReport(startDate, endDate) {
    const loading = document.getElementById('report-loading');
    const error   = document.getElementById('report-error');
    const content = document.getElementById('report-content');
    const empty   = document.getElementById('report-empty');

    const params = startDate && endDate
        ? `?start_date=${startDate}&end_date=${endDate}`
        : '';

    try {
        const [reportData, catData] = await Promise.all([
            api.get(`/api/reports/spending${params}`),
            api.get('/api/categories/'),
        ]);

        data = reportData;
        categories = catData.categories || [];

        loading.style.display = 'none';

        // Empty state: no categories at all
        if (!data.categories || data.categories.length === 0) {
            empty.style.display = '';
            content.style.display = 'none';
            return;
        }

        empty.style.display = 'none';
        content.style.display = '';

        renderKPIs(data);
        renderChart(data);
        renderTable(data);

    } catch (err) {
        loading.style.display = 'none';
        error.style.display = '';
        error.textContent = err.message || 'Failed to load spending report.';
    }
}

async function refreshReport(startDate, endDate) {
    const content = document.getElementById('report-content');
    const empty   = document.getElementById('report-empty');

    const params = `?start_date=${startDate}&end_date=${endDate}`;

    try {
        const reportData = await api.get(`/reports/spending${params}`);
        data = reportData;

        if (!data.categories || data.categories.length === 0) {
            empty.style.display = '';
            content.style.display = 'none';
            return;
        }

        empty.style.display = 'none';
        content.style.display = '';

        _destroyChart();
        renderKPIs(data);
        renderChart(data);
        renderTable(data);

    } catch (err) {
        console.error('Failed to refresh report:', err);
    }
}

// ---------------------------------------------------------------------------
// KPI cards
// ---------------------------------------------------------------------------

function renderKPIs(data) {
    const grid = document.getElementById('report-kpis');
    const { totals, current_period, previous_period } = data;

    const changeClass = _changeClass(totals.change);
    const arrow = _changeArrow(totals.change);
    const pctText = _formatPct(totals.change_pct);

    grid.innerHTML = `
        <div class="kpi-card">
            <span class="kpi-card__label">${escHtml(current_period.label)} Spending</span>
            <span class="kpi-card__value">${formatCurrency(-totals.current)}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-card__label">${escHtml(previous_period.label)} Spending</span>
            <span class="kpi-card__value">${formatCurrency(-totals.previous)}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-card__label">Change</span>
            <span class="kpi-card__value">
                <span class="${changeClass}">${arrow} ${formatCurrency(-Math.abs(totals.change), false)}</span>
                <span class="${changeClass}" style="font-size:14px;margin-left:6px">${pctText}</span>
            </span>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Comparison chart (horizontal bar)
// ---------------------------------------------------------------------------

function renderChart(data) {
    const canvas = document.getElementById('chart-comparison');
    const emptyEl = document.getElementById('chart-empty');
    const periodLabel = document.getElementById('report-period-label');

    periodLabel.textContent = `${data.current_period.label} vs ${data.previous_period.label}`;

    if (!data.categories || data.categories.length === 0) {
        canvas.style.display = 'none';
        emptyEl.style.display = '';
        return;
    }
    canvas.style.display = '';
    emptyEl.style.display = 'none';

    // Dark-mode defaults
    Chart.defaults.color = '#9CA3AF';
    Chart.defaults.borderColor = '#2E3140';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

    // Top 10 categories by current spending for chart readability
    const chartData = data.categories.slice(0, 10);
    const catLabels = chartData.map(d => d.display_name || d.category);

    const ctx = canvas.getContext('2d');

    chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: catLabels,
            datasets: [
                {
                    label: data.current_period.label,
                    data: chartData.map(d => d.current),
                    backgroundColor: 'rgba(0, 168, 107, 0.75)',
                    borderColor: '#00A86B',
                    borderWidth: 1,
                    borderRadius: 4,
                },
                {
                    label: data.previous_period.label,
                    data: chartData.map(d => d.previous),
                    backgroundColor: 'rgba(59, 130, 246, 0.45)',
                    borderColor: '#3B82F6',
                    borderWidth: 1,
                    borderRadius: 4,
                },
            ],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: chartData.length <= 5 ? 1.8 : 1.2,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { usePointStyle: true, padding: 16 },
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label(tipCtx) {
                            const val = tipCtx.parsed.x;
                            const formatted = '£' + val.toLocaleString('en-GB', { minimumFractionDigits: 2 });
                            return `${tipCtx.dataset.label}: ${formatted}`;
                        },
                        afterBody(tipItems) {
                            const idx = tipItems[0].dataIndex;
                            const d = chartData[idx];
                            const arrow = _changeArrow(d.change);
                            const pct = _formatPct(d.change_pct);
                            const sign = d.change >= 0 ? '+' : '';
                            return `Change: ${sign}£${Math.abs(d.change).toFixed(2)} (${arrow} ${pct})`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { color: '#2E3140' },
                    ticks: { callback: _formatAxis },
                },
                y: {
                    grid: { display: false },
                },
            },
        },
    });
}

// ---------------------------------------------------------------------------
// Comparison table
// ---------------------------------------------------------------------------

function renderTable(data) {
    const tbody = document.getElementById('report-table-body');
    const tfoot = document.getElementById('report-table-foot');
    const thCurrent = document.getElementById('th-current');
    const thPrevious = document.getElementById('th-previous');

    // Update column headers with period labels
    thCurrent.textContent = data.current_period.label;
    thPrevious.textContent = data.previous_period.label;

    tbody.innerHTML = data.categories.map(d => {
        const changeClass = _changeClass(d.change);
        const arrow = _changeArrow(d.change);
        const pctText = _formatPct(d.change_pct);
        const colour = d.colour || '#6B7280';

        return `
            <tr>
                <td>
                    <span class="colour-swatch" style="background:${escHtml(colour)}"></span>
                    ${escHtml(_categoryDisplayName(d.category))}
                </td>
                <td style="text-align:right">${formatCurrency(-d.current)}</td>
                <td style="text-align:right">${formatCurrency(-d.previous)}</td>
                <td style="text-align:right">
                    <span class="${changeClass}">${arrow} ${formatCurrency(-Math.abs(d.change), false)}</span>
                </td>
                <td style="text-align:right">
                    <span class="${changeClass}">${pctText}</span>
                </td>
            </tr>
        `;
    }).join('');

    // Totals row
    const { totals } = data;
    const totalChangeClass = _changeClass(totals.change);
    const totalArrow = _changeArrow(totals.change);
    const totalPctText = _formatPct(totals.change_pct);

    tfoot.innerHTML = `
        <tr style="font-weight:600;border-top:2px solid var(--color-border)">
            <td>Total</td>
            <td style="text-align:right">${formatCurrency(-totals.current)}</td>
            <td style="text-align:right">${formatCurrency(-totals.previous)}</td>
            <td style="text-align:right">
                <span class="${totalChangeClass}">${totalArrow} ${formatCurrency(-Math.abs(totals.change), false)}</span>
            </td>
            <td style="text-align:right">
                <span class="${totalChangeClass}">${totalPctText}</span>
            </td>
        </tr>
    `;
}
