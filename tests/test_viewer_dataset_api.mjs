import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const helperSource = await fs.readFile(
  new URL('../frontend/js/viewer_dataset_api.js', import.meta.url),
  'utf8',
);
const helperModule = await import(`data:text/javascript;base64,${Buffer.from(helperSource).toString('base64')}`);

const {
  buildDatasetFileCandidates,
  buildDatasetListUrl,
  buildDatasetPreviewUrl,
  extractDatasetItems,
  normalizeViewerPath,
  parentPath,
} = helperModule;

assert.equal(buildDatasetListUrl(''), '/api/datasets');
assert.equal(buildDatasetListUrl('nested/run-1'), '/api/datasets?path=nested%2Frun-1');
assert.equal(
  buildDatasetPreviewUrl('nested/mesh.vtu'),
  '/api/datasets/preview?path=nested%2Fmesh.vtu',
);

assert.deepEqual(
  buildDatasetFileCandidates('nested/mesh.obj'),
  [
    '/api/datasets/file?path=nested%2Fmesh.obj',
    '/api/datasets/nested/mesh.obj',
  ],
);

assert.equal(normalizeViewerPath('Output\\nested/demo.vtp'), 'nested/demo.vtp');
assert.equal(parentPath('nested/demo.vtp'), 'nested');
assert.equal(parentPath('nested'), '');

assert.deepEqual(
  extractDatasetItems([
    {
      filename: 'legacy.vtp',
      size_human: '1.0 KB',
      extension: '.vtp',
    },
  ]),
  {
    path: '',
    items: [
      {
        name: 'legacy.vtp',
        path: 'legacy.vtp',
        is_dir: false,
        size_human: '1.0 KB',
        extension: '.vtp',
      },
    ],
  },
);

assert.deepEqual(
  extractDatasetItems({
    path: 'nested',
    items: [
      {
        name: 'child',
        path: 'nested/child',
        is_dir: true,
        size_human: '',
        extension: '',
      },
      {
        name: 'mesh.vtu',
        path: 'nested/mesh.vtu',
        is_dir: false,
        size_human: '2.0 KB',
        extension: '.vtu',
      },
      {
        name: 'skip.gltf',
        path: 'nested/skip.gltf',
        is_dir: false,
        size_human: '3.0 KB',
        extension: '.gltf',
      },
    ],
  }),
  {
    path: 'nested',
    items: [
      {
        name: 'child',
        path: 'nested/child',
        is_dir: true,
        size_human: '',
        extension: '',
      },
      {
        name: 'mesh.vtu',
        path: 'nested/mesh.vtu',
        is_dir: false,
        size_human: '2.0 KB',
        extension: '.vtu',
      },
    ],
  },
);
