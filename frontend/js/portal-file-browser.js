const VIEWER_EXTENSIONS = new Set(['.vtp', '.vtu', '.stl', '.obj']);

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

if (typeof window !== 'undefined') {
    window.PortalFileBrowser = {
        filterAndSortItems: filterAndSortItems,
        groupItemsByExtension: groupItemsByExtension,
        isViewerResultFile: isViewerResultFile,
    };
}
