/**
 * trade-form.js — New / edit trade form (Phase 4.5).
 *
 * Tabbed interface covering all trade fields grouped into 6 sections:
 * Entry, Exit, Risk, Strategy, Psychology, Notes & Tags.
 */

import { api } from '../api.js';
import { escHtml } from '../utils.js';
import { showToast } from '../toast.js';

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

let formState = { mode: 'new', id: null, saving: false, activeTab: 'entry', initialTagIds: [] };

// Which form-group id lives in which tab (for error dot placement)
const FIELD_TAB = {
    'fg-account':    'entry',
    'fg-symbol':     'entry',
    'fg-asset-class':'entry',
    'fg-direction':  'entry',
    'fg-entry-date': 'entry',
    'fg-entry-price':'entry',
    'fg-pos-size':   'entry',
};

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export async function render(container) {
    formState = { ...parseRoute(), saving: false, activeTab: 'entry', initialTagIds: [] };

    let accounts = [], strategies = [], tags = [];
    try {
        [{ accounts }, { strategies }, { tags }] = await Promise.all([
            api.get('/api/accounts/'),
            api.get('/api/strategies/'),
            api.get('/api/tags/'),
        ]);
    } catch (err) {
        console.warn('Supporting data load failed:', err.message);
    }

    const isEdit = formState.mode === 'edit';
    container.innerHTML = buildFormHTML(isEdit);

    populateDropdowns(accounts, strategies);
    renderTagList(tags);
    attachTabListeners();
    attachFormListeners(isEdit);

    if (isEdit) {
        await loadTrade();
    } else {
        document.getElementById('f-entry-date').value = new Date().toISOString().split('T')[0];
        document.getElementById('f-is-open').checked = true;
    }
}

// ---------------------------------------------------------------------------
// Route parsing
// ---------------------------------------------------------------------------

