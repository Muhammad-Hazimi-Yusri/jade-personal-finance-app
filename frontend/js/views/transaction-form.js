/**
 * transaction-form.js — Add / Edit transaction form (Phase 1.7).
 *
 * Routes:
 *   #/transactions/new        → add mode (empty form, date defaults to today)
 *   #/transactions/edit/:id   → edit mode (pre-populated from API)
 */

import { api } from '../api.js';
import { escHtml } from '../utils.js';
import { showToast } from '../toast.js';

// ---- Module-level state ----

let formState = { mode: 'add', id: null, saving: false };
let categoriesCache = [];

// ---- Route parsing ----

function parseRoute() {
    const hash = window.location.hash.replace(/^#\/?/, '');
    if (hash === 'transactions/new') {
        return { mode: 'add', id: null };
    }
    const match = hash.match(/^transactions\/edit\/(\d+)$/);
    if (match) {
        return { mode: 'edit', id: parseInt(match[1], 10) };
    }
    return { mode: 'add', id: null };
}

// ---- Render entry point ----

export async function render(container) {
    formState = { ...parseRoute(), saving: false };
    categoriesCache = [];

    const isEdit = formState.mode === 'edit';
    const title = isEdit ? 'Edit Transaction' : 'Add Transaction';
    const subtitle = isEdit
        ? 'Update the details of this transaction.'
        : 'Manually record an income or expense.';

    container.innerHTML = `
        <div class="page-header">
            <a href="#/transactions" class="text-secondary" style="font-size: 13px;">&larr; Back to Transactions</a>
            <h1 style="margin-top: var(--space-2);">${title}</h1>
            <p class="text-secondary">${subtitle}</p>
        </div>

        <div class="card" style="max-width: 640px;">
            <form id="tx-form" novalidate>
                <!-- Date & Name -->
                <div class="grid-2">
                    <div class="form-group" id="fg-date">
                        <label for="f-date">Date <span class="text-danger">*</span></label>
                        <input id="f-date" type="date" required>
                    </div>
                    <div class="form-group" id="fg-name">
                        <label for="f-name">Name <span class="text-danger">*</span></label>
                        <input id="f-name" type="text" placeholder="e.g. Tesco, Uber, Salary" required>
                    </div>
                </div>

                <!-- Amount & Category -->
                <div class="grid-2">
                    <div class="form-group" id="fg-amount">
                        <label for="f-amount">Amount (&pound;) <span class="text-danger">*</span></label>
                        <input id="f-amount" type="number" step="0.01" placeholder="-12.50" required>
                        <span class="form-hint">Negative for expenses, positive for income</span>
                    </div>
                    <div class="form-group" id="fg-category">
                        <label for="f-category">Category <span class="text-danger">*</span></label>
                        <select id="f-category" required>
                            <option value="">Select a category</option>
                        </select>
                    </div>
                </div>

                <!-- Notes -->
                <div class="form-group" id="fg-notes">
                    <label for="f-notes">Notes</label>
                    <textarea id="f-notes" rows="3" placeholder="Add notes or #tags"></textarea>
                </div>

                <!-- Optional fields -->
                <details>
                    <summary>More details</summary>
                    <div class="grid-2">
                        <div class="form-group">
                            <label for="f-type">Type</label>
                            <input id="f-type" type="text" placeholder="e.g. Card payment, Direct debit">
                        </div>
                        <div class="form-group">
                            <label for="f-currency">Currency</label>
                            <input id="f-currency" type="text" maxlength="3" placeholder="GBP" value="GBP">
                        </div>
                    </div>
                </details>

                <!-- Error banner -->
                <div id="form-error" class="error-state" style="display: none; margin-top: var(--space-4);"></div>

                <!-- Action buttons -->
                <div class="form-actions">
                    <button type="submit" id="btn-save" class="btn btn-primary">
                        ${isEdit ? 'Save Changes' : 'Save Transaction'}
                    </button>
                    <a href="#/transactions" class="btn btn-ghost">Cancel</a>
                    ${isEdit ? '<button type="button" id="btn-delete" class="btn btn-danger">Delete</button>' : ''}
                </div>
            </form>
        </div>
    `;

    attachListeners();
    await loadCategories();

    if (isEdit) {
        await loadTransaction();
    } else {
        // Default date to today
        document.getElementById('f-date').value = new Date().toISOString().split('T')[0];
    }
}

// ---- Data loading ----

async function loadCategories() {
    try {
        const data = await api.get('/api/categories/');
        categoriesCache = data.categories ?? [];
        const sel = document.getElementById('f-category');
        if (!sel) return;
        categoriesCache.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.name;
            opt.textContent = cat.display_name;
            sel.appendChild(opt);
        });
    } catch {
        // Non-fatal — category select will just have the placeholder
    }
}

