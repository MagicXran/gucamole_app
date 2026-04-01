"""
结果预览转换服务：将 VTU 转为可由现有 viewer 渲染的 VTP。
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
import os
import time
import uuid
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def _load_drive_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)
    drive_cfg = config.get("guacamole", {}).get("drive", {})
    if "GUACAMOLE_DRIVE_BASE_PATH" in os.environ:
        drive_cfg["base_path"] = os.environ["GUACAMOLE_DRIVE_BASE_PATH"]
    if "GUACAMOLE_DRIVE_RESULTS_ROOT" in os.environ:
        drive_cfg["results_root"] = os.environ["GUACAMOLE_DRIVE_RESULTS_ROOT"]
    return drive_cfg


_drive_cfg = _load_drive_config()
DRIVE_BASE = Path(_drive_cfg.get("base_path", "/drive"))
RESULTS_ROOT_NAME = _drive_cfg.get("results_root", "Output")
PREVIEW_CACHE_DIR_NAME = ".preview_cache"
PREVIEW_LOCK_SUFFIX = ".lock"


class DatasetPreviewError(Exception):
    """预览转换基础异常"""


class DatasetPreviewPathError(DatasetPreviewError):
    """请求路径非法"""


class DatasetPreviewConfigError(DatasetPreviewError):
    """服务端配置异常"""


class DatasetPreviewNotFoundError(DatasetPreviewError):
    """源文件不存在"""


class DatasetPreviewUnavailableError(DatasetPreviewError):
    """VTK 依赖不可用"""


class DatasetPreviewConversionError(DatasetPreviewError):
    """VTU 转换失败"""


def _normalized_resolved_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and resolved.startswith("\\\\?\\"):
        return resolved[4:]
    return resolved


def _ensure_within_root(target: Path, root: Path, error_message: str):
    root_str = _normalized_resolved_path(root)
    target_str = _normalized_resolved_path(target)
    if target_str != root_str and not target_str.startswith(root_str + os.sep):
        raise DatasetPreviewPathError(error_message)


def _normalize_relative_path(path: str) -> str:
    if not path or path in (".", "/", "\\"):
        return ""
    return path.replace("\\", "/").strip("/")


def _user_results_root(user_id: int) -> Path:
    user_dir = (DRIVE_BASE / f"portal_u{user_id}").resolve()
    results_root = (user_dir / RESULTS_ROOT_NAME).resolve()
    try:
        results_root.relative_to(user_dir)
    except ValueError as exc:
        raise DatasetPreviewConfigError("结果目录配置无效") from exc
    return results_root


def _resolve_source_path(user_id: int, relative_path: str) -> tuple[Path, Path]:
    results_root = _user_results_root(user_id)
    normalized_path = _normalize_relative_path(relative_path)
    if not normalized_path:
        raise DatasetPreviewPathError("路径不能为空")

    target = (results_root / normalized_path).resolve()
    try:
        target.relative_to(results_root)
    except ValueError as exc:
        raise DatasetPreviewPathError("非法路径") from exc

    relative_target = target.relative_to(results_root)
    if relative_target.parts and relative_target.parts[0] == PREVIEW_CACHE_DIR_NAME:
        raise DatasetPreviewPathError("非法路径")

    if target.suffix.lower() != ".vtu":
        raise DatasetPreviewPathError("仅支持 VTU 预览转换")

    if not target.exists() or not target.is_file():
        raise DatasetPreviewNotFoundError("文件不存在")

    return results_root, target


def _preview_target(results_root: Path, source: Path) -> tuple[Path, str]:
    relative_source = source.relative_to(results_root)
    relative_preview = Path(PREVIEW_CACHE_DIR_NAME).joinpath(relative_source).with_suffix(".vtp")
    preview_target = (results_root / relative_preview).resolve()
    _ensure_within_root(preview_target, results_root, "非法路径")
    return preview_target, relative_preview.as_posix()


@contextmanager
def _preview_lock(lock_path: Path, timeout_seconds: float = 10.0):
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise DatasetPreviewConversionError("VTU 预览生成超时，请稍后重试")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _convert_vtu_to_vtp(source: Path, target: Path) -> None:
    try:
        from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
        from vtkmodules.vtkIOXML import vtkXMLPolyDataWriter, vtkXMLUnstructuredGridReader
    except Exception as exc:
        raise DatasetPreviewUnavailableError("缺少 VTK 依赖，无法转换 VTU") from exc

    reader = vtkXMLUnstructuredGridReader()
    reader.SetFileName(str(source))
    reader.Update()

    geometry_filter = vtkGeometryFilter()
    geometry_filter.SetInputConnection(reader.GetOutputPort())
    geometry_filter.Update()

    writer = vtkXMLPolyDataWriter()
    writer.SetFileName(str(target))
    writer.SetInputConnection(geometry_filter.GetOutputPort())
    writer.SetDataModeToBinary()
    if writer.Write() != 1:
        raise DatasetPreviewConversionError(f"转换失败: {source.name}")


def ensure_preview_path(user_id: int, relative_path: str) -> str:
    """
    生成或复用 VTU 预览缓存，返回可被 /api/datasets/file 读取的相对路径。
    """
    results_root, source = _resolve_source_path(user_id, relative_path)
    preview_target, preview_relative_path = _preview_target(results_root, source)

    def _needs_rebuild() -> bool:
        if not preview_target.exists() or not preview_target.is_file():
            return True
        return preview_target.stat().st_mtime < source.stat().st_mtime

    if not _needs_rebuild():
        return preview_relative_path

    preview_target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = preview_target.with_suffix(preview_target.suffix + PREVIEW_LOCK_SUFFIX)

    with _preview_lock(lock_path):
        if not _needs_rebuild():
            return preview_relative_path

        temp_target = preview_target.with_name(
            f"{preview_target.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            _convert_vtu_to_vtp(source, temp_target)
            temp_target.replace(preview_target)
        except DatasetPreviewError:
            if temp_target.exists():
                temp_target.unlink(missing_ok=True)
            raise
        except Exception as exc:
            if temp_target.exists():
                temp_target.unlink(missing_ok=True)
            logger.exception("VTU 预览转换异常: %s", source)
            raise DatasetPreviewConversionError("VTU 预览转换失败") from exc

    return preview_relative_path
