/**
 * dashboard.js — Dashboard view (Phase 3).
 * Shows combined finance + trading overview.
 */

export async function render(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1>Dashboard</h1>
            <p>Finance and trading overview — coming in Phase 3.</p>
        </div>
        <p class="text-muted">Add transactions via the Transactions page or upload a Monzo CSV to get started.</p>
    `;
}