function parseRoute() {
    const hash = window.location.hash.replace(/^#\/?/, '');
    if (hash === 'trades/new') return { mode: 'new', id: null };
    const m = hash.match(/^trades\/edit\/(\d+)$/);
    return m ? { mode: 'edit', id: parseInt(m[1], 10) } : { mode: 'new', id: null };
}

// ---------------------------------------------------------------------------
// HTML builder
// ---------------------------------------------------------------------------

function buildFormHTML(isEdit) {
    const title = isEdit ? 'Edit Trade' : 'New Trade';
    const subtitle = isEdit
        ? 'Update your trade record.'
        : 'Record a new trade across any instrument or asset class.';
    const saveLabel = isEdit ? 'Save Changes' : 'Save Trade';

    return `
<div class="page-header">
    <a href="#/trades" class="text-secondary" style="font-size:13px;">&larr; Back to Trades</a>
    <h1 style="margin-top:var(--space-2);">${escHtml(title)}</h1>
    <p class="text-secondary">${escHtml(subtitle)}</p>
</div>

<form id="trade-form" novalidate>
    <div class="tab-bar">
        <button type="button" class="tab-btn tab-btn--active" data-tab="entry">Entry</button>
        <button type="button" class="tab-btn" data-tab="exit">Exit</button>
        <button type="button" class="tab-btn" data-tab="risk">Risk</button>
        <button type="button" class="tab-btn" data-tab="strategy">Strategy</button>
        <button type="button" class="tab-btn" data-tab="psychology">Psychology</button>
        <button type="button" class="tab-btn" data-tab="notes">Notes &amp; Tags</button>
    </div>

    <div class="card">

        <!-- ── Tab: Entry ─────────────────────────────────────────────── -->
        <div id="tab-entry" class="tab-panel tab-panel--active">
            <div class="grid-2">
                <div class="form-group" id="fg-account">
                    <label for="f-account">Account <span class="text-danger">*</span></label>
                    <select id="f-account">
                        <option value="">— select account —</option>
                    </select>
                </div>
                <div class="form-group" id="fg-symbol">
                    <label for="f-symbol">Symbol <span class="text-danger">*</span></label>
                    <input type="text" id="f-symbol" placeholder="AAPL, EUR/USD, BTC/USDT…" autocomplete="off">
                </div>
            </div>
            <div class="grid-3">
                <div class="form-group" id="fg-asset-class">
                    <label for="f-asset-class">Asset Class <span class="text-danger">*</span></label>
                    <select id="f-asset-class">
                        <option value="">— select —</option>
                        <option value="stocks">Stocks</option>
                        <option value="forex">Forex</option>
                        <option value="crypto">Crypto</option>
                        <option value="options">Options</option>
                    </select>
                </div>
                <div class="form-group" id="fg-direction">
                    <label for="f-direction">Direction <span class="text-danger">*</span></label>
                    <select id="f-direction">
                        <option value="">— select —</option>
                        <option value="long">Long</option>
                        <option value="short">Short</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="f-trade-type">Trade Type</label>
                    <select id="f-trade-type">
                        <option value="trade">Trade</option>
                        <option value="dividend">Dividend</option>
                        <option value="fee">Fee</option>
                        <option value="interest">Interest</option>
                        <option value="deposit">Deposit</option>
                        <option value="withdrawal">Withdrawal</option>
                    </select>
                </div>
            </div>
            <div class="grid-3">
                <div class="form-group" id="fg-entry-date">
                    <label for="f-entry-date">Entry Date <span class="text-danger">*</span></label>
                    <input type="date" id="f-entry-date">
                </div>
                <div class="form-group" id="fg-entry-price">
                    <label for="f-entry-price">Entry Price <span class="text-danger">*</span></label>
                    <input type="number" id="f-entry-price" step="0.0001" min="0" placeholder="0.00">
                </div>
                <div class="form-group" id="fg-pos-size">
                    <label for="f-pos-size">Position Size <span class="text-danger">*</span></label>
                    <input type="number" id="f-pos-size" step="0.0001" min="0" placeholder="Qty / lots / contracts">
                </div>
            </div>
            <div class="grid-2">
                <div class="form-group">
                    <label for="f-entry-fee">Entry Fee (£)</label>
                    <input type="number" id="f-entry-fee" step="0.01" min="0" placeholder="0.00">
                </div>
                <div></div>
            </div>

            <!-- Options-specific fields (shown only when asset_class = options) -->
            <div class="options-fields" id="options-fields">
                <div class="grid-3">
                    <div class="form-group">
                        <label for="f-option-type">Option Type</label>
                        <select id="f-option-type">
                            <option value="">— select —</option>
                            <option value="call">Call</option>
                            <option value="put">Put</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="f-strike-price">Strike Price (£)</label>
                        <input type="number" id="f-strike-price" step="0.01" min="0" placeholder="0.00">
                    </div>
                    <div class="form-group">
                        <label for="f-expiry-date">Expiry Date</label>
                        <input type="date" id="f-expiry-date">
                    </div>
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="f-implied-volatility">Implied Volatility (%)</label>
                        <input type="number" id="f-implied-volatility" step="0.01" min="0" placeholder="e.g. 32.5">
                    </div>
                    <div></div>
                </div>
            </div>

            <div class="form-group" style="margin-top:var(--space-3);">
                <label style="display:flex;align-items:center;gap:var(--space-2);cursor:pointer;font-weight:400;">
                    <input type="checkbox" id="f-is-open" style="width:auto;margin:0;accent-color:var(--color-primary);">
                    Trade is still open
                </label>
                <span class="form-hint">Uncheck when closing a trade and fill in the Exit tab.</span>
            </div>
        </div>

        <!-- ── Tab: Exit ──────────────────────────────────────────────── -->
        <div id="tab-exit" class="tab-panel">
            <p class="text-secondary" style="margin-bottom:var(--space-4);font-size:13px;">
                Leave blank for open trades. Fill in these fields when closing a position.
            </p>
            <div class="grid-3">
                <div class="form-group">
                    <label for="f-exit-date">Exit Date</label>
                    <input type="date" id="f-exit-date">
                </div>
                <div class="form-group">
                    <label for="f-exit-price">Exit Price (£)</label>
                    <input type="number" id="f-exit-price" step="0.0001" min="0" placeholder="0.00">
                </div>
                <div class="form-group">
                    <label for="f-exit-fee">Exit Fee (£)</label>
                    <input type="number" id="f-exit-fee" step="0.01" min="0" placeholder="0.00">
                </div>
            </div>
        </div>

        <!-- ── Tab: Risk ──────────────────────────────────────────────── -->
        <div id="tab-risk" class="tab-panel">
            <p class="text-secondary" style="margin-bottom:var(--space-4);font-size:13px;">
                Prices in the same units as entry price. Risk amount is used to calculate R-multiples.
            </p>
            <div class="grid-3">
                <div class="form-group">
                    <label for="f-stop-loss">Stop Loss (£)</label>
                    <input type="number" id="f-stop-loss" step="0.0001" min="0" placeholder="0.00">
                </div>
                <div class="form-group">
                    <label for="f-take-profit">Take Profit (£)</label>
                    <input type="number" id="f-take-profit" step="0.0001" min="0" placeholder="0.00">
                </div>
                <div class="form-group">
                    <label for="f-risk-amount">Risk Amount (£)</label>
                    <input type="number" id="f-risk-amount" step="0.01" min="0" placeholder="0.00">
                    <span class="form-hint">£ amount risked on this trade.</span>
                </div>
            </div>
        </div>

        <!-- ── Tab: Strategy ─────────────────────────────────────────── -->
        <div id="tab-strategy" class="tab-panel">
            <div class="grid-2">
                <div class="form-group">
                    <label for="f-strategy">Strategy</label>
                    <select id="f-strategy">
                        <option value="">— no strategy —</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="f-timeframe">Timeframe</label>
                    <select id="f-timeframe">
                        <option value="">— none —</option>
                        <option value="1m">1m</option>
                        <option value="5m">5m</option>
                        <option value="15m">15m</option>
                        <option value="1h">1h</option>
                        <option value="4h">4h</option>
                        <option value="D">Daily</option>
                        <option value="W">Weekly</option>
                    </select>
                </div>
            </div>
            <div class="grid-2">
                <div class="form-group">
                    <label for="f-setup-type">Setup Type</label>
                    <input type="text" id="f-setup-type" placeholder="e.g. breakout, pullback, reversal…">
                </div>
                <div class="form-group">
                    <label for="f-market-condition">Market Condition</label>
                    <select id="f-market-condition">
                        <option value="">— none —</option>
                        <option value="trending">Trending</option>
                        <option value="ranging">Ranging</option>
                        <option value="volatile">Volatile</option>
                        <option value="choppy">Choppy</option>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label for="f-entry-reason">Entry Reason</label>
                <textarea id="f-entry-reason" rows="3" placeholder="Why did you enter this trade?"></textarea>
            </div>
            <div class="form-group">
                <label for="f-exit-reason">Exit Reason</label>
                <textarea id="f-exit-reason" rows="3" placeholder="Why did you exit? (fill in after closing)"></textarea>
            </div>
            <div class="form-group">
                <label>Confidence <span class="form-hint" style="display:inline;">(1 = low, 10 = high)</span></label>
                <div class="rating-group" id="rg-confidence">
                    ${[1,2,3,4,5,6,7,8,9,10].map(n => `
                        <input type="radio" name="confidence" id="conf-${n}" value="${n}">
                        <label class="rating-label" for="conf-${n}">${n}</label>
                    `).join('')}
                </div>
            </div>
        </div>

        <!-- ── Tab: Psychology ───────────────────────────────────────── -->
        <div id="tab-psychology" class="tab-panel">
            <p class="text-secondary" style="margin-bottom:var(--space-4);font-size:13px;">
                Rate your emotional state on a 1–5 scale: 1 = fearful/tilted, 3 = calm/neutral, 5 = in the zone.
            </p>
            <div class="grid-3">
                <div class="form-group">
                    <label>Before Entry</label>
                    <div class="rating-group">
                        ${[1,2,3,4,5].map(n => `
                            <input type="radio" name="emotion_before" id="eb-${n}" value="${n}">
                            <label class="rating-label" for="eb-${n}">${n}</label>
                        `).join('')}
                    </div>
                </div>
                <div class="form-group">
                    <label>During Trade</label>
                    <div class="rating-group">
                        ${[1,2,3,4,5].map(n => `
                            <input type="radio" name="emotion_during" id="ed-${n}" value="${n}">
                            <label class="rating-label" for="ed-${n}">${n}</label>
                        `).join('')}
                    </div>
                </div>
                <div class="form-group">
                    <label>After Exit</label>
                    <div class="rating-group">
                        ${[1,2,3,4,5].map(n => `
                            <input type="radio" name="emotion_after" id="ea-${n}" value="${n}">
                            <label class="rating-label" for="ea-${n}">${n}</label>
                        `).join('')}
                    </div>
                </div>
            </div>
            <div class="form-group" style="max-width:260px;">
                <label for="f-rules-followed">Rules Followed (%)</label>
                <input type="number" id="f-rules-followed" step="1" min="0" max="100" placeholder="0–100">
                <span class="form-hint">% of your trading rules you followed on this trade.</span>
            </div>
            <div class="form-group">
                <label for="f-psychology-notes">Psychology Notes</label>
                <textarea id="f-psychology-notes" rows="3" placeholder="What went right or wrong psychologically?"></textarea>
            </div>
            <div class="form-group">
                <label for="f-post-trade-review">Post-Trade Review</label>
                <textarea id="f-post-trade-review" rows="3" placeholder="What would you do differently?"></textarea>
            </div>
        </div>

        <!-- ── Tab: Notes & Tags ─────────────────────────────────────── -->
        <div id="tab-notes" class="tab-panel">
            <div class="form-group">
                <label for="f-notes">Notes</label>
                <textarea id="f-notes" rows="4" placeholder="General notes about this trade…"></textarea>
            </div>
            <div class="form-group">
                <label for="f-screenshot-path">Screenshot Path</label>
                <input type="text" id="f-screenshot-path" placeholder="Relative path or URL to a chart screenshot">
            </div>
            <div class="form-group">
                <label>Tags</label>
                <div id="tag-list">
                    <p class="text-muted" style="font-size:13px;">Loading tags…</p>
                </div>
            </div>
        </div>

        <!-- ── Error banner + Actions (always visible) ───────────────── -->
        <div id="form-error" class="error-state" style="display:none;margin-top:var(--space-4);"></div>

        <div class="form-actions">
            <button type="submit" id="btn-save" class="btn btn-primary">${escHtml(saveLabel)}</button>
            <a href="#/trades" class="btn btn-ghost">Cancel</a>
            ${isEdit ? '<button type="button" id="btn-delete" class="btn btn-danger">Delete Trade</button>' : ''}
        </div>
    </div>
</form>`;
}

// ---------------------------------------------------------------------------
// Populate dropdowns
// ---------------------------------------------------------------------------

function populateDropdowns(accounts, strategies) {
    const accountSel = document.getElementById('f-account');
    accounts.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = `${a.name}${a.broker ? ` (${a.broker})` : ''}`;
        accountSel.appendChild(opt);
    });

    const strategySel = document.getElementById('f-strategy');
    strategies.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name;
        strategySel.appendChild(opt);
    });
}

