/**
 * budgets.js — Budget management view (Phase 3).
 *
 * Displays all budgets in a table with category info and amount.
 * Provides inline add/edit form and delete with confirmation.
 * Supports toggling budgets active/inactive.
 */

import { api } from '../api.js';
import { escHtml, formatCurrency } from '../utils.js';

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

let budgets = [];
let categories = [];
let formMode = null;   // null | 'add' | 'edit'
let editId = null;

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

export async function render(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1>Budgets</h1>
            <p>Set spending limits per category and track your progress.</p>
        </div>

        <!-- Inline add/edit form (hidden by default) -->
        <div id="budget-form-section" style="display:none">
            <div class="card mb-5">
                <h2 id="budget-form-title" class="card-title">Add Budget</h2>
                <div id="budget-form-error" class="error-state mb-4" style="display:none"></div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="bf-category">Category <span class="text-danger">*</span></label>
                        <select id="bf-category">
                            <option value="">Select category…</option>
                        </select>
                        <span class="form-hint">Spending category to set a limit for</span>
                    </div>
                    <div class="form-group">
                        <label for="bf-amount">Amount (£) <span class="text-danger">*</span></label>
                        <input type="number" id="bf-amount" step="0.01" min="0.01"
                               placeholder="e.g. 250.00">
                        <span class="form-hint">Monthly or weekly spending limit</span>
                    </div>
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label for="bf-period">Period</label>
                        <select id="bf-period">
                            <option value="monthly">Monthly</option>
                            <option value="weekly">Weekly</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="bf-start-date">Start Date (optional)</label>
                        <input type="date" id="bf-start-date">
                        <span class="form-hint">When this budget takes effect</span>
                    </div>
                </div>
                <div class="form-actions">
                    <button type="button" id="btn-save-budget" class="btn btn-primary">Save</button>
                    <button type="button" id="btn-cancel-budget" class="btn btn-ghost">Cancel</button>
                </div>
            </div>
        </div>

        <!-- Budgets table -->
        <div class="card">
            <div class="flex items-center justify-between mb-4">
                <h2 class="card-title" style="margin-bottom:0">Budgets</h2>
                <button type="button" id="btn-add-budget" class="btn btn-primary">+ Add Budget</button>
            </div>
            <div id="budget-loading" class="loading">Loading budgets…</div>
            <div id="budget-error" class="error-state" style="display:none"></div>
            <div id="budget-empty" class="text-muted" style="display:none;padding:var(--space-4) 0">
                No budgets yet. Add one to start tracking your spending limits.
            </div>
            <div id="budget-table-wrap" class="table-container" style="display:none">
                <table>
                    <thead>
                        <tr>
                            <th>Category</th>
                            <th style="text-align:right">Amount</th>
                            <th>Period</th>
                            <th>Start Date</th>
                            <th style="width:70px">Active</th>
                            <th style="width:120px">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="budget-body"></tbody>
                </table>
            </div>
        </div>
    `;

    attachListeners(container);
    await loadBudgets();
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadBudgets() {
    const loading = document.getElementById('budget-loading');
    const error = document.getElementById('budget-error');
    const tableWrap = document.getElementById('budget-table-wrap');
    const empty = document.getElementById('budget-empty');

    loading.style.display = '';
    error.style.display = 'none';
    tableWrap.style.display = 'none';
    empty.style.display = 'none';

    try {
        const [budgetData, catData] = await Promise.all([
            api.get('/api/budgets/'),
            api.get('/api/categories/'),
        ]);
        budgets = budgetData.budgets;
        categories = catData.categories;

        loading.style.display = 'none';
        if (budgets.length === 0) {
            empty.style.display = '';
        } else {
            renderBudgetRows();
            tableWrap.style.display = '';
        }
    } catch (err) {
        loading.style.display = 'none';
        error.style.display = '';
        error.textContent = `Failed to load budgets: ${err.message}`;
    }
}

// ---------------------------------------------------------------------------
// Table rendering
// ---------------------------------------------------------------------------

const _PERIOD_LABELS = {
    monthly: 'Monthly',
    weekly: 'Weekly',
};

function _categoryDisplayName(name) {
    const cat = categories.find(c => c.name === name);
    return cat ? (cat.icon ? cat.icon + ' ' : '') + cat.display_name : name;
}

function _categoryColour(name) {
    const cat = categories.find(c => c.name === name);
    return cat ? cat.colour : '#6B7280';
}

function renderBudgetRows() {
    const tbody = document.getElementById('budget-body');
    if (!tbody) return;

    tbody.innerHTML = budgets.map(b => `
        <tr style="${b.is_active ? '' : 'opacity:0.5'}">
            <td>
                <span class="colour-swatch" style="background:${escHtml(_categoryColour(b.category))}"></span>
                ${escHtml(_categoryDisplayName(b.category))}
            </td>
            <td style="text-align:right">
                <span class="mono">${formatCurrency(b.amount, false)}</span>
            </td>
            <td>
                <span class="badge badge-neutral">${escHtml(_PERIOD_LABELS[b.period] ?? b.period)}</span>
            </td>
            <td class="text-secondary">${b.start_date ? escHtml(b.start_date) : '—'}</td>
            <td>
                <button class="btn btn-ghost" style="padding:2px 8px;font-size:12px"
                        data-budget-toggle="${b.id}">
                    ${b.is_active ? 'On' : 'Off'}
                </button>
            </td>
            <td>
                <div class="flex gap-2">
                    <button class="btn btn-ghost" style="padding:2px 8px;font-size:12px"
                            data-budget-edit="${b.id}">Edit</button>
                    <button class="btn btn-danger" style="padding:2px 8px;font-size:12px"
                            data-budget-delete="${b.id}">Delete</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// ---------------------------------------------------------------------------
// Form handling
// ---------------------------------------------------------------------------

function _populateCategoryDropdown() {
    const select = document.getElementById('bf-category');
    select.innerHTML = '<option value="">Select category…</option>' +
        categories.map(c =>
            `<option value="${escHtml(c.name)}">${c.icon ? escHtml(c.icon) + ' ' : ''}${escHtml(c.display_name)}</option>`
        ).join('');
}

function showForm(mode, budget = null) {
    formMode = mode;
    editId = budget ? budget.id : null;

    const section = document.getElementById('budget-form-section');
    const title = document.getElementById('budget-form-title');
    const errorDiv = document.getElementById('budget-form-error');

    title.textContent = mode === 'add' ? 'Add Budget' : 'Edit Budget';
    errorDiv.style.display = 'none';

    _populateCategoryDropdown();

    document.getElementById('bf-category').value = budget ? budget.category : '';
    document.getElementById('bf-amount').value = budget ? budget.amount : '';
    document.getElementById('bf-period').value = budget ? budget.period : 'monthly';
    document.getElementById('bf-start-date').value = budget?.start_date ?? '';

    section.style.display = '';
    document.getElementById(mode === 'add' ? 'bf-category' : 'bf-amount').focus();
}

function hideForm() {
    formMode = null;
    editId = null;
    document.getElementById('budget-form-section').style.display = 'none';
    document.getElementById('budget-form-error').style.display = 'none';
}

async function saveBudget() {
    const category = document.getElementById('bf-category').value;
    const amountStr = document.getElementById('bf-amount').value.trim();
    const period = document.getElementById('bf-period').value;
    const startDate = document.getElementById('bf-start-date').value || null;
    const errorDiv = document.getElementById('budget-form-error');
    const saveBtn = document.getElementById('btn-save-budget');

    // Client-side validation
    if (!category) {
        errorDiv.textContent = 'Category is required.';
        errorDiv.style.display = '';
        document.getElementById('bf-category').focus();
        return;
    }
    const amount = parseFloat(amountStr);
    if (!amountStr || isNaN(amount) || amount <= 0) {
        errorDiv.textContent = 'Amount must be a positive number.';
        errorDiv.style.display = '';
        document.getElementById('bf-amount').focus();
        return;
    }

    errorDiv.style.display = 'none';
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';

    try {
        const body = { category, amount, period, start_date: startDate };
        if (formMode === 'add') {
            await api.post('/api/budgets/', body);
        } else {
            await api.put(`/api/budgets/${editId}`, body);
        }
        hideForm();
        await loadBudgets();
    } catch (err) {
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
}

async function deleteBudget(id) {
    const budget = budgets.find(b => b.id === id);
    if (!budget) return;

    const catName = _categoryDisplayName(budget.category);
    if (!confirm(`Delete budget for "${catName}"? This cannot be undone.`)) return;

    try {
        await api.del(`/api/budgets/${id}`);
        await loadBudgets();
    } catch (err) {
        const errorDiv = document.getElementById('budget-error');
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    }
}

async function toggleBudget(id) {
    try {
        await api.post(`/api/budgets/${id}/toggle`);
        await loadBudgets();
    } catch (err) {
        const errorDiv = document.getElementById('budget-error');
        errorDiv.textContent = err.message;
        errorDiv.style.display = '';
    }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

function attachListeners(container) {
    container.querySelector('#btn-add-budget').addEventListener('click', () => {
        showForm('add');
    });

    container.querySelector('#btn-save-budget').addEventListener('click', saveBudget);
    container.querySelector('#btn-cancel-budget').addEventListener('click', hideForm);

    // Table delegation: edit / delete / toggle buttons
    container.querySelector('#budget-body').addEventListener('click', (e) => {
        const editBtn = e.target.closest('[data-budget-edit]');
        if (editBtn) {
            const id = Number(editBtn.dataset.budgetEdit);
            const budget = budgets.find(b => b.id === id);
            if (budget) showForm('edit', budget);
            return;
        }

        const deleteBtn = e.target.closest('[data-budget-delete]');
        if (deleteBtn) {
            const id = Number(deleteBtn.dataset.budgetDelete);
            deleteBudget(id);
            return;
        }

        const toggleBtn = e.target.closest('[data-budget-toggle]');
        if (toggleBtn) {
            const id = Number(toggleBtn.dataset.budgetToggle);
            toggleBudget(id);
        }
    });

    // Enter key in form submits
    const formSection = container.querySelector('#budget-form-section');
    formSection.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveBudget();
        }
    });
}
