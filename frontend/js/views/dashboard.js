/**
 * dashboard.js — Finance dashboard view (Phase 3.3).
 * Renders KPI cards, Chart.js charts, budget progress bars,
 * and a recent transactions table from /api/dashboard/finance.
 */

import { api } from '../api.js';
import { formatCurrency, formatDate, escHtml } from '../utils.js';

// Module state
let data = null;
let categories = [];
let charts = {};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _categoryColour(name) {
    const cat = categories.find(c => c.name === name);
    return cat ? cat.colour : '#6B7280';
}

function _categoryDisplayName(name) {
    const cat = categories.find(c => c.name === name);
    return cat ? (cat.icon ? cat.icon + ' ' : '') + cat.display_name : name;
}

function _barColour(pct) {
    if (pct >= 100) return '#EF4444';
    if (pct >= 80)  return '#F59E0B';
    return '#10B981';
}

function _destroyCharts() {
    Object.values(charts).forEach(c => c?.destroy());
    charts = {};
}

function _formatAxis(value) {
    return '£' + Number(value).toLocaleString('en-GB');
}

// ---------------------------------------------------------------------------
// Render entry point
// ---------------------------------------------------------------------------

export async function render(container) {
    _destroyCharts();

    container.innerHTML = `
        <div class="page-header">
            <h1>Dashboard</h1>
            <p>Finance overview</p>
        </div>

        <div id="dash-loading" class="loading">Loading dashboard…</div>
        <div id="dash-error" class="error-state" style="display:none"></div>
        <div id="dash-empty" class="empty-state" style="display:none">
            <p class="text-muted">No financial data yet. Import a CSV or add transactions manually to see your dashboard.</p>
        </div>

        <div id="dash-content" style="display:none">
            <div class="kpi-grid" id="kpi-grid"></div>

            <div class="dash-grid">
                <div class="card">
                    <div class="card-title">Income vs Expenses</div>
                    <div class="chart-wrap">
                        <canvas id="chart-income-expenses"></canvas>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title">Budget Progress</div>
                    <div id="budget-bars" class="budget-progress-list"></div>
                </div>
            </div>

            <div class="dash-grid">
                <div class="card">
                    <div class="card-title">Spending by Category</div>
                    <div class="chart-wrap">
                        <canvas id="chart-spending"></canvas>
                    </div>
                    <div id="spending-breakdown" class="spending-breakdown"></div>
                    <p id="spending-empty" class="text-muted" style="display:none;text-align:center;margin-top:16px;">No spending this month.</p>
                </div>
                <div class="card">
                    <div class="card-title">Cash Flow</div>
                    <div class="chart-wrap">
                        <canvas id="chart-cash-flow"></canvas>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Recent Transactions</div>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Name</th>
                            <th>Category</th>
                            <th style="text-align:right">Amount</th>
                        </tr>
                    </thead>
                    <tbody id="dash-tx-body"></tbody>
                </table>
                <p id="tx-empty" class="text-muted" style="display:none;text-align:center;margin-top:16px;">No transactions yet.</p>
            </div>
        </div>
    `;

    await loadDashboard();
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadDashboard() {
    const loading = document.getElementById('dash-loading');
    const error   = document.getElementById('dash-error');
    const content = document.getElementById('dash-content');
    const empty   = document.getElementById('dash-empty');

    try {
        const [dashData, catData] = await Promise.all([
            api.get('/dashboard/finance'),
            api.get('/categories/'),
        ]);

        data = dashData;
        categories = catData.categories || [];

        loading.style.display = 'none';

        // Empty state check
        const s = data.summary;
        if (s.balance === 0 && s.month_income === 0 && data.recent_transactions.length === 0) {
            empty.style.display = '';
            return;
        }

        content.style.display = '';

        renderKPIs(data.summary);
        renderBudgetBars(data.budget_status);
        renderRecentTransactions(data.recent_transactions);
        renderCharts(data);

    } catch (err) {
        loading.style.display = 'none';
        error.style.display = '';
        error.textContent = err.message || 'Failed to load dashboard.';
    }
}

// ---------------------------------------------------------------------------
// KPI cards
// ---------------------------------------------------------------------------

function renderKPIs(summary) {
    const grid = document.getElementById('kpi-grid');

    const savingsColour = summary.savings_rate >= 0 ? 'text-success' : 'text-danger';

    grid.innerHTML = `
        <div class="kpi-card">
            <span class="kpi-card__label">Balance</span>
            <span class="kpi-card__value">${formatCurrency(summary.balance)}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-card__label">Income This Month</span>
            <span class="kpi-card__value">${formatCurrency(summary.month_income)}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-card__label">Expenses This Month</span>
            <span class="kpi-card__value">${formatCurrency(-summary.month_expenses)}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-card__label">Net This Month</span>
            <span class="kpi-card__value">${formatCurrency(summary.month_net)}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-card__label">Savings Rate</span>
            <span class="kpi-card__value"><span class="${savingsColour}">${summary.savings_rate}%</span></span>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Budget progress bars
// ---------------------------------------------------------------------------

function renderBudgetBars(budgetStatus) {
    const container = document.getElementById('budget-bars');

    if (!budgetStatus || budgetStatus.length === 0) {
        container.innerHTML = '<p class="text-muted">No active budgets. <a href="#/budgets">Set up budgets</a> to track spending.</p>';
        return;
    }

    container.innerHTML = budgetStatus.map(b => {
        const pct = Math.min(b.percentage, 100);
        const colour = _barColour(b.percentage);
        const catColour = _categoryColour(b.category);
        const warn = b.percentage >= 100 ? ' ⚠' : '';

        return `
            <div class="budget-bar">
                <div class="budget-bar__header">
                    <span class="budget-bar__name">
                        <span class="colour-swatch" style="background:${escHtml(catColour)}"></span>
                        ${escHtml(_categoryDisplayName(b.category))}
                    </span>
                    <span class="budget-bar__pct">£${b.spent.toFixed(2)} / £${b.budget_amount.toFixed(2)} (${b.percentage}%${warn})</span>
                </div>
                <div class="budget-bar__track">
                    <div class="budget-bar__fill" style="width:${pct}%;background:${colour}"></div>
                </div>
            </div>
        `;
    }).join('');
}

// ---------------------------------------------------------------------------
// Recent transactions
// ---------------------------------------------------------------------------

function renderRecentTransactions(transactions) {
    const tbody = document.getElementById('dash-tx-body');
    const emptyEl = document.getElementById('tx-empty');

    if (!transactions || transactions.length === 0) {
        tbody.style.display = 'none';
        emptyEl.style.display = '';
        return;
    }

    tbody.innerHTML = transactions.map(tx => `
        <tr style="cursor:pointer" onclick="location.hash='#/transactions/edit/${tx.id}'">
            <td>${escHtml(formatDate(tx.date))}</td>
            <td>${escHtml(tx.name)}</td>
            <td>${escHtml(tx.category_display_name || tx.category)}</td>
            <td style="text-align:right">${formatCurrency(tx.amount)}</td>
        </tr>
    `).join('');
}

// ---------------------------------------------------------------------------
// Chart.js integration
// ---------------------------------------------------------------------------

function renderCharts(data) {
    // Dark-mode defaults
    Chart.defaults.color = '#9CA3AF';
    Chart.defaults.borderColor = '#2E3140';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

    renderIncomeExpensesChart(data.income_vs_expenses);
    renderSpendingChart(data.spending_by_category);
    renderCashFlowChart(data.cash_flow);
}

function renderIncomeExpensesChart(incomeExpenses) {
    const ctx = document.getElementById('chart-income-expenses').getContext('2d');

    charts.incomeExpenses = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: incomeExpenses.map(d => d.month),
            datasets: [
                {
                    label: 'Income',
                    data: incomeExpenses.map(d => d.income),
                    backgroundColor: 'rgba(16, 185, 129, 0.6)',
                    borderColor: '#10B981',
                    borderWidth: 1,
                    borderRadius: 4,
                },
                {
                    label: 'Expenses',
                    data: incomeExpenses.map(d => d.expenses),
                    backgroundColor: 'rgba(239, 68, 68, 0.6)',
                    borderColor: '#EF4444',
                    borderWidth: 1,
                    borderRadius: 4,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 1.5,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { usePointStyle: true, padding: 16 },
                },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: £${ctx.parsed.y.toLocaleString('en-GB', { minimumFractionDigits: 2 })}`,
                    },
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#2E3140' },
                    ticks: { callback: _formatAxis },
                },
                x: {
                    grid: { display: false },
                },
            },
        },
    });
}

