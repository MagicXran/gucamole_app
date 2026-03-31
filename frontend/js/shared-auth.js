function getToken() { return localStorage.getItem('portal_token'); }

function getUser() {
    try { return JSON.parse(localStorage.getItem('portal_user')); }
    catch (e) { return null; }
}

function authHeaders() { return { 'Authorization': 'Bearer ' + getToken() }; }

function logout() {
    localStorage.removeItem('portal_token');
    localStorage.removeItem('portal_user');
    window.location.href = '/login.html';
}

function requireAuth() {
    if (!getToken()) {
        window.location.href = '/login.html';
        return false;
    }
    return true;
}
