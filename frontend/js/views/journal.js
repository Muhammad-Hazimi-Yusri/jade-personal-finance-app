/**
 * journal.js — Daily trading journal view.
 *
 * Route: #/journal
 * Two-column layout: date-navigable entry form on the left,
 * recent entries list on the right.
 */

import { api } from '../api.js';
import { escHtml } from '../utils.js';

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

let state = {
    date: todayISO(),
    entry: null,   // currently loaded entry dict, or null
    saving: false,
};

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export async function render(container) {
    state = { date: todayISO(), entry: null, saving: false };

    container.innerHTML = buildShellHTML();
    attachListeners();
    await loadDate(state.date);
    await loadRecentEntries();
}

// ---------------------------------------------------------------------------
// Shell HTML
// ---------------------------------------------------------------------------

function buildShellHTML() {
    return `
<div class="page-header">
    <h1>Journal</h1>
    <p class="text-secondary">Daily market outlook, trade plan, and end-of-day review.</p>
</div>

<div class="journal-layout">
    <!-- Left: entry form -->
    <div class="card journal-form-card">
        <div class="journal-date-nav">
            <button class="btn btn-ghost btn-icon" id="j-prev" title="Previous day">&#8592;</button>
            <input type="date" id="j-date" class="input journal-date-input" />
            <button class="btn btn-ghost btn-icon" id="j-next" title="Next day">&#8594;</button>
            <span id="j-status" class="journal-status text-muted"></span>
        </div>

        <form id="j-form" class="journal-form" novalidate>
            <div class="form-group">
                <label class="form-label" for="j-outlook">Market Outlook</label>
                <textarea id="j-outlook" class="input journal-textarea" rows="3"
                    placeholder="What's your read on the market today?"></textarea>
            </div>

            <div class="form-group">
                <label class="form-label" for="j-plan">Trade Plan</label>
                <textarea id="j-plan" class="input journal-textarea" rows="4"
                    placeholder="Which setups are you watching? Entry triggers, levels, size…"></textarea>
            </div>

            <div class="form-group">
                <label class="form-label" for="j-review">End-of-Day Review</label>
                <textarea id="j-review" class="input journal-textarea" rows="4"
                    placeholder="How did the day go? Did you follow the plan?"></textarea>
            </div>

            <div class="form-group">
                <label class="form-label">Mood</label>
                <div class="mood-picker" id="j-mood-picker">
                    <button type="button" class="mood-btn" data-mood="1" title="Terrible">😞<span>1</span></button>
                    <button type="button" class="mood-btn" data-mood="2" title="Bad">😕<span>2</span></button>
                    <button type="button" class="mood-btn" data-mood="3" title="Neutral">😐<span>3</span></button>
                    <button type="button" class="mood-btn" data-mood="4" title="Good">🙂<span>4</span></button>
                    <button type="button" class="mood-btn" data-mood="5" title="Great">😄<span>5</span></button>
                </div>
            </div>

            <div class="form-group">
                <label class="form-label" for="j-lessons">Lessons Learned</label>
                <textarea id="j-lessons" class="input journal-textarea" rows="3"
                    placeholder="What will you take into tomorrow?"></textarea>
            </div>

            <div class="journal-actions">
                <button type="submit" class="btn btn-primary" id="j-save">Save Entry</button>
                <button type="button" class="btn btn-danger-ghost" id="j-delete" style="display:none">
                    Delete Entry
                </button>
            </div>
        </form>
    </div>

    <!-- Right: recent entries -->
    <div class="journal-sidebar">
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Recent Entries</h3>
            </div>
            <div id="j-entries-list" class="journal-entries-list">
                <p class="text-muted" style="padding: var(--space-3);">Loading…</p>
            </div>
        </div>
    </div>
</div>`;
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

function attachListeners() {
    document.getElementById('j-date').addEventListener('change', e => {
        loadDate(e.target.value);
    });

    document.getElementById('j-prev').addEventListener('click', () => {
        shiftDate(-1);
    });

    document.getElementById('j-next').addEventListener('click', () => {
        shiftDate(1);
    });

    document.getElementById('j-form').addEventListener('submit', async e => {
        e.preventDefault();
        await saveEntry();
    });

    document.getElementById('j-delete').addEventListener('click', async () => {
        await deleteEntry();
    });

    document.getElementById('j-mood-picker').addEventListener('click', e => {
        const btn = e.target.closest('.mood-btn');
        if (!btn) return;
        selectMood(parseInt(btn.dataset.mood, 10));
    });
}

// ---------------------------------------------------------------------------
// Date navigation
// ---------------------------------------------------------------------------

function todayISO() {
    return new Date().toISOString().split('T')[0];
}

function shiftDate(days) {
    const d = new Date(state.date + 'T00:00:00');
    d.setDate(d.getDate() + days);
    const next = d.toISOString().split('T')[0];
    loadDate(next);
}

// ---------------------------------------------------------------------------
// Load entry for a date
// ---------------------------------------------------------------------------

async function loadDate(date) {
    state.date = date;
    document.getElementById('j-date').value = date;
    setStatus('');

    let entry = null;
    try {
        const data = await api.get(`/api/journal/${date}`);
        entry = data.entry;
    } catch (err) {
        // 404 is expected when no entry exists — treat as empty form
        if (!err.message.includes('404') && !err.message.toLowerCase().includes('not found')) {
            setStatus('Failed to load entry.');
            console.error(err);
        }
    }

    state.entry = entry;
    populateForm(entry);
    toggleDeleteButton(entry !== null);
}

// ---------------------------------------------------------------------------
// Populate / clear form
// ---------------------------------------------------------------------------

function populateForm(entry) {
    document.getElementById('j-outlook').value  = entry?.market_outlook ?? '';
    document.getElementById('j-plan').value     = entry?.plan           ?? '';
    document.getElementById('j-review').value   = entry?.review         ?? '';
    document.getElementById('j-lessons').value  = entry?.lessons        ?? '';
    selectMood(entry?.mood ?? null);
}

function selectMood(mood) {
    document.querySelectorAll('.mood-btn').forEach(btn => {
        btn.classList.toggle('mood-btn--active', parseInt(btn.dataset.mood, 10) === mood);
    });
}

function getSelectedMood() {
    const active = document.querySelector('.mood-btn--active');
    return active ? parseInt(active.dataset.mood, 10) : null;
}

function toggleDeleteButton(show) {
    document.getElementById('j-delete').style.display = show ? '' : 'none';
}

function setStatus(msg) {
    document.getElementById('j-status').textContent = msg;
}

// ---------------------------------------------------------------------------
// Save entry
// ---------------------------------------------------------------------------

async function saveEntry() {
    if (state.saving) return;
    state.saving = true;

    const btn = document.getElementById('j-save');
    btn.disabled = true;
    btn.textContent = 'Saving…';

    const payload = {
        date:           state.date,
        market_outlook: document.getElementById('j-outlook').value.trim() || null,
        plan:           document.getElementById('j-plan').value.trim()    || null,
        review:         document.getElementById('j-review').value.trim()  || null,
        mood:           getSelectedMood(),
        lessons:        document.getElementById('j-lessons').value.trim() || null,
    };

    try {
        const data = await api.post('/api/journal/', payload);
        state.entry = data.entry;
        setStatus('Saved.');
        toggleDeleteButton(true);
        await loadRecentEntries();
    } catch (err) {
        setStatus(`Error: ${err.message}`);
    } finally {
        state.saving = false;
        btn.disabled = false;
        btn.textContent = 'Save Entry';
    }
}

// ---------------------------------------------------------------------------
// Delete entry
// ---------------------------------------------------------------------------

async function deleteEntry() {
    if (!state.entry) return;
    if (!confirm(`Delete journal entry for ${state.date}?`)) return;

    try {
        await api.del(`/api/journal/${state.date}`);
        state.entry = null;
        populateForm(null);
        setStatus('Entry deleted.');
        toggleDeleteButton(false);
        await loadRecentEntries();
    } catch (err) {
        setStatus(`Error: ${err.message}`);
    }
}

// ---------------------------------------------------------------------------
// Recent entries list
// ---------------------------------------------------------------------------

async function loadRecentEntries() {
    const listEl = document.getElementById('j-entries-list');
    if (!listEl) return;

    let entries = [];
    try {
        const data = await api.get('/api/journal/?limit=30');
        entries = data.entries;
    } catch (err) {
        listEl.innerHTML = `<p class="text-muted" style="padding: var(--space-3);">Failed to load entries.</p>`;
        return;
    }

    if (entries.length === 0) {
        listEl.innerHTML = `<p class="text-muted" style="padding: var(--space-3);">No entries yet.</p>`;
        return;
    }

    listEl.innerHTML = entries.map(e => {
        const isActive = e.date === state.date;
        const moodEmoji = moodToEmoji(e.mood);
        const hasReview = e.review || e.plan || e.market_outlook;
        const dot = hasReview
            ? '<span class="entry-dot entry-dot--filled"></span>'
            : '<span class="entry-dot"></span>';
        return `
            <button type="button"
                class="journal-entry-row${isActive ? ' journal-entry-row--active' : ''}"
                data-date="${escHtml(e.date)}">
                ${dot}
                <span class="entry-date">${escHtml(e.date)}</span>
                <span class="entry-mood">${moodEmoji}</span>
            </button>`;
    }).join('');

    listEl.querySelectorAll('.journal-entry-row').forEach(btn => {
        btn.addEventListener('click', () => loadDate(btn.dataset.date));
    });
}

function moodToEmoji(mood) {
    const map = { 1: '😞', 2: '😕', 3: '😐', 4: '🙂', 5: '😄' };
    return mood != null ? map[mood] ?? '—' : '—';
}
