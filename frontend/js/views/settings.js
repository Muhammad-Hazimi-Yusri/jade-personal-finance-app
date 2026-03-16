/**
 * settings.js — Settings view: category management.
 *
 * Displays all categories in a table with colour swatches.
 * Provides inline add/edit form and delete with confirmation.
 */

import { api } from '../api.js';
import { escHtml } from '../utils.js';

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

let categories = [];
let formMode = null;   // null | 'add' | 'edit'
let editId = null;

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

export async function render(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1>Settings</h1>
            <p>Manage spending categories, colours, and icons.</p>
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
        <div class="card">
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
    `;

    attachListeners(container);
    await loadCategories();
}

// ---------------------------------------------------------------------------
// Data loading
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
// Table rendering
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
// Form handling
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
// Event listeners
// ---------------------------------------------------------------------------

function attachListeners(container) {
    // Add button
    container.querySelector('#btn-add-cat').addEventListener('click', () => {
        showForm('add');
    });

    // Save / Cancel
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

    // Enter key in form submits
    const formSection = container.querySelector('#cat-form-section');
    formSection.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveCategory();
        }
    });
}