async function loadTransaction() {
    try {
        const tx = await api.get(`/api/transactions/${formState.id}`);

        document.getElementById('f-date').value = tx.date ? tx.date.split('T')[0] : '';
        document.getElementById('f-name').value = tx.name ?? '';
        document.getElementById('f-amount').value = tx.amount ?? '';
        document.getElementById('f-category').value = tx.category ?? '';
        document.getElementById('f-notes').value = tx.notes ?? '';
        document.getElementById('f-type').value = tx.type ?? '';
        document.getElementById('f-currency').value = tx.currency ?? 'GBP';

        // Open details section if optional fields have values
        if (tx.type) {
            document.querySelector('details').open = true;
        }
    } catch (err) {
        const form = document.getElementById('tx-form');
        form.innerHTML = `
            <div class="error-state">
                <strong>Failed to load transaction</strong>
                <p class="mt-2">${escHtml(err.message)}</p>
                <a href="#/transactions" class="btn btn-ghost mt-4">Back to Transactions</a>
            </div>`;
    }
}

// ---- Validation ----

function validate() {
    const errors = [];

    // Clear previous error states
    document.querySelectorAll('.form-group--error').forEach(el => {
        el.classList.remove('form-group--error');
    });

    const date = document.getElementById('f-date').value;
    const name = document.getElementById('f-name').value.trim();
    const amount = document.getElementById('f-amount').value;
    const category = document.getElementById('f-category').value;

    if (!date) {
        errors.push('Date is required');
        document.getElementById('fg-date').classList.add('form-group--error');
    }
    if (!name) {
        errors.push('Name is required');
        document.getElementById('fg-name').classList.add('form-group--error');
    }
    if (!amount || parseFloat(amount) === 0 || isNaN(parseFloat(amount))) {
        errors.push('Amount must be a non-zero number');
        document.getElementById('fg-amount').classList.add('form-group--error');
    }
    if (!category) {
        errors.push('Category is required');
        document.getElementById('fg-category').classList.add('form-group--error');
    }

    return errors;
}

// ---- Save / Delete ----

async function saveTransaction() {
    const errors = validate();
    const errorEl = document.getElementById('form-error');

    if (errors.length > 0) {
        errorEl.innerHTML = `<strong>Please fix the following:</strong><ul style="margin-top: var(--space-2); padding-left: var(--space-4);">${errors.map(e => `<li>${escHtml(e)}</li>`).join('')}</ul>`;
        errorEl.style.display = '';
        return;
    }

    errorEl.style.display = 'none';

    const payload = {
        date: document.getElementById('f-date').value,
        name: document.getElementById('f-name').value.trim(),
        amount: parseFloat(document.getElementById('f-amount').value),
        category: document.getElementById('f-category').value,
    };

    const notes = document.getElementById('f-notes').value.trim();
    const type = document.getElementById('f-type').value.trim();
    const currency = document.getElementById('f-currency').value.trim();

    // Include optional fields — send empty string to allow clearing
    if (formState.mode === 'edit') {
        payload.notes = notes;
        payload.type = type;
        if (currency) payload.currency = currency;
    } else {
        if (notes) payload.notes = notes;
        if (type) payload.type = type;
        if (currency && currency !== 'GBP') payload.currency = currency;
    }

    formState.saving = true;
    const btn = document.getElementById('btn-save');
    btn.disabled = true;
    btn.textContent = 'Saving…';

    try {
        if (formState.mode === 'edit') {
            await api.put(`/api/transactions/${formState.id}`, payload);
            showToast('Transaction updated', 'success');
        } else {
            await api.post('/api/transactions/', payload);
            showToast('Transaction saved', 'success');
        }
        window.location.hash = '#/transactions';
    } catch (err) {
        errorEl.innerHTML = `<strong>Save failed</strong><p class="mt-2">${escHtml(err.message)}</p>`;
        errorEl.style.display = '';
        showToast(`Could not save transaction: ${err.message}`, 'error');
        btn.disabled = false;
        btn.textContent = formState.mode === 'edit' ? 'Save Changes' : 'Save Transaction';
        formState.saving = false;
    }
}

async function deleteTransaction() {
    if (!confirm('Delete this transaction? This cannot be undone.')) return;

    const btn = document.getElementById('btn-delete');
    btn.disabled = true;
    btn.textContent = 'Deleting…';

    try {
        await api.del(`/api/transactions/${formState.id}`);
        showToast('Transaction deleted', 'success');
        window.location.hash = '#/transactions';
    } catch (err) {
        const errorEl = document.getElementById('form-error');
        errorEl.innerHTML = `<strong>Delete failed</strong><p class="mt-2">${escHtml(err.message)}</p>`;
        errorEl.style.display = '';
        showToast(`Could not delete transaction: ${err.message}`, 'error');
        btn.disabled = false;
        btn.textContent = 'Delete';
    }
}

// ---- Event listeners ----

function attachListeners() {
    document.getElementById('tx-form').addEventListener('submit', e => {
        e.preventDefault();
        if (!formState.saving) saveTransaction();
    });

    const deleteBtn = document.getElementById('btn-delete');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deleteTransaction);
    }
}
