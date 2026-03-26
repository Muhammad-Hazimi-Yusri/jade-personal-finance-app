/**
 * date-range-selector.js — Reusable date range selector component (Phase 3.9).
 *
 * Provides preset quick-select buttons (This Month, Last Month, 3M, 6M, 12M,
 * YTD, Custom) and a custom date range with two <input type="date"> fields.
 *
 * Usage:
 *   import { createDateRangeSelector } from '../components/date-range-selector.js';
 *   const el = createDateRangeSelector({
 *       onChange: (startDate, endDate, label) => { ... },
 *       initialPreset: 'last_6m',
 *       id: 'dash-date-range',
 *   });
 *   container.appendChild(el);
 */


// ---------------------------------------------------------------------------
// Preset definitions
// ---------------------------------------------------------------------------

const PRESETS = [
    { key: 'this_month',  label: 'This Month' },
    { key: 'last_month',  label: 'Last Month' },
    { key: 'last_3m',     label: '3M' },
    { key: 'last_6m',     label: '6M' },
    { key: 'last_12m',    label: '12M' },
    { key: 'ytd',         label: 'YTD' },
    { key: 'custom',      label: 'Custom' },
];


/**
 * Compute start/end ISO date strings for a named preset.
 *
 * @param {string} presetKey  One of the preset keys defined above.
 * @param {Date}   [refDate]  Reference date (defaults to now).
 * @returns {{ startDate: string, endDate: string, label: string }}
 */
export function getPresetRange(presetKey, refDate) {
    const ref = refDate ? new Date(refDate) : new Date();
    const y = ref.getFullYear();
    const m = ref.getMonth();       // 0-based
    const today = _isoDate(ref);

    switch (presetKey) {
        case 'this_month':
            return {
                startDate: _isoDate(new Date(y, m, 1)),
                endDate: today,
                label: 'This Month',
            };
        case 'last_month': {
            const start = new Date(y, m - 1, 1);
            const end = new Date(y, m, 0);  // last day of previous month
            return {
                startDate: _isoDate(start),
                endDate: _isoDate(end),
                label: 'Last Month',
            };
        }
        case 'last_3m':
            return {
                startDate: _isoDate(new Date(y, m - 2, 1)),
                endDate: today,
                label: 'Last 3 Months',
            };
        case 'last_6m':
            return {
                startDate: _isoDate(new Date(y, m - 5, 1)),
                endDate: today,
                label: 'Last 6 Months',
            };
        case 'last_12m':
            return {
                startDate: _isoDate(new Date(y, m - 11, 1)),
                endDate: today,
                label: 'Last 12 Months',
            };
        case 'ytd':
            return {
                startDate: `${y}-01-01`,
                endDate: today,
                label: 'Year to Date',
            };
        default:
            // Fallback: this month
            return {
                startDate: _isoDate(new Date(y, m, 1)),
                endDate: today,
                label: 'This Month',
            };
    }
}


// ---------------------------------------------------------------------------
// Component factory
// ---------------------------------------------------------------------------

/**
 * Create a date range selector DOM element.
 *
 * @param {object}   options
 * @param {function} options.onChange       Called with (startDate, endDate, label)
 *                                         when the user selects a range.
 * @param {string}   [options.initialPreset='this_month']  Initial active preset key.
 * @param {string}   [options.id='date-range']             HTML id for the container.
 * @returns {HTMLElement}
 */
export function createDateRangeSelector({ onChange, initialPreset = 'this_month', id = 'date-range' }) {
    // State
    let activePreset = initialPreset;

    // Root element
    const root = document.createElement('div');
    root.className = 'date-range-selector';
    root.id = id;

    // Preset buttons row
    const presetsRow = document.createElement('div');
    presetsRow.className = 'date-range-presets';

    PRESETS.forEach(({ key, label }) => {
        const btn = document.createElement('button');
        btn.className = 'period-btn' + (key === activePreset ? ' period-btn--active' : '');
        btn.dataset.preset = key;
        btn.textContent = label;
        presetsRow.appendChild(btn);
    });

    root.appendChild(presetsRow);

    // Custom date range row
    const customRow = document.createElement('div');
    customRow.className = 'date-range-custom';
    customRow.style.display = activePreset === 'custom' ? '' : 'none';

    const startInput = document.createElement('input');
    startInput.type = 'date';
    startInput.className = 'date-range-start';
    startInput.title = 'Start date';

    const sep = document.createElement('span');
    sep.className = 'date-range-sep';
    sep.textContent = 'to';

    const endInput = document.createElement('input');
    endInput.type = 'date';
    endInput.className = 'date-range-end';
    endInput.title = 'End date';

    const applyBtn = document.createElement('button');
    applyBtn.className = 'btn btn-primary btn-sm';
    applyBtn.textContent = 'Apply';

    customRow.appendChild(startInput);
    customRow.appendChild(sep);
    customRow.appendChild(endInput);
    customRow.appendChild(applyBtn);
    root.appendChild(customRow);

    // --- Event handlers ---

    // Preset button click
    presetsRow.addEventListener('click', (e) => {
        const btn = e.target.closest('.period-btn');
        if (!btn) return;

        const key = btn.dataset.preset;
        if (key === activePreset && key !== 'custom') return;

        activePreset = key;

        // Update active state
        presetsRow.querySelectorAll('.period-btn').forEach(b =>
            b.classList.toggle('period-btn--active', b.dataset.preset === key)
        );

        if (key === 'custom') {
            // Show custom row; pre-fill with current month if empty
            customRow.style.display = '';
            if (!startInput.value) {
                const def = getPresetRange('this_month');
                startInput.value = def.startDate;
                endInput.value = def.endDate;
            }
        } else {
            customRow.style.display = 'none';
            const range = getPresetRange(key);
            onChange(range.startDate, range.endDate, range.label);
        }
    });

    // Apply button for custom range
    applyBtn.addEventListener('click', () => {
        const sd = startInput.value;
        const ed = endInput.value;
        if (!sd || !ed) return;
        if (sd > ed) {
            // Swap if reversed
            startInput.value = ed;
            endInput.value = sd;
            onChange(ed, sd, 'Custom');
        } else {
            onChange(sd, ed, 'Custom');
        }
    });

    return root;
}


// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

function _isoDate(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}
