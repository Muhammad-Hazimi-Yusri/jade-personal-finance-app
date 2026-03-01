/**
 * settings.js — Settings view: categories, strategies, account management (Phase 1.8 / 4).
 */

export async function render(container) {
    container.innerHTML = `
        <div class="page-header">
            <h1>Settings</h1>
            <p>Manage categories, strategies, and trading accounts.</p>
        </div>
        <p class="text-muted">Category management comes in Phase 1.8. Strategy and account management in Phase 4.</p>
    `;
}
