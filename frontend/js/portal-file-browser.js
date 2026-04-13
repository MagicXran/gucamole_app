const VIEWER_EXTENSIONS = new Set(['.vtp', '.vtu', '.stl', '.obj']);
const FAST_REFRESH_DELAY_MS = 2000;
const STABLE_REFRESH_DELAY_MS = 10000;

function getExtension(name) {
    var idx = name.lastIndexOf('.');
    return idx >= 0 ? name.slice(idx).toLowerCase() : '';
}

export function isViewerResultFile(path) {
    return VIEWER_EXTENSIONS.has(getExtension(path || ''));
}

export function filterAndSortItems(items, options) {
    options = options || {};
    var query = String(options.query || '').trim().toLowerCase();
    var sortKey = options.sortKey || 'name';

    var filtered = (items || []).filter(function(item) {
        if (!query) return true;
        return String(item.name || '').toLowerCase().indexOf(query) !== -1;
    });

    filtered.sort(function(a, b) {
        if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
        if (sortKey === 'size') return Number(a.size || 0) - Number(b.size || 0) || String(a.name).localeCompare(String(b.name));
        if (sortKey === 'mtime') return Number(b.mtime || 0) - Number(a.mtime || 0) || String(a.name).localeCompare(String(b.name));
        return String(a.name).localeCompare(String(b.name));
    });

    return filtered;
}

export function groupItemsByExtension(items) {
    var directories = [];
    var groups = new Map();

    (items || []).forEach(function(item) {
        if (item.is_dir) {
            directories.push(item);
            return;
        }
        var ext = getExtension(item.name) || '其他';
        if (!groups.has(ext)) groups.set(ext, []);
        groups.get(ext).push(item);
    });

    var result = [];
    if (directories.length) {
        result.push({ label: '文件夹', items: directories });
    }
    Array.from(groups.keys()).sort().forEach(function(ext) {
        result.push({ label: ext, items: groups.get(ext) });
    });
    return result;
}

function itemFingerprint(item) {
    return [
        item && item.name || '',
        item && item.is_dir ? 'd' : 'f',
        Number(item && item.size || 0),
        Number(item && item.mtime || 0),
    ].join('|');
}

export function annotatePendingTransfers(items, previousItems, options) {
    options = options || {};
    var nowSeconds = Number(options.nowSeconds || Math.floor(Date.now() / 1000));
    var recentWindowSeconds = Number(options.recentWindowSeconds || 15);
    var previousMap = new Map();

    (previousItems || []).forEach(function(item) {
        previousMap.set(String(item.name || ''), itemFingerprint(item));
    });

    return (items || []).map(function(item) {
        var annotated = Object.assign({}, item);
        if (annotated.is_dir) {
            annotated.is_pending = false;
            return annotated;
        }

        var fingerprint = itemFingerprint(annotated);
        var previousFingerprint = previousMap.get(String(annotated.name || ''));
        var ageSeconds = Math.max(0, nowSeconds - Number(annotated.mtime || 0));
        annotated.is_pending = previousFingerprint !== fingerprint && ageSeconds <= recentWindowSeconds;
        return annotated;
    });
}

export function resolveRefreshDelay(options) {
    options = options || {};
    var nowMs = Number(options.nowMs || Date.now());
    var burstUntilMs = Number(options.burstUntilMs || 0);
    var hasPendingItems = !!options.hasPendingItems;
    if (hasPendingItems) return FAST_REFRESH_DELAY_MS;
    if (burstUntilMs > nowMs) return FAST_REFRESH_DELAY_MS;
    return STABLE_REFRESH_DELAY_MS;
}

if (typeof window !== 'undefined') {
    window.PortalFileBrowser = {
        filterAndSortItems: filterAndSortItems,
        groupItemsByExtension: groupItemsByExtension,
        isViewerResultFile: isViewerResultFile,
        annotatePendingTransfers: annotatePendingTransfers,
        resolveRefreshDelay: resolveRefreshDelay,
    };
}
