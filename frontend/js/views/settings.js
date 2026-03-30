/**
 * settings.js — Settings view: category & category rules management.
 *
 * Displays all categories in a table with colour swatches.
 * Provides inline add/edit form and delete with confirmation.
 *
 * Also displays category rules for auto-categorisation on import,
 * with full CRUD and toggle active/inactive.
 */

import { api } from '../api.js';
import { escHtml, formatCurrency } from '../utils.js';

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

let categories = [];
let formMode = null;   // null | 'add' | 'edit'
let editId = null;

let rules = [];
let ruleFormMode = null;   // null | 'add' | 'edit'
let ruleEditId = null;

let accounts = [];
let acctFormMode = null;   // null | 'add' | 'edit'
let acctEditId = null;

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

export async function render(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1>Settings</h1>
            <p>Manage spending categories, colours, and auto-categorisation rules.</p>
        </div>

        <!-- Inline add/edit form (hidden by default) -->
        <div id="cat-form-section" style="display:none">
            <div class="card mb-5">
                <h2 id="cat-form-title" class="card-title">Add Category</h2>
                <div id="cat-form-error" class="error-state mb-4" style="display:none"></div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="f-label">Label <span class="text-danger">*</span></label>
                        <input type="text" id="f-label" placeholder="e.g. Subscriptions" maxlength="50">
                        <span class="form-hint">Display name shown in the UI</span>
                    </div>
                    <div class="form-group">
                        <label for="f-colour">Colour <span class="text-danger">*</span></label>
                        <div class="colour-input-group">
                            <input type="color" id="f-colour" value="#6B7280">
                            <span id="f-colour-preview" class="colour-swatch" style="background:#6B7280"></span>
                            <span id="f-colour-hex" class="text-secondary mono" style="font-size:13px">#6B7280</span>
                        </div>
                    </div>
                </div>
                <div class="form-group" style="max-width:200px">
                    <label for="f-icon">Icon (optional)</label>
                    <input type="text" id="f-icon" placeholder="e.g. 🎵" maxlength="10">
                    <span class="form-hint">Emoji character</span>
                </div>
                <div class="form-actions">
                    <button type="button" id="btn-save-cat" class="btn btn-primary">Save</button>
                    <button type="button" id="btn-cancel-cat" class="btn btn-ghost">Cancel</button>
                </div>
            </div>
        </div>

        <!-- Categories table -->
        <div class="card mb-5">
            <div class="flex items-center justify-between mb-4">
                <h2 class="card-title" style="margin-bottom:0">Categories</h2>
                <button type="button" id="btn-add-cat" class="btn btn-primary">+ Add Category</button>
            </div>
            <div id="cat-loading" class="loading">Loading categories…</div>
            <div id="cat-error" class="error-state" style="display:none"></div>
            <div id="cat-table-wrap" class="table-container" style="display:none">
                <table>
                    <thead>
                        <tr>
                            <th style="width:48px">Colour</th>
                            <th>Label</th>
                            <th>Name</th>
                            <th style="width:80px">Type</th>
                            <th style="width:120px">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="cat-body"></tbody>
                </table>
            </div>
        </div>

        <!-- Rule add/edit form (hidden by default) -->
        <div id="rule-form-section" style="display:none">
            <div class="card mb-5">
                <h2 id="rule-form-title" class="card-title">Add Rule</h2>
                <div id="rule-form-error" class="error-state mb-4" style="display:none"></div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="rf-field">Field <span class="text-danger">*</span></label>
                        <select id="rf-field">
                            <option value="name">Name</option>
                            <option value="description">Description</option>
                            <option value="notes">Notes</option>
                        </select>
                        <span class="form-hint">Transaction field to match against</span>
                    </div>
                    <div class="form-group">
                        <label for="rf-operator">Operator</label>
                        <select id="rf-operator">
                            <option value="contains">Contains</option>
                            <option value="equals">Equals</option>
                            <option value="starts_with">Starts with</option>
                        </select>
                    </div>
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="rf-value">Match Value <span class="text-danger">*</span></label>
                        <input type="text" id="rf-value" placeholder="e.g. Tesco" maxlength="200">
                        <span class="form-hint">Text to match (case-insensitive)</span>
                    </div>
                    <div class="form-group">
                        <label for="rf-category">Category <span class="text-danger">*</span></label>
                        <select id="rf-category">
                            <option value="">Select category…</option>
                        </select>
                    </div>
                </div>
                <div class="form-group" style="max-width:200px">
                    <label for="rf-priority">Priority</label>
                    <input type="number" id="rf-priority" value="0" min="0" max="999">
                    <span class="form-hint">Higher = checked first</span>
                </div>
                <div class="form-actions">
                    <button type="button" id="btn-save-rule" class="btn btn-primary">Save</button>
                    <button type="button" id="btn-cancel-rule" class="btn btn-ghost">Cancel</button>
                </div>
            </div>
        </div>

        <!-- Category Rules table -->
        <div class="card mb-5">
            <div class="flex items-center justify-between mb-4">
                <h2 class="card-title" style="margin-bottom:0">Category Rules</h2>
                <button type="button" id="btn-add-rule" class="btn btn-primary">+ Add Rule</button>
            </div>
            <p class="text-secondary mb-4" style="margin-top:-8px">
                Rules auto-categorise imported transactions by matching keywords.
                Higher-priority rules are checked first.
            </p>
            <div id="rule-loading" class="loading">Loading rules…</div>
            <div id="rule-error" class="error-state" style="display:none"></div>
            <div id="rule-empty" class="text-muted" style="display:none;padding:var(--space-4) 0">
                No category rules yet. Add one to start auto-categorising imports.
            </div>
            <div id="rule-table-wrap" class="table-container" style="display:none">
                <table>
                    <thead>
                        <tr>
                            <th>Field</th>
                            <th>Operator</th>
                            <th>Value</th>
                            <th>Category</th>
                            <th style="width:70px">Priority</th>
                            <th style="width:80px">Source</th>
                            <th style="width:70px">Active</th>
                            <th style="width:120px">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="rule-body"></tbody>
                </table>
            </div>
        </div>

        <!-- Account add/edit form (hidden by default) -->
        <div id="acct-form-section" style="display:none">
            <div class="card mb-5">
                <h2 id="acct-form-title" class="card-title">Add Trading Account</h2>
                <div id="acct-form-error" class="error-state mb-4" style="display:none"></div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="af-name">Account Name <span class="text-danger">*</span></label>
                        <input type="text" id="af-name" placeholder="e.g. IBKR Main" maxlength="100">
                        <span class="form-hint">Your name for this account</span>
                    </div>
                    <div class="form-group">
                        <label for="af-broker">Broker (optional)</label>
                        <input type="text" id="af-broker" placeholder="e.g. Interactive Brokers" maxlength="100">
                        <span class="form-hint">Broker or exchange name</span>
                    </div>
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="af-asset-class">Asset Class <span class="text-danger">*</span></label>
                        <select id="af-asset-class">
                            <option value="stocks">Stocks</option>
                            <option value="forex">Forex</option>
                            <option value="crypto">Crypto</option>
                            <option value="options">Options</option>
                            <option value="multi">Multi</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="af-currency">Currency</label>
                        <input type="text" id="af-currency" placeholder="GBP" maxlength="10" value="GBP">
                        <span class="form-hint">3-letter currency code</span>
                    </div>
                </div>
                <div class="form-group" style="max-width:220px">
                    <label for="af-balance">Initial Balance (£)</label>
                    <input type="number" id="af-balance" step="0.01" min="0" placeholder="0.00" value="0">
                    <span class="form-hint">Starting account balance</span>
                </div>
                <div class="form-actions">
                    <button type="button" id="btn-save-acct" class="btn btn-primary">Save</button>
                    <button type="button" id="btn-cancel-acct" class="btn btn-ghost">Cancel</button>
                </div>
            </div>
        </div>

        <!-- Trading Accounts table -->
        <div class="card">
            <div class="flex items-center justify-between mb-4">
                <h2 class="card-title" style="margin-bottom:0">Trading Accounts</h2>
                <button type="button" id="btn-add-acct" class="btn btn-primary">+ Add Account</button>
            </div>
            <p class="text-secondary mb-4" style="margin-top:-8px">
                Manage your trading accounts across brokers and asset classes.
            </p>
            <div id="acct-loading" class="loading">Loading accounts…</div>
            <div id="acct-error" class="error-state" style="display:none"></div>
            <div id="acct-empty" class="text-muted" style="display:none;padding:var(--space-4) 0">
                No trading accounts yet. Add one to start logging trades.
            </div>
            <div id="acct-table-wrap" class="table-container" style="display:none">
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Broker</th>
                            <th>Asset Class</th>
                            <th>Currency</th>
                            <th style="text-align:right">Initial Balance</th>
                            <th style="width:70px">Active</th>
                            <th style="width:120px">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="acct-body"></tbody>
                </table>
            </div>
        </div>
    `;

    attachListeners(container);
    await loadCategories();
    await loadRules();
    await loadAccounts();
}

// ---------------------------------------------------------------------------
// Data loading — Categories
// ---------------------------------------------------------------------------

async function loadCategories() {
    const loading = document.getElementById('cat-loading');
    const error = document.getElementById('cat-error');
    const tableWrap = document.getElementById('cat-table-wrap');

    loading.style.display = '';
    error.style.display = 'none';
    tableWrap.style.display = 'none';

    try {
        const data = await api.get('/api/categories/');
        categories = data.categories;
        renderCategoryRows();
        loading.style.display = 'none';
        tableWrap.style.display = '';
    } catch (err) {
        loading.style.display = 'none';
        error.style.display = '';
        error.textContent = `Failed to load categories: ${err.message}`;
    }
}

// ---------------------------------------------------------------------------
// Data loading — Rules
// ---------------------------------------------------------------------------

async function loadRules() {
    const loading = document.getElementById('rule-loading');
    const error = document.getElementById('rule-error');
    const tableWrap = document.getElementById('rule-table-wrap');
    const empty = document.getElementById('rule-empty');

    loading.style.display = '';
    error.style.display = 'none';
    tableWrap.style.display = 'none';
    empty.style.display = 'none';

    try {
        const data = await api.get('/api/category-rules/');
        rules = data.rules;
        if (rules.length === 0) {
            loading.style.display = 'none';
            empty.style.display = '';
        } else {
            renderRuleRows();
            loading.style.display = 'none';
            tableWrap.style.display = '';
        }
    } catch (err) {
        loading.style.display = 'none';
        error.style.display = '';
        error.textContent = `Failed to load rules: ${err.message}`;
    }
}

// ---------------------------------------------------------------------------
// Table rendering — Categories
// ---------------------------------------------------------------------------

function renderCategoryRows() {
    const tbody = document.getElementById('cat-body');
    if (!tbody) return;

    tbody.innerHTML = categories.map(cat => `
        <tr>
            <td><span class="colour-swatch" style="background:${escHtml(cat.colour)}"></span></td>
            <td>${cat.icon ? escHtml(cat.icon) + ' ' : ''}${escHtml(cat.display_name)}</td>
            <td><span class="mono text-muted" style="font-size:12px">${escHtml(cat.name)}</span></td>
            <td>
                ${cat.is_default
                    ? '<span class="badge badge-info">Default</span>'
                    : '<span class="badge badge-neutral">Custom</span>'}
            </td>
            <td>
                <div class="flex gap-2">
                    <button class="btn btn-ghost" style="padding:2px 8px;font-size:12px"
                            data-edit="${cat.id}">Edit</button>
                    ${!cat.is_default
                        ? `<button class="btn btn-danger" style="padding:2px 8px;font-size:12px"
                                   data-delete="${cat.id}">Delete</button>`
                        : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

// ---------------------------------------------------------------------------
// Table rendering — Rules
// ---------------------------------------------------------------------------

const _OPERATOR_LABELS = {
    contains: 'Contains',
    equals: 'Equals',
    starts_with: 'Starts with',
};

function _categoryDisplayName(name) {
    const cat = categories.find(c => c.name === name);
    return cat ? (cat.icon ? cat.icon + ' ' : '') + cat.display_name : name;
}

function renderRuleRows() {
    const tbody = document.getElementById('rule-body');
    if (!tbody) return;

    tbody.innerHTML = rules.map(rule => `
        <tr style="${rule.is_active ? '' : 'opacity:0.5'}">
            <td>${escHtml(rule.field.charAt(0).toUpperCase() + rule.field.slice(1))}</td>
            <td>${escHtml(_OPERATOR_LABELS[rule.operator] ?? rule.operator)}</td>
            <td><strong class="mono" style="font-size:13px">${escHtml(rule.value)}</strong></td>
            <td>${escHtml(_categoryDisplayName(rule.category))}</td>
            <td class="mono" style="text-align:right">${rule.priority}</td>
            <td>
                ${rule.source === 'learned'
                    ? '<span class="badge badge-info">Learned</span>'
                    : '<span class="badge badge-neutral">Manual</span>'}
            </td>
            <td>
                <button class="btn btn-ghost" style="padding:2px 8px;font-size:12px"
                        data-rule-toggle="${rule.id}">
                    ${rule.is_active ? 'On' : 'Off'}
                </button>
            </td>
            <td>
                <div class="flex gap-2">
                    <button class="btn btn-ghost" style="padding:2px 8px;font-size:12px"
                            data-rule-edit="${rule.id}">Edit</button>
                    <button class="btn btn-danger" style="padding:2px 8px;font-size:12px"
                            data-rule-delete="${rule.id}">Delete</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// ---------------------------------------------------------------------------
// Form handling — Categories
// ---------------------------------------------------------------------------

function showForm(mode, cat = null) {
    formMode = mode;
    editId = cat ? cat.id : null;

    const section = document.getElementById('cat-form-section');
    const title = document.getElementById('cat-form-title');
    const errorDiv = document.getElementById('cat-form-error');

    title.textContent = mode === 'add' ? 'Add Category' : 'Edit Category';
    errorDiv.style.display = 'none';

    document.getElementById('f-label').value = cat ? cat.display_name : '';
    const colour = cat ? cat.colour : '#6B7280';
    document.getElementById('f-colour').value = colour;
    document.getElementById('f-colour-preview').style.background = colour;
    document.getElementById('f-colour-hex').textContent = colour;
    document.getElementById('f-icon').value = cat?.icon ?? '';

    section.style.display = '';
    document.getElementById('f-label').focus();
}

function hideForm() {
    formMode = null;
    editId = null;
    document.getElementById('cat-form-section').style.display = 'none';
    document.getElementById('cat-form-error').style.display = 'none';
}

async function saveCategory() {
    const label = document.getElementById('f-label').value.trim();
    const colour = document.getElementById('f-colour').value;
    const icon = document.getElementById('f-icon').value.trim() || null;
    const errorDiv = document.getElementById('cat-form-error');
    const saveBtn = document.getElementById('btn-save-cat');

    // Client-side validation
    if (!label) {
        errorDiv.textContent = 'Label is required.';
        errorDiv.style.display = '';
        document.getElementById('f-label').focus();
        return;
    }

    errorDiv.style.display = 'none';
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        const body = { label, colour, icon };
        if (formMode === 'add') {
            await api.post('/api/categories/', body);
        } else {
            await api.put(`/api/categories/${editId}`, body);
        }
        hideForm();
        await loadCategories();
    } catch (err) {
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
}

async function deleteCategory(id) {
    const cat = categories.find(c => c.id === id);
    if (!cat) return;

    if (!confirm(`Delete category "${cat.display_name}"? This cannot be undone.`)) return;

    try {
        await api.del(`/api/categories/${id}`);
        await loadCategories();
    } catch (err) {
        const errorDiv = document.getElementById('cat-error');
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    }
}

// ---------------------------------------------------------------------------
// Form handling — Rules
// ---------------------------------------------------------------------------

function _populateCategorySelect() {
    const select = document.getElementById('rf-category');
    select.innerHTML = '<option value="">Select category…</option>' +
        categories.map(c =>
            `<option value="${escHtml(c.name)}">${c.icon ? escHtml(c.icon) + ' ' : ''}${escHtml(c.display_name)}</option>`
        ).join('');
}

function showRuleForm(mode, rule = null) {
    ruleFormMode = mode;
    ruleEditId = rule ? rule.id : null;

    const section = document.getElementById('rule-form-section');
    const title = document.getElementById('rule-form-title');
    const errorDiv = document.getElementById('rule-form-error');

    title.textContent = mode === 'add' ? 'Add Rule' : 'Edit Rule';
    errorDiv.style.display = 'none';

    _populateCategorySelect();

    document.getElementById('rf-field').value = rule ? rule.field : 'name';
    document.getElementById('rf-operator').value = rule ? rule.operator : 'contains';
    document.getElementById('rf-value').value = rule ? rule.value : '';
    document.getElementById('rf-category').value = rule ? rule.category : '';
    document.getElementById('rf-priority').value = rule ? rule.priority : 0;

    section.style.display = '';
    document.getElementById('rf-value').focus();
}

function hideRuleForm() {
    ruleFormMode = null;
    ruleEditId = null;
    document.getElementById('rule-form-section').style.display = 'none';
    document.getElementById('rule-form-error').style.display = 'none';
}

async function saveRule() {
    const field = document.getElementById('rf-field').value;
    const operator = document.getElementById('rf-operator').value;
    const value = document.getElementById('rf-value').value.trim();
    const category = document.getElementById('rf-category').value;
    const priority = parseInt(document.getElementById('rf-priority').value, 10) || 0;
    const errorDiv = document.getElementById('rule-form-error');
    const saveBtn = document.getElementById('btn-save-rule');

    // Client-side validation
    if (!value) {
        errorDiv.textContent = 'Match value is required.';
        errorDiv.style.display = '';
        document.getElementById('rf-value').focus();
        return;
    }
    if (!category) {
        errorDiv.textContent = 'Category is required.';
        errorDiv.style.display = '';
        document.getElementById('rf-category').focus();
        return;
    }

    errorDiv.style.display = 'none';
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        const body = { field, operator, value, category, priority };
        if (ruleFormMode === 'add') {
            await api.post('/api/category-rules/', body);
        } else {
            await api.put(`/api/category-rules/${ruleEditId}`, body);
        }
        hideRuleForm();
        await loadRules();
    } catch (err) {
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
}

async function deleteRule(id) {
    const rule = rules.find(r => r.id === id);
    if (!rule) return;

    if (!confirm(`Delete rule matching "${rule.value}"? This cannot be undone.`)) return;

    try {
        await api.del(`/api/category-rules/${id}`);
        await loadRules();
    } catch (err) {
        const errorDiv = document.getElementById('rule-error');
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    }
}

async function toggleRule(id) {
    try {
        await api.post(`/api/category-rules/${id}/toggle`);
        await loadRules();
    } catch (err) {
        const errorDiv = document.getElementById('rule-error');
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    }
}

// ---------------------------------------------------------------------------
// Data loading — Accounts
// ---------------------------------------------------------------------------

async function loadAccounts() {
    const loading = document.getElementById('acct-loading');
    const error = document.getElementById('acct-error');
    const tableWrap = document.getElementById('acct-table-wrap');
    const empty = document.getElementById('acct-empty');

    loading.style.display = '';
    error.style.display = 'none';
    tableWrap.style.display = 'none';
    empty.style.display = 'none';

    try {
        const data = await api.get('/api/accounts/');
        accounts = data.accounts;
        loading.style.display = 'none';
        if (accounts.length === 0) {
            empty.style.display = '';
        } else {
            renderAccountRows();
            tableWrap.style.display = '';
        }
    } catch (err) {
        loading.style.display = 'none';
        error.style.display = '';
        error.textContent = `Failed to load accounts: ${err.message}`;
    }
}

// ---------------------------------------------------------------------------
// Table rendering — Accounts
// ---------------------------------------------------------------------------

const _ASSET_CLASS_LABELS = {
    stocks: 'Stocks',
    forex: 'Forex',
    crypto: 'Crypto',
    options: 'Options',
    multi: 'Multi',
};

const _ASSET_CLASS_COLOURS = {
    stocks: '#3B82F6',
    forex: '#F59E0B',
    crypto: '#A78BFA',
    options: '#EC4899',
    multi: '#10B981',
};

function renderAccountRows() {
    const tbody = document.getElementById('acct-body');
    if (!tbody) return;

    tbody.innerHTML = accounts.map(a => {
        const colour = _ASSET_CLASS_COLOURS[a.asset_class] ?? '#6B7280';
        const label = escHtml(_ASSET_CLASS_LABELS[a.asset_class] ?? a.asset_class);
        return `
        <tr style="${a.is_active ? '' : 'opacity:0.5'}">
            <td><strong>${escHtml(a.name)}</strong></td>
            <td class="text-secondary">${a.broker ? escHtml(a.broker) : '—'}</td>
            <td>
                <span class="colour-swatch" style="background:${colour}"></span>
                ${label}
            </td>
            <td class="mono">${escHtml(a.currency)}</td>
            <td style="text-align:right">
                <span class="mono">${formatCurrency(a.initial_balance, false)}</span>
            </td>
            <td>
                <button class="btn btn-ghost" style="padding:2px 8px;font-size:12px"
                        data-acct-toggle="${a.id}">
                    ${a.is_active ? 'On' : 'Off'}
                </button>
            </td>
            <td>
                <div class="flex gap-2">
                    <button class="btn btn-ghost" style="padding:2px 8px;font-size:12px"
                            data-acct-edit="${a.id}">Edit</button>
                    <button class="btn btn-danger" style="padding:2px 8px;font-size:12px"
                            data-acct-delete="${a.id}">Delete</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

// ---------------------------------------------------------------------------
// Form handling — Accounts
// ---------------------------------------------------------------------------

function showAccountForm(mode, account = null) {
    acctFormMode = mode;
    acctEditId = account ? account.id : null;

    const section = document.getElementById('acct-form-section');
    const title = document.getElementById('acct-form-title');
    const errorDiv = document.getElementById('acct-form-error');

    title.textContent = mode === 'add' ? 'Add Trading Account' : 'Edit Trading Account';
    errorDiv.style.display = 'none';

    document.getElementById('af-name').value = account ? account.name : '';
    document.getElementById('af-broker').value = account?.broker ?? '';
    document.getElementById('af-asset-class').value = account ? account.asset_class : 'stocks';
    document.getElementById('af-currency').value = account ? account.currency : 'GBP';
    document.getElementById('af-balance').value = account ? account.initial_balance : '0';

    section.style.display = '';
    document.getElementById('af-name').focus();
}

function hideAccountForm() {
    acctFormMode = null;
    acctEditId = null;
    document.getElementById('acct-form-section').style.display = 'none';
    document.getElementById('acct-form-error').style.display = 'none';
}

async function saveAccount() {
    const name = document.getElementById('af-name').value.trim();
    const broker = document.getElementById('af-broker').value.trim() || null;
    const asset_class = document.getElementById('af-asset-class').value;
    const currency = document.getElementById('af-currency').value.trim() || 'GBP';
    const balanceStr = document.getElementById('af-balance').value;
    const errorDiv = document.getElementById('acct-form-error');
    const saveBtn = document.getElementById('btn-save-acct');

    // Client-side validation
    if (!name) {
        errorDiv.textContent = 'Account name is required.';
        errorDiv.style.display = '';
        document.getElementById('af-name').focus();
        return;
    }
    const balance = parseFloat(balanceStr);
    if (balanceStr !== '' && (isNaN(balance) || balance < 0)) {
        errorDiv.textContent = 'Initial balance must be zero or a positive number.';
        errorDiv.style.display = '';
        document.getElementById('af-balance').focus();
        return;
    }

    errorDiv.style.display = 'none';
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        const body = {
            name,
            broker,
            asset_class,
            currency,
            initial_balance: balanceStr === '' ? 0 : balance,
        };
        if (acctFormMode === 'add') {
            await api.post('/api/accounts/', body);
        } else {
            await api.put(`/api/accounts/${acctEditId}`, body);
        }
        hideAccountForm();
        await loadAccounts();
    } catch (err) {
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
}

async function deleteAccount(id) {
    const account = accounts.find(a => a.id === id);
    if (!account) return;

    if (!confirm(`Delete account "${account.name}"? This cannot be undone.`)) return;

    try {
        await api.del(`/api/accounts/${id}`);
        await loadAccounts();
    } catch (err) {
        const errorDiv = document.getElementById('acct-error');
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    }
}

async function toggleAccount(id) {
    try {
        await api.post(`/api/accounts/${id}/toggle`);
        await loadAccounts();
    } catch (err) {
        const errorDiv = document.getElementById('acct-error');
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

function attachListeners(container) {
    // --- Category listeners ---
    container.querySelector('#btn-add-cat').addEventListener('click', () => {
        showForm('add');
    });

    container.querySelector('#btn-save-cat').addEventListener('click', saveCategory);
    container.querySelector('#btn-cancel-cat').addEventListener('click', hideForm);

    // Colour input live preview
    container.querySelector('#f-colour').addEventListener('input', (e) => {
        const val = e.target.value;
        document.getElementById('f-colour-preview').style.background = val;
        document.getElementById('f-colour-hex').textContent = val;
    });

    // Table delegation: edit / delete buttons
    container.querySelector('#cat-body').addEventListener('click', (e) => {
        const editBtn = e.target.closest('[data-edit]');
        if (editBtn) {
            const id = Number(editBtn.dataset.edit);
            const cat = categories.find(c => c.id === id);
            if (cat) showForm('edit', cat);
            return;
        }

        const deleteBtn = e.target.closest('[data-delete]');
        if (deleteBtn) {
            const id = Number(deleteBtn.dataset.delete);
            deleteCategory(id);
        }
    });

    // Enter key in category form submits
    const catFormSection = container.querySelector('#cat-form-section');
    catFormSection.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveCategory();
        }
    });

    // --- Rule listeners ---
    container.querySelector('#btn-add-rule').addEventListener('click', () => {
        showRuleForm('add');
    });

    container.querySelector('#btn-save-rule').addEventListener('click', saveRule);
    container.querySelector('#btn-cancel-rule').addEventListener('click', hideRuleForm);

    // Rule table delegation: edit / delete / toggle
    container.querySelector('#rule-body').addEventListener('click', (e) => {
        const editBtn = e.target.closest('[data-rule-edit]');
        if (editBtn) {
            const id = Number(editBtn.dataset.ruleEdit);
            const rule = rules.find(r => r.id === id);
            if (rule) showRuleForm('edit', rule);
            return;
        }

        const deleteBtn = e.target.closest('[data-rule-delete]');
        if (deleteBtn) {
            const id = Number(deleteBtn.dataset.ruleDelete);
            deleteRule(id);
            return;
        }

        const toggleBtn = e.target.closest('[data-rule-toggle]');
        if (toggleBtn) {
            const id = Number(toggleBtn.dataset.ruleToggle);
            toggleRule(id);
        }
    });

    // Enter key in rule form submits
    const ruleFormSection = container.querySelector('#rule-form-section');
    ruleFormSection.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveRule();
        }
    });

    // --- Account listeners ---
    container.querySelector('#btn-add-acct').addEventListener('click', () => {
        showAccountForm('add');
    });

    container.querySelector('#btn-save-acct').addEventListener('click', saveAccount);
    container.querySelector('#btn-cancel-acct').addEventListener('click', hideAccountForm);

    // Table delegation: edit / delete / toggle
    container.querySelector('#acct-body').addEventListener('click', (e) => {
        const editBtn = e.target.closest('[data-acct-edit]');
        if (editBtn) {
            const id = Number(editBtn.dataset.acctEdit);
            const account = accounts.find(a => a.id === id);
            if (account) showAccountForm('edit', account);
            return;
        }

        const deleteBtn = e.target.closest('[data-acct-delete]');
        if (deleteBtn) {
            const id = Number(deleteBtn.dataset.acctDelete);
            deleteAccount(id);
            return;
        }

        const toggleBtn = e.target.closest('[data-acct-toggle]');
        if (toggleBtn) {
            const id = Number(toggleBtn.dataset.acctToggle);
            toggleAccount(id);
        }
    });

    // Enter key in account form submits
    const acctFormSection = container.querySelector('#acct-form-section');
    acctFormSection.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveAccount();
        }
    });
}
