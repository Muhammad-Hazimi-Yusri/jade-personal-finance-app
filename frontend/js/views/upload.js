/**
 * upload.js — Monzo CSV upload view (Phase 2).
 */

export async function render(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1>Upload CSV</h1>
            <p>Import transactions from a Monzo CSV export — coming in Phase 2.</p>
        </div>
        <p class="text-muted">Export your statement from the Monzo app and upload it here.</p>
    `;
}
