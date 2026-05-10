/**
 * Auth bootstrap pro dashboard.
 *
 * - Pokud /health vrátí 503 nebo /status vrátí 401, zeptá se na DASHBOARD_TOKEN
 *   a uloží jej do localStorage.
 * - Wrapuje globální fetch() — všechny following volání automaticky doplní
 *   `Authorization: Bearer <token>` header.
 * - Při 401 odpovědi token zneplatní a vyzve k zadání znovu.
 */
(function () {
    const STORAGE_KEY = 'gca_dashboard_token';

    function getToken() {
        try { return localStorage.getItem(STORAGE_KEY) || ''; }
        catch (_) { return ''; }
    }
    function setToken(t) {
        try { localStorage.setItem(STORAGE_KEY, t || ''); }
        catch (_) { /* private mode */ }
    }
    function clearToken() {
        try { localStorage.removeItem(STORAGE_KEY); }
        catch (_) { /* */ }
    }

    function promptForToken(reason) {
        const msg = reason
            ? `${reason}\n\nVlož DASHBOARD_TOKEN (z .env):`
            : 'Vlož DASHBOARD_TOKEN pro přístup k dashboardu:';
        const t = window.prompt(msg, '');
        if (t && t.trim()) {
            setToken(t.trim());
            // Reload, aby každé in-flight volání běželo s novým tokenem.
            window.location.reload();
        }
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = function patchedFetch(input, init) {
        init = init || {};
        const headers = new Headers(init.headers || (typeof input !== 'string' && input.headers) || {});
        const token = getToken();
        if (token && !headers.has('Authorization')) {
            headers.set('Authorization', 'Bearer ' + token);
        }
        const newInit = Object.assign({}, init, { headers });
        return originalFetch(input, newInit).then(function (resp) {
            // Auth selhal → zneplatnit a zeptat se znovu.
            // Ignoruj /health (může vracet 503 z jiných důvodů).
            const url = (typeof input === 'string') ? input : (input && input.url) || '';
            if (resp.status === 401 && !url.endsWith('/health')) {
                clearToken();
                promptForToken('Token byl odmítnut serverem.');
            }
            return resp;
        });
    };

    // Při startu — pokud je DASHBOARD_TOKEN povinný a my žádný nemáme, vyzvi.
    document.addEventListener('DOMContentLoaded', function () {
        if (getToken()) return;
        // Cheap probe — /status nyní vyžaduje auth.
        originalFetch('/status').then(function (r) {
            if (r.status === 401) promptForToken();
        }).catch(function () { /* offline OK */ });
    });
})();
