/**
 * upload.js — Monzo CSV upload view (Phase 2.4).
 *
 * State machine: idle → uploading → success / error
 * Supports drag-and-drop and click-to-browse with client-side validation.
 */

import { api } from '../api.js';
import { escHtml } from '../utils.js';

/* ---- Module state ---- */

let containerEl = null;
let state = { phase: 'idle', file: null, result: null, error: null };

/* ---- Public entry point ---- */

export async function render(container) {
    containerEl = container;
    state = { phase: 'idle', file: null, result: null, error: null };
    renderIdle();
}

/* ---- Render helpers ---- */

function renderIdle() {
    containerEl.innerHTML = `
        <div class="page-header">
            <h1>Upload CSV</h1>
            <p>Import transactions from a Monzo CSV export.</p>
        </div>

        <div class="card" style="max-width: 640px;">
            <input type="file" id="file-input" accept=".csv" style="display: none;">

            <div id="drop-zone" class="drop-zone">
                <div class="drop-zone__icon">
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                </div>
                <p class="drop-zone__primary">Drop your Monzo CSV here</p>
                <p class="drop-zone__secondary">or click to browse</p>
                <p class="drop-zone__hint">CSV files only, max 10 MB</p>
            </div>

            <div id="file-info" class="file-info" style="display: none;"></div>

            <div id="upload-error" class="error-state" style="display: none;"></div>

            <div id="upload-actions" class="form-actions" style="display: none;">
                <button id="btn-upload" class="btn btn-primary">Import Transactions</button>
                <button id="btn-clear" class="btn btn-ghost">Clear</button>
            </div>
        </div>

        <p class="text-muted mt-4" style="max-width: 640px;">
            Export your statement from the Monzo app: Account &rarr; Download statement &rarr; CSV.
        </p>
    `;
    attachListeners();
}

function renderUploading() {
    const card = containerEl.querySelector('.card');
    card.innerHTML = `
        <div class="upload-spinner">
            <div class="upload-spinner__ring"></div>
            <p class="upload-spinner__text">Importing transactions&hellip;</p>
        </div>
    `;
}

function renderSuccess() {
    const r = state.result;
    const hasErrors = r.errors && r.errors.length > 0;

    let errorsHtml = '';
    if (hasErrors) {
        const items = r.errors
            .map(e => `<li>Row ${e.row_num}: ${escHtml(e.error)}</li>`)
            .join('');
        errorsHtml = `
            <div class="upload-summary__errors">
                <h3>${r.errors.length} Row Error${r.errors.length !== 1 ? 's' : ''}</h3>
                <ul>${items}</ul>
            </div>
        `;
    }

    containerEl.innerHTML = `
        <div class="page-header">
            <h1>Upload CSV</h1>
            <p>Import transactions from a Monzo CSV export.</p>
        </div>

        <div class="card" style="max-width: 640px;">
            <div class="upload-summary__header">
                <span class="upload-summary__icon text-success">&#10003;</span>
                <h2>Import Complete</h2>
            </div>

            <div class="upload-summary__stats">
                <div class="upload-stat">
                    <span class="upload-stat__value text-success">${r.imported}</span>
                    <span class="upload-stat__label">Imported</span>
                </div>
                <div class="upload-stat">
                    <span class="upload-stat__value text-warning">${r.skipped}</span>
                    <span class="upload-stat__label">Skipped</span>
                </div>
                <div class="upload-stat">
                    <span class="upload-stat__value text-info">${r.total}</span>
                    <span class="upload-stat__label">Total Rows</span>
                </div>
            </div>

            ${errorsHtml}

            <div class="form-actions mt-4">
                <a href="#/transactions" class="btn btn-primary">View Transactions</a>
                <button id="btn-another" class="btn btn-ghost">Upload Another</button>
            </div>
        </div>
    `;

    const btnAnother = containerEl.querySelector('#btn-another');
    if (btnAnother) {
        btnAnother.addEventListener('click', () => render(containerEl));
    }
}

function renderError() {
    containerEl.innerHTML = `
        <div class="page-header">
            <h1>Upload CSV</h1>
            <p>Import transactions from a Monzo CSV export.</p>
        </div>

        <div class="card" style="max-width: 640px;">
            <div class="error-state">
                <p><strong>Import failed</strong></p>
                <p>${escHtml(state.error)}</p>
            </div>

            <div class="form-actions mt-4">
                <button id="btn-retry" class="btn btn-primary">Try Again</button>
            </div>
        </div>
    `;

    containerEl.querySelector('#btn-retry')
        .addEventListener('click', () => render(containerEl));
}

/* ---- Event listeners ---- */

function attachListeners() {
    const dropZone = containerEl.querySelector('#drop-zone');
    const fileInput = containerEl.querySelector('#file-input');
    const btnUpload = containerEl.querySelector('#btn-upload');
    const btnClear = containerEl.querySelector('#btn-clear');
    let dragCounter = 0;

    // Click to browse
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        handleFile(fileInput.files[0]);
        fileInput.value = '';
    });

    // Drag-and-drop (counter technique prevents child-element flicker)
    dropZone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        dropZone.classList.add('drop-zone--dragover');
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
    });

    dropZone.addEventListener('dragleave', () => {
        dragCounter--;
        if (dragCounter === 0) {
            dropZone.classList.remove('drop-zone--dragover');
        }
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        dropZone.classList.remove('drop-zone--dragover');
        handleFile(e.dataTransfer.files[0]);
    });

    // Upload & clear buttons
    btnUpload.addEventListener('click', uploadFile);
    btnClear.addEventListener('click', () => render(containerEl));
}

/* ---- File handling ---- */

function handleFile(file) {
    if (!file) return;

    const errorDiv = containerEl.querySelector('#upload-error');
    errorDiv.style.display = 'none';

    const validationError = validateFile(file);
    if (validationError) {
        errorDiv.textContent = validationError;
        errorDiv.style.display = 'block';
        return;
    }

    state.file = file;

    // Show file info
    const fileInfo = containerEl.querySelector('#file-info');
    fileInfo.innerHTML = `
        <span class="file-info__name">${escHtml(file.name)}</span>
        <span class="file-info__size">${formatFileSize(file.size)}</span>
    `;
    fileInfo.style.display = 'flex';

    // Show action buttons
    containerEl.querySelector('#upload-actions').style.display = 'flex';

    // Update drop zone visual
    containerEl.querySelector('#drop-zone').classList.add('drop-zone--has-file');
}

function validateFile(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
        return 'Only .csv files are accepted. Please select a CSV file.';
    }
    if (file.size > 10 * 1024 * 1024) {
        return `File is too large (${formatFileSize(file.size)}). Maximum size is 10 MB.`;
    }
    return null;
}

async function uploadFile() {
    state.phase = 'uploading';
    renderUploading();

    try {
        const result = await api.upload('/api/upload/monzo', state.file);
        state.phase = 'success';
        state.result = result;
        renderSuccess();
    } catch (err) {
        state.phase = 'error';
        state.error = err.message;
        renderError();
    }
}

/* ---- Utilities ---- */

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