function renderSpendingChart(spending) {
    const canvas = document.getElementById('chart-spending');
    const emptyEl = document.getElementById('spending-empty');
    const breakdownEl = document.getElementById('spending-breakdown');

    if (!spending || spending.length === 0) {
        canvas.style.display = 'none';
        breakdownEl.style.display = 'none';
        emptyEl.style.display = '';
        return;
    }

    const grandTotal = spending.reduce((sum, d) => sum + d.total, 0);

    // Inline plugin: draw grand total in the doughnut centre
    const centerTotalPlugin = {
        id: 'centerTotal',
        beforeDraw(chart) {
            const { ctx, chartArea: { top, bottom, left, right } } = chart;
            const centreX = (left + right) / 2;
            const centreY = (top + bottom) / 2;

            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            ctx.font = "600 20px 'Inter', system-ui, sans-serif";
            ctx.fillStyle = '#F3F4F6';
            ctx.fillText(`£${grandTotal.toLocaleString('en-GB', { minimumFractionDigits: 2 })}`, centreX, centreY - 10);

            ctx.font = "400 11px 'Inter', system-ui, sans-serif";
            ctx.fillStyle = '#9CA3AF';
            ctx.fillText('Total spent', centreX, centreY + 12);

            ctx.restore();
        },
    };

    const ctx = canvas.getContext('2d');

    charts.spending = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: spending.map(d => d.display_name || d.category),
            datasets: [{
                data: spending.map(d => d.total),
                backgroundColor: spending.map(d => d.colour || '#6B7280'),
                borderColor: '#1A1D27',
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 1.2,
            cutout: '65%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label(tipCtx) {
                            const amount = tipCtx.parsed.toLocaleString('en-GB', { minimumFractionDigits: 2 });
                            const pct = spending[tipCtx.dataIndex]?.percentage ?? 0;
                            return `${tipCtx.label}: £${amount} (${pct}%)`;
                        },
                    },
                },
            },
        },
        plugins: [centerTotalPlugin],
    });

    // Breakdown list (replaces legend)
    breakdownEl.innerHTML = spending.map((d, i) => `
        <div class="spending-breakdown__item" data-index="${i}">
            <span class="spending-breakdown__swatch" style="background:${escHtml(d.colour || '#6B7280')}"></span>
            <span class="spending-breakdown__name">${escHtml(d.display_name || d.category)}</span>
            <span class="spending-breakdown__amount">${formatCurrency(-d.total)}</span>
            <span class="spending-breakdown__pct">${d.percentage}%</span>
        </div>
    `).join('');

    // Click-to-toggle segments
    breakdownEl.querySelectorAll('.spending-breakdown__item').forEach(item => {
        item.addEventListener('click', () => {
            const idx = Number(item.dataset.index);
            charts.spending.toggleDataVisibility(idx);
            charts.spending.update();
            item.classList.toggle('spending-breakdown__item--hidden');
        });
    });
}

function renderCashFlowChart(cashFlow) {
    const ctx = document.getElementById('chart-cash-flow').getContext('2d');

    charts.cashFlow = new Chart(ctx, {
        type: 'line',
        data: {
            labels: cashFlow.map(d => d.month),
            datasets: [{
                label: 'Net Cash Flow',
                data: cashFlow.map(d => d.net),
                borderColor: '#00A86B',
                backgroundColor: 'rgba(0, 168, 107, 0.15)',
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#00A86B',
                pointBorderColor: '#1A1D27',
                pointBorderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 1.5,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => `Net: £${ctx.parsed.y.toLocaleString('en-GB', { minimumFractionDigits: 2 })}`,
                    },
                },
            },
            scales: {
                y: {
                    grid: { color: '#2E3140' },
                    ticks: { callback: _formatAxis },
                },
                x: {
                    grid: { display: false },
                },
            },
        },
    });
}
