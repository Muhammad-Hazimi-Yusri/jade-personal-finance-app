/**
 * api.js — Fetch wrapper for all Jade API calls.
 *
 * All methods parse JSON and throw on non-2xx responses, including
 * the error message from the API body when available.
 *
 * Usage:
 *   import { api } from './api.js';
 *   const data = await api.get('/api/transactions');
 *   await api.post('/api/transactions', { name: 'Coffee', amount: -3.50, ... });
 */

/**
 * Core fetch helper.
 * @param {string} path    - Absolute path, e.g. '/api/transactions'
 * @param {object} options - fetch() options
 * @returns {Promise<any>} Parsed JSON response body
 */
async function request(path, options = {}) {
    const res = await fetch(path, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });

    // Try to extract a JSON error body for richer error messages
    let body;
    try {
        body = await res.json();
    } catch {
        body = null;
    }

    if (!res.ok) {
        const message = body?.error ?? body?.message ?? `HTTP ${res.status} ${res.statusText}`;
        throw new Error(message);
    }

    return body;
}

export const api = {
    /**
     * GET request.
     * @param {string} path - e.g. '/api/transactions?page=1'
     */
    get(path) {
        return request(path, { method: 'GET' });
    },

    /**
     * POST request with JSON body.
     * @param {string} path
     * @param {object} body
     */
    post(path, body) {
        return request(path, {
            method: 'POST',
            body: JSON.stringify(body),
        });
    },

    /**
     * PUT request with JSON body.
     * @param {string} path
     * @param {object} body
     */
    put(path, body) {
        return request(path, {
            method: 'PUT',
            body: JSON.stringify(body),
        });
    },

    /**
     * DELETE request.
     * @param {string} path
     */
    del(path) {
        return request(path, { method: 'DELETE' });
    },

    /**
     * Upload a file via multipart/form-data.
     * Uses fetch directly (not request()) because Content-Type must be
     * omitted so the browser sets the multipart boundary automatically.
     * @param {string} path - e.g. '/api/upload/monzo'
     * @param {File}   file - File object from input or drag-and-drop
     * @returns {Promise<any>} Parsed JSON response body
     */
    async upload(path, file) {
        const form = new FormData();
        form.append('file', file);

        const res = await fetch(path, { method: 'POST', body: form });

        let body;
        try {
            body = await res.json();
        } catch {
            body = null;
        }

        if (!res.ok) {
            const message = body?.error ?? body?.message ?? `HTTP ${res.status} ${res.statusText}`;
            throw new Error(message);
        }

        return body;
    },
};
