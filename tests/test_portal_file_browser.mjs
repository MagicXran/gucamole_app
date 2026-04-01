import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const source = await fs.readFile(new URL('../frontend/js/portal-file-browser.js', import.meta.url), 'utf8');
const mod = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

const ITEMS = [
  { name: 'Output', is_dir: true, size: 0, mtime: 30 },
  { name: 'mesh.vtu', is_dir: false, size: 200, mtime: 20 },
  { name: 'mesh.obj', is_dir: false, size: 100, mtime: 10 },
  { name: 'notes.txt', is_dir: false, size: 50, mtime: 40 },
];

test('filterAndSortItems keeps directories first and applies name filter', () => {
  const result = mod.filterAndSortItems(ITEMS, {
    query: 'mesh',
    sortKey: 'name',
  });

  assert.deepEqual(result.map((item) => item.name), ['mesh.obj', 'mesh.vtu']);
});

test('groupItemsByExtension creates grouped sections after directories', () => {
  const grouped = mod.groupItemsByExtension(ITEMS);

  assert.equal(grouped[0].label, '文件夹');
  assert.deepEqual(grouped[0].items.map((item) => item.name), ['Output']);
  assert.equal(grouped[1].label, '.obj');
  assert.equal(grouped[2].label, '.txt');
  assert.equal(grouped[3].label, '.vtu');
});

test('isViewerResultFile recognizes vtu as previewable', () => {
  assert.equal(mod.isViewerResultFile('nested/mesh.vtu'), true);
  assert.equal(mod.isViewerResultFile('nested/notes.txt'), false);
});
