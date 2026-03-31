const VIEWER_SUPPORTED_EXTENSIONS = new Set(['.vtp', '.vtu', '.stl', '.obj']);

export function normalizeViewerPath(inputPath) {
    var path = (inputPath || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    if (path.toLowerCase() === 'output') return '';
    if (path.toLowerCase().indexOf('output/') === 0) return path.slice(7);
    return path;
}

export function parentPath(path) {
    var parts = normalizeViewerPath(path).split('/').filter(function(part) { return part; });
    parts.pop();
    return parts.join('/');
}

export function baseName(path) {
    var parts = normalizeViewerPath(path).split('/');
    return parts[parts.length - 1] || '';
}

export function buildDatasetListUrl(path) {
    var normalizedPath = normalizeViewerPath(path);
    if (!normalizedPath) return '/api/datasets';
    return '/api/datasets?path=' + encodeURIComponent(normalizedPath);
}

export function buildDatasetFileCandidates(path) {
    var normalizedPath = normalizeViewerPath(path);
    var encodedPath = encodeURIComponent(normalizedPath);
    var legacyPath = normalizedPath
        .split('/')
        .filter(function(part) { return part; })
        .map(encodeURIComponent)
        .join('/');

    return [
        '/api/datasets/file?path=' + encodedPath,
        '/api/datasets/' + legacyPath,
    ];
}

function normalizeItem(item) {
    if (!item || typeof item !== 'object') return null;

    if (Object.prototype.hasOwnProperty.call(item, 'filename')) {
        return {
            name: item.filename,
            path: normalizeViewerPath(item.filename),
            is_dir: false,
            size_human: item.size_human || '',
            extension: String(item.extension || '').toLowerCase(),
        };
    }

    return {
        name: item.name || baseName(item.path || ''),
        path: normalizeViewerPath(item.path || item.name || ''),
        is_dir: Boolean(item.is_dir),
        size_human: item.size_human || '',
        extension: String(item.extension || '').toLowerCase(),
    };
}

function isRenderableItem(item) {
    if (!item) return false;
    if (item.is_dir) return true;
    return VIEWER_SUPPORTED_EXTENSIONS.has(item.extension);
}

export function extractDatasetItems(payload) {
    var path = '';
    var rawItems = [];

    if (Array.isArray(payload)) {
        rawItems = payload;
    } else if (payload && typeof payload === 'object') {
        path = normalizeViewerPath(payload.path || '');
        rawItems = Array.isArray(payload.items) ? payload.items : [];
    }

    return {
        path: path,
        items: rawItems
            .map(normalizeItem)
            .filter(isRenderableItem),
    };
}
