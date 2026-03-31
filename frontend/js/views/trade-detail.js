/**
 * trade-detail.js — Read-only detail view for a single trade.
 *
 * Route: #/trades/view/:id
 * Shows all fields grouped into logical sections: Entry, Exit & P&L,
 * Risk Management, Strategy & Context, Psychology, Options (conditional),
 * Notes & Tags, and Metadata.
 */

import { api } from '../api.js';
import { formatCurrency, formatDate, formatDateShort, escHtml } from '../utils.js';

export async function render(container) {
    const id = window.location.hash.split('/').pop();

    container.innerHTML = '<div class="loading">Loading…</div>';

    let trade, accounts, strategies;
    try {
        [{ trade }, { accounts }, { strategies }] = await Promise.all([
            api.get(`/api/trades/${id}`),
            api.get('/api/accounts'),
            api.get('/api/strategies'),
        ]);
    } catch (err) {
        container.innerHTML = `
            <div class="error-state" style="margin: var(--space-5);">
                <strong>Failed to load trade</strong>
                <p class="mt-2">${escHtml(err.message)}</p>
            </div>`;
        return;
    }

    const accountName = accounts.find(a => a.id === trade.account_id)?.name ?? '—';
    const strategyName = strategies.find(s => s.id === trade.strategy_id)?.name ?? null;

    const dirClass  = trade.direction === 'long' ? 'text-success' : 'text-danger';
    const dirLabel  = trade.direction ? trade.direction.charAt(0).toUpperCase() + trade.direction.slice(1) : '—';
    const statusBadge = trade.is_open
        ? '<span class="badge badge-warning">Open</span>'
        : '<span class="badge badge-neutral">Closed</span>';
    const assetBadge = trade.asset_class
        ? `<span class="badge badge-info">${escHtml(trade.asset_class)}</span>`
        : '';

    const dash = '—';

    /** Format a nullable currency value; returns dash if null/undefined. */
    function fmtCcy(val) {
        return (val === null || val === undefined) ? dash : formatCurrency(val);
    }

    /** Format a nullable decimal as a plain string with given decimal places. */
    function fmtNum(val, dp = 2) {
        return (val === null || val === undefined) ? dash : Number(val).toFixed(dp);
    }

    /** Format a nullable percentage. */
    function fmtPct(val) {
        return (val === null || val === undefined) ? dash : `${Number(val).toFixed(2)}%`;
    }

    /** Format duration in minutes to a readable string. */
    function fmtDuration(mins) {
        if (mins === null || mins === undefined) return dash;
        if (mins < 60) return `${mins}m`;
        const h = Math.floor(mins / 60);
        const m = mins % 60;
        return m > 0 ? `${h}h ${m}m` : `${h}h`;
    }

    /** Render a label/value pair inside a grid cell. */
    function field(label, valueHtml) {
        return `
            <div>
                <div class="text-muted" style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-1);">${label}</div>
                <div class="mono" style="font-size: 14px;">${valueHtml}</div>
            </div>`;
    }

    /** Render a full-width text block (for textareas). */
    function textBlock(label, value) {
        if (!value) return '';
        return `
            <div style="margin-top: var(--space-4);">
                <div class="text-muted" style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-2);">${label}</div>
                <div style="font-size: 14px; line-height: 1.6; white-space: pre-wrap;">${escHtml(value)}</div>
            </div>`;
    }

    /** P&L KPI card. */
    function kpiCard(label, valueHtml) {
        return `
            <div class="kpi-card">
                <div class="kpi-card__label">${label}</div>
                <div class="kpi-card__value">${valueHtml}</div>
            </div>`;
    }

    // --- P&L values ---
    const pnlGrossHtml = fmtCcy(trade.pnl);
    const pnlNetHtml   = fmtCcy(trade.pnl_net);
    const pnlPctHtml   = fmtPct(trade.pnl_percentage);
    const rMultipleHtml = (trade.r_multiple === null || trade.r_multiple === undefined)
        ? dash
        : `<span class="${trade.r_multiple >= 0 ? 'text-success' : 'text-danger'}">${fmtNum(trade.r_multiple, 2)}R</span>`;

    // --- Options section (only for options trades) ---
    const optionsSection = trade.asset_class === 'options' ? `
        <div class="card mt-5">
            <div class="card-title" style="margin-bottom: var(--space-4);">Options</div>
            <div class="grid-3" style="gap: var(--space-4);">
                ${field('Option Type', trade.option_type
                    ? `<span class="badge ${trade.option_type === 'call' ? 'badge-success' : 'badge-danger'}">${trade.option_type.toUpperCase()}</span>`
                    : dash)}
                ${field('Strike Price', fmtCcy(trade.strike_price))}
                ${field('Expiry Date', trade.expiry_date ? formatDateShort(trade.expiry_date) : dash)}
            </div>
            <div class="grid-3" style="gap: var(--space-4); margin-top: var(--space-4);">
                ${field('Implied Volatility', fmtPct(trade.implied_volatility))}
            </div>
        </div>` : '';

    // --- Tags ---
    const tagsHtml = (trade.tags && trade.tags.length > 0)
        ? trade.tags.map(t => `<span class="badge badge-neutral">${escHtml(t.name)}</span>`).join(' ')
        : '<span class="text-muted">No tags</span>';

    container.innerHTML = `
        <div style="max-width: 960px; margin: 0 auto; padding: 0 var(--space-5);">

            <!-- Page header -->
            <div class="page-header" style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4);">
                <div>
                    <div style="display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; margin-bottom: var(--space-3);">
                        <span class="mono" style="font-size: 24px; font-weight: 700;">${escHtml(trade.symbol)}</span>
                        <span class="${dirClass}" style="font-weight: 600; font-size: 16px;">${dirLabel}</span>
                        ${statusBadge}
                        ${assetBadge}
                    </div>
                    <div class="text-secondary" style="font-size: 13px;">
                        ${accountName} &middot; ${formatDate(trade.entry_date)}
                        ${trade.trade_type && trade.trade_type !== 'trade' ? `&middot; <span class="badge badge-neutral">${escHtml(trade.trade_type)}</span>` : ''}
                    </div>
                </div>
                <div style="display: flex; gap: var(--space-3); flex-shrink: 0;">
                    <a href="#/trades" class="btn btn-ghost">← Back</a>
                    <a href="#/trades/edit/${trade.id}" class="btn btn-primary">Edit Trade</a>
                </div>
            </div>

            <!-- Entry -->
            <div class="card">
                <div class="card-title" style="margin-bottom: var(--space-4);">Entry</div>
                <div class="grid-3" style="gap: var(--space-4);">
                    ${field('Account', escHtml(accountName))}
                    ${field('Entry Date', formatDate(trade.entry_date))}
                    ${field('Entry Price', fmtCcy(trade.entry_price))}
                </div>
                <div class="grid-3" style="gap: var(--space-4); margin-top: var(--space-4);">
                    ${field('Position Size', fmtNum(trade.position_size, 4))}
                    ${field('Entry Fee', fmtCcy(trade.entry_fee))}
                    ${field('Trade Type', trade.trade_type ? `<span class="badge badge-neutral">${escHtml(trade.trade_type)}</span>` : dash)}
                </div>
            </div>

            <!-- Exit & P&L -->
            <div class="card mt-5">
                <div class="card-title" style="margin-bottom: var(--space-4);">Exit &amp; P&amp;L</div>
                <div class="grid-3" style="gap: var(--space-4);">
                    ${field('Exit Date', trade.exit_date ? formatDate(trade.exit_date) : dash)}
                    ${field('Exit Price', fmtCcy(trade.exit_price))}
                    ${field('Exit Fee', fmtCcy(trade.exit_fee))}
                </div>
                <div class="grid-3" style="gap: var(--space-4); margin-top: var(--space-4);">
                    ${field('Duration', fmtDuration(trade.duration_minutes))}
                </div>
                <div class="grid-4" style="gap: var(--space-3); margin-top: var(--space-5);">
                    ${kpiCard('P&amp;L (Gross)', pnlGrossHtml)}
                    ${kpiCard('P&amp;L (Net)', pnlNetHtml)}
                    ${kpiCard('P&amp;L %', pnlPctHtml)}
                    ${kpiCard('R-Multiple', rMultipleHtml)}
                </div>
            </div>

            <!-- Risk Management -->
            <div class="card mt-5">
                <div class="card-title" style="margin-bottom: var(--space-4);">Risk Management</div>
                <div class="grid-3" style="gap: var(--space-4);">
                    ${field('Stop Loss', fmtCcy(trade.stop_loss))}
                    ${field('Take Profit', fmtCcy(trade.take_profit))}
                    ${field('Risk Amount', fmtCcy(trade.risk_amount))}
                </div>
                <div class="grid-4" style="gap: var(--space-4); margin-top: var(--space-4);">
                    ${field('MAE', fmtCcy(trade.mae))}
                    ${field('MFE', fmtCcy(trade.mfe))}
                    ${field('MAE %', fmtPct(trade.mae_percentage))}
                    ${field('MFE %', fmtPct(trade.mfe_percentage))}
                </div>
            </div>

            <!-- Strategy & Context -->
            <div class="card mt-5">
                <div class="card-title" style="margin-bottom: var(--space-4);">Strategy &amp; Context</div>
                <div class="grid-3" style="gap: var(--space-4);">
                    ${field('Strategy', strategyName ? escHtml(strategyName) : dash)}
                    ${field('Timeframe', trade.timeframe ? escHtml(trade.timeframe) : dash)}
                    ${field('Setup Type', trade.setup_type ? escHtml(trade.setup_type) : dash)}
                </div>
                <div class="grid-3" style="gap: var(--space-4); margin-top: var(--space-4);">
                    ${field('Market Condition', trade.market_condition
                        ? `<span class="badge badge-neutral">${escHtml(trade.market_condition)}</span>`
                        : dash)}
                    ${field('Confidence', trade.confidence !== null && trade.confidence !== undefined
                        ? `${trade.confidence} / 10`
                        : dash)}
                </div>
                ${textBlock('Entry Reason', trade.entry_reason)}
                ${textBlock('Exit Reason', trade.exit_reason)}
            </div>

            <!-- Psychology -->
            <div class="card mt-5">
                <div class="card-title" style="margin-bottom: var(--space-4);">Psychology</div>
                <div class="grid-3" style="gap: var(--space-4);">
                    ${field('Emotion Before', trade.emotion_before !== null && trade.emotion_before !== undefined
                        ? `${trade.emotion_before} / 5`
                        : dash)}
                    ${field('Emotion During', trade.emotion_during !== null && trade.emotion_during !== undefined
                        ? `${trade.emotion_during} / 5`
                        : dash)}
                    ${field('Emotion After', trade.emotion_after !== null && trade.emotion_after !== undefined
                        ? `${trade.emotion_after} / 5`
                        : dash)}
                </div>
                <div style="margin-top: var(--space-4);">
                    ${field('Rules Followed', trade.rules_followed_pct !== null && trade.rules_followed_pct !== undefined
                        ? `${Number(trade.rules_followed_pct).toFixed(0)}%`
                        : dash)}
                </div>
                ${textBlock('Psychology Notes', trade.psychology_notes)}
                ${textBlock('Post-Trade Review', trade.post_trade_review)}
            </div>

            ${optionsSection}

            <!-- Notes & Tags -->
            <div class="card mt-5">
                <div class="card-title" style="margin-bottom: var(--space-4);">Notes &amp; Tags</div>
                ${trade.notes ? textBlock('Notes', trade.notes) : ''}
                ${trade.screenshot_path ? `
                    <div style="margin-top: var(--space-4);">
                        ${field('Screenshot Path', escHtml(trade.screenshot_path))}
                    </div>` : ''}
                <div style="margin-top: var(--space-4);">
                    <div class="text-muted" style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-2);">Tags</div>
                    <div style="display: flex; flex-wrap: wrap; gap: var(--space-2);">${tagsHtml}</div>
                </div>
            </div>

            <!-- Metadata -->
            <div class="card mt-5" style="margin-bottom: var(--space-6);">
                <div class="card-title" style="margin-bottom: var(--space-4);">Metadata</div>
                <div class="grid-3" style="gap: var(--space-4);">
                    ${field('Trade ID', `#${trade.id}`)}
                    ${field('Created', trade.created_at ? formatDate(trade.created_at) : dash)}
                    ${field('Last Updated', trade.updated_at ? formatDate(trade.updated_at) : dash)}
                </div>
            </div>

        </div>`;
}