// ---------------------------------------------------------------------------
// Tag list
// ---------------------------------------------------------------------------

function renderTagList(tags) {
    const container = document.getElementById('tag-list');
    if (!tags || !tags.length) {
        container.innerHTML = '<p class="text-muted" style="font-size:13px;">No tags yet. Create tags in Settings.</p>';
        return;
    }

    // Group by group_name
    const groups = {};
    tags.forEach(tag => {
        if (!groups[tag.group_name]) groups[tag.group_name] = [];
        groups[tag.group_name].push(tag);
    });

    let html = '';
    for (const [groupName, groupTags] of Object.entries(groups)) {
        html += `<div class="tag-group-label">${escHtml(groupName)}</div>`;
        html += '<div class="tag-checkbox-list">';
        groupTags.forEach(tag => {
            html += `
                <label class="tag-checkbox-item">
                    <input type="checkbox" name="tags" value="${tag.id}">
                    ${escHtml(tag.name)}
                </label>`;
        });
        html += '</div>';
    }
    container.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------

function switchTab(tabId) {
    formState.activeTab = tabId;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('tab-btn--active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('tab-panel--active', panel.id === `tab-${tabId}`);
    });
}

function attachTabListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
}

// ---------------------------------------------------------------------------
// Options fields visibility
// ---------------------------------------------------------------------------

