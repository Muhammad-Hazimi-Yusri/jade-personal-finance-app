/**
 * trades.js — Trade log view (Phase 4).
 */

export async function render(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1>Trade Log</h1>
            <p>Filterable log of all your trades — coming in Phase 4.</p>
        </div>
        <p class="text-muted">Track every trade across stocks, forex, crypto, and options.</p>
    `;
}
