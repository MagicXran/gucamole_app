import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "patch-guacd-rdpdr-drive-name.py"


def _load_patch_module():
    spec = importlib.util.spec_from_file_location("guacd_patch", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_patch_replaces_only_pinned_call_bytes():
    module = _load_patch_module()
    data = bytearray(module.CALL_OFFSET + len(module.ORIGINAL_CALL) + 8)
    data[module.CALL_OFFSET : module.CALL_OFFSET + 5] = module.ORIGINAL_CALL

    patched = module.patch_bytes(bytes(data))

    assert patched[: module.CALL_OFFSET] == data[: module.CALL_OFFSET]
    assert patched[module.CALL_OFFSET : module.CALL_OFFSET + 5] == module.PATCHED_CALL
    assert patched[module.CALL_OFFSET + 5 :] == data[module.CALL_OFFSET + 5 :]


def test_patch_rejects_unknown_or_already_patched_bytes():
    module = _load_patch_module()
    data = bytearray(module.CALL_OFFSET + 5)

    with pytest.raises(ValueError, match="unexpected bytes"):
        module.patch_bytes(bytes(data))

    data[module.CALL_OFFSET : module.CALL_OFFSET + 5] = module.PATCHED_CALL
    with pytest.raises(ValueError, match="already applied"):
        module.patch_bytes(bytes(data))