function handleAssetClassChange() {
    const val = document.getElementById('f-asset-class').value;
    const div = document.getElementById('options-fields');
    const isOptions = val === 'options';
    div.classList.toggle('options-fields--visible', isOptions);
    if (!isOptions) {
        ['f-option-type', 'f-strike-price', 'f-expiry-date', 'f-implied-volatility'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
    }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

function attachFormListeners(isEdit) {
    // Symbol auto-uppercase
    document.getElementById('f-symbol').addEventListener('input', e => {
        const pos = e.target.selectionStart;
        e.target.value = e.target.value.toUpperCase();
        e.target.setSelectionRange(pos, pos);
    });

    // Options fields toggle
    document.getElementById('f-asset-class').addEventListener('change', handleAssetClassChange);

    // Form submit
    document.getElementById('trade-form').addEventListener('submit', handleSubmit);

    // Delete (edit only)
    if (isEdit) {
        document.getElementById('btn-delete').addEventListener('click', handleDelete);
    }
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function validate() {
    const errors = [];

    // Clear previous errors
    document.querySelectorAll('.form-group--error').forEach(el => el.classList.remove('form-group--error'));
    document.querySelectorAll('.tab-btn[data-has-error]').forEach(el => el.removeAttribute('data-has-error'));

    const errorTabs = new Set();

    function flagField(fgId, message) {
        errors.push(message);
        const fg = document.getElementById(fgId);
        if (fg) fg.classList.add('form-group--error');
        const tab = FIELD_TAB[fgId];
        if (tab) errorTabs.add(tab);
    }

    if (!document.getElementById('f-account').value)
        flagField('fg-account', 'Account is required');
    if (!document.getElementById('f-symbol').value.trim())
        flagField('fg-symbol', 'Symbol is required');
    if (!document.getElementById('f-asset-class').value)
        flagField('fg-asset-class', 'Asset class is required');
    if (!document.getElementById('f-direction').value)
        flagField('fg-direction', 'Direction is required');
    if (!document.getElementById('f-entry-date').value)
        flagField('fg-entry-date', 'Entry date is required');
    if (!document.getElementById('f-entry-price').value)
        flagField('fg-entry-price', 'Entry price is required');
    if (!document.getElementById('f-pos-size').value)
        flagField('fg-pos-size', 'Position size is required');

    // Mark tab buttons with errors
    errorTabs.forEach(tab => {
        const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
        if (btn) btn.dataset.hasError = 'true';
    });

    return errors;
}

// ---------------------------------------------------------------------------
// Payload builder
// ---------------------------------------------------------------------------

function buildPayload() {
    const payload = {};

    // Required
    payload.account_id    = parseInt(document.getElementById('f-account').value, 10);
    payload.symbol        = document.getElementById('f-symbol').value.trim().toUpperCase();
    payload.asset_class   = document.getElementById('f-asset-class').value;
    payload.direction     = document.getElementById('f-direction').value;
    payload.entry_date    = document.getElementById('f-entry-date').value;
    payload.entry_price   = parseFloat(document.getElementById('f-entry-price').value);
    payload.position_size = parseFloat(document.getElementById('f-pos-size').value);

    // Helpers — only include if non-empty
    const optStr  = (id, key) => { const v = document.getElementById(id)?.value?.trim(); if (v) payload[key] = v; };
    const optNum  = (id, key) => { const v = document.getElementById(id)?.value; if (v !== '' && v != null && v !== undefined) payload[key] = parseFloat(v); };
    const optRadio = (name, key) => { const el = document.querySelector(`input[name="${name}"]:checked`); if (el) payload[key] = parseInt(el.value, 10); };

    // Entry
    const tradeType = document.getElementById('f-trade-type').value;
    if (tradeType) payload.trade_type = tradeType;
    optNum('f-entry-fee', 'entry_fee');
    payload.is_open = document.getElementById('f-is-open').checked ? 1 : 0;

    // Options-specific
    if (payload.asset_class === 'options') {
        optStr('f-option-type',        'option_type');
        optNum('f-strike-price',       'strike_price');
        optStr('f-expiry-date',        'expiry_date');
        optNum('f-implied-volatility', 'implied_volatility');
    }

    // Exit
    optStr('f-exit-date',  'exit_date');
    optNum('f-exit-price', 'exit_price');
    optNum('f-exit-fee',   'exit_fee');

    // Risk
    optNum('f-stop-loss',   'stop_loss');
    optNum('f-take-profit', 'take_profit');
    optNum('f-risk-amount', 'risk_amount');

    // Strategy
    const stratVal = document.getElementById('f-strategy').value;
    if (stratVal) payload.strategy_id = parseInt(stratVal, 10);
    optStr('f-timeframe',       'timeframe');
    optStr('f-setup-type',      'setup_type');
    optStr('f-market-condition','market_condition');
    optStr('f-entry-reason',    'entry_reason');
    optStr('f-exit-reason',     'exit_reason');
    optRadio('confidence',      'confidence');

    // Psychology
    optRadio('emotion_before', 'emotion_before');
    optRadio('emotion_during', 'emotion_during');
    optRadio('emotion_after',  'emotion_after');
    optNum('f-rules-followed', 'rules_followed_pct');
    optStr('f-psychology-notes',  'psychology_notes');
    optStr('f-post-trade-review', 'post_trade_review');

    // Notes
    optStr('f-notes',          'notes');
    optStr('f-screenshot-path','screenshot_path');

    return payload;
}

// ---------------------------------------------------------------------------
// Tag sync
// ---------------------------------------------------------------------------

async function syncTags(tradeId) {
    const checked = Array.from(document.querySelectorAll('input[name="tags"]:checked'))
        .map(cb => parseInt(cb.value, 10));
    const prev    = formState.initialTagIds;
    const toAdd   = checked.filter(id => !prev.includes(id));
    const toRemove = prev.filter(id => !checked.includes(id));

    const reqs = [];
    if (toAdd.length) {
        reqs.push(api.post(`/api/trades/${tradeId}/tags`, { tag_ids: toAdd }));
    }
    for (const id of toRemove) {
        reqs.push(api.del(`/api/trades/${tradeId}/tags/${id}`));
    }
    if (reqs.length) await Promise.all(reqs);
}

// ---------------------------------------------------------------------------
// Load trade (edit mode)
// ---------------------------------------------------------------------------

async function loadTrade() {
    try {
        const data = await api.get(`/api/trades/${formState.id}`);
        const t = data.trade;

        // Entry tab
        document.getElementById('f-account').value     = t.account_id ?? '';
        document.getElementById('f-symbol').value      = t.symbol ?? '';
        document.getElementById('f-asset-class').value = t.asset_class ?? '';
        document.getElementById('f-direction').value   = t.direction ?? '';
        document.getElementById('f-trade-type').value  = t.trade_type ?? 'trade';
        document.getElementById('f-entry-date').value  = isoToDate(t.entry_date);
        document.getElementById('f-entry-price').value = t.entry_price ?? '';
        document.getElementById('f-pos-size').value    = t.position_size ?? '';
        document.getElementById('f-entry-fee').value   = t.entry_fee ?? '';
        document.getElementById('f-is-open').checked   = Boolean(t.is_open);

        // Show options fields if needed
        handleAssetClassChange();

        if (t.asset_class === 'options') {
            document.getElementById('f-option-type').value        = t.option_type ?? '';
            document.getElementById('f-strike-price').value       = t.strike_price ?? '';
            document.getElementById('f-expiry-date').value        = isoToDate(t.expiry_date);
            document.getElementById('f-implied-volatility').value = t.implied_volatility ?? '';
        }

        // Exit tab
        document.getElementById('f-exit-date').value  = isoToDate(t.exit_date);
        document.getElementById('f-exit-price').value = t.exit_price ?? '';
        document.getElementById('f-exit-fee').value   = t.exit_fee ?? '';

        // Risk tab
        document.getElementById('f-stop-loss').value   = t.stop_loss ?? '';
        document.getElementById('f-take-profit').value = t.take_profit ?? '';
        document.getElementById('f-risk-amount').value = t.risk_amount ?? '';

        // Strategy tab
        document.getElementById('f-strategy').value        = t.strategy_id ?? '';
        document.getElementById('f-timeframe').value       = t.timeframe ?? '';
        document.getElementById('f-setup-type').value      = t.setup_type ?? '';
        document.getElementById('f-market-condition').value = t.market_condition ?? '';
        document.getElementById('f-entry-reason').value    = t.entry_reason ?? '';
        document.getElementById('f-exit-reason').value     = t.exit_reason ?? '';
        setRadio('confidence', t.confidence);

        // Psychology tab
        setRadio('emotion_before', t.emotion_before);
        setRadio('emotion_during', t.emotion_during);
        setRadio('emotion_after',  t.emotion_after);
        document.getElementById('f-rules-followed').value    = t.rules_followed_pct ?? '';
        document.getElementById('f-psychology-notes').value  = t.psychology_notes ?? '';
        document.getElementById('f-post-trade-review').value = t.post_trade_review ?? '';

        // Notes & Tags tab
        document.getElementById('f-notes').value           = t.notes ?? '';
        document.getElementById('f-screenshot-path').value = t.screenshot_path ?? '';

        const tagIds = (t.tags ?? []).map(tag => tag.id);
        formState.initialTagIds = tagIds;
        tagIds.forEach(id => {
            const cb = document.querySelector(`input[name="tags"][value="${id}"]`);
            if (cb) cb.checked = true;
        });

    } catch (err) {
        document.getElementById('trade-form').innerHTML = `
            <div class="error-state">
                <strong>Failed to load trade</strong>
                <p class="mt-2">${escHtml(err.message)}</p>
                <a href="#/trades" class="btn btn-ghost" style="margin-top:var(--space-4);">Back to Trades</a>
            </div>`;
    }
}

// ---------------------------------------------------------------------------
// Submit handler
// ---------------------------------------------------------------------------

async function handleSubmit(e) {
    e.preventDefault();

    const errors = validate();
    const errorEl = document.getElementById('form-error');

    if (errors.length > 0) {
        errorEl.innerHTML = `<strong>Please fix the following:</strong>
            <ul style="margin-top:var(--space-2);padding-left:var(--space-4);">
                ${errors.map(msg => `<li>${escHtml(msg)}</li>`).join('')}
            </ul>`;
        errorEl.style.display = '';

        // Auto-switch to first errored tab
        const firstErrorTab = document.querySelector('.tab-btn[data-has-error="true"]');
        if (firstErrorTab) switchTab(firstErrorTab.dataset.tab);
        return;
    }

    errorEl.style.display = 'none';
    formState.saving = true;
    const btn = document.getElementById('btn-save');
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        let tradeId;
        const payload = buildPayload();

        if (formState.mode === 'edit') {
            await api.put(`/api/trades/${formState.id}`, payload);
            tradeId = formState.id;
        } else {
            const result = await api.post('/api/trades/', payload);
            tradeId = result.trade.id;
        }

        await syncTags(tradeId);
        showToast(formState.mode === 'edit' ? 'Trade updated' : 'Trade saved', 'success');
        window.location.hash = '#/trades';

    } catch (err) {
        errorEl.innerHTML = `<strong>Save failed</strong><p class="mt-2">${escHtml(err.message)}</p>`;
        errorEl.style.display = '';
        showToast(`Could not save trade: ${err.message}`, 'error');
        btn.disabled = false;
        btn.textContent = formState.mode === 'edit' ? 'Save Changes' : 'Save Trade';
        formState.saving = false;
    }
}

// ---------------------------------------------------------------------------
// Delete handler
// ---------------------------------------------------------------------------

async function handleDelete() {
    if (!confirm('Delete this trade? This cannot be undone.')) return;

    const btn = document.getElementById('btn-delete');
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        await api.del(`/api/trades/${formState.id}`);
        showToast('Trade deleted', 'success');
        window.location.hash = '#/trades';
    } catch (err) {
        const errorEl = document.getElementById('form-error');
        errorEl.innerHTML = `<strong>Delete failed</strong><p class="mt-2">${escHtml(err.message)}</p>`;
        errorEl.style.display = '';
        showToast(`Could not delete trade: ${err.message}`, 'error');
        btn.disabled = false;
        btn.textContent = 'Delete Trade';
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Safely set a radio button by name + value. */
function setRadio(name, value) {
    if (value == null) return;
    const el = document.querySelector(`input[name="${name}"][value="${value}"]`);
    if (el) el.checked = true;
}

/** Strip time portion from ISO datetime strings for <input type="date">. */
function isoToDate(iso) {
    if (!iso) return '';
    return iso.split('T')[0];
}
