/**
 * trade-form.js — New / edit trade form (Phase 4).
 */

export async function render(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1>New Trade</h1>
            <p>Trade entry form with risk management and psychology fields — coming in Phase 4.</p>
        </div>
        <p class="text-muted">Log entry price, stop loss, position size, and more.</p>
    `;
}
