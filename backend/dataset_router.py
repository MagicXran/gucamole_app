"""
仿真数据集 API - 文件列表与下载

PoC 阶段：扫描 data/samples/ 本地目录
近期规划：共享 guacd_drive volume 扫描 /drive/portal_u{uid}/
远期规划：Windows Agent + MinIO 统一存储
"""

import logging
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.models import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# 数据目录：优先环境变量，否则用项目根下的 data/samples
_DATA_DIR = Path(os.environ.get(
    "DATASET_DIR",
    str(Path(__file__).parent.parent / "data" / "samples"),
))

# 支持的仿真数据文件扩展名
SUPPORTED_EXTENSIONS = {".vtk", ".vtp", ".vtu", ".stl", ".obj", ".gltf", ".glb"}


class DatasetInfo(BaseModel):
    """数据集文件信息"""
    filename: str
    size_bytes: int
    size_human: str
    extension: str
    modified: str


def _human_size(size_bytes: int) -> str:
    """字节数转可读字符串"""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _scan_datasets() -> List[DatasetInfo]:
    """扫描数据目录，返回支持格式的文件列表"""
    if not _DATA_DIR.exists():
        return []

    results = []
    for f in sorted(_DATA_DIR.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        stat = f.stat()
        results.append(DatasetInfo(
            filename=f.name,
            size_bytes=stat.st_size,
            size_human=_human_size(stat.st_size),
            extension=ext,
            modified=str(stat.st_mtime),
        ))
    return results


@router.get("/", response_model=List[DatasetInfo])
def list_datasets(user: UserInfo = Depends(get_current_user)):
    """列出可用的仿真数据集文件"""
    return _scan_datasets()


@router.get("/{filename}")
def download_dataset(
    filename: str,
    user: UserInfo = Depends(get_current_user),
):
    """下载指定的数据集文件（StreamingResponse）"""
    # 安全检查：禁止路径穿越
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="非法文件名",
        )

    filepath = _DATA_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    ext = filepath.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件格式",
        )

    # 根据扩展名设置 MIME type
    mime_map = {
        ".vtk": "application/octet-stream",
        ".vtp": "application/xml",
        ".vtu": "application/xml",
        ".stl": "application/octet-stream",
        ".obj": "text/plain",
        ".gltf": "application/json",
        ".glb": "application/octet-stream",
    }
    media_type = mime_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(filepath),
        media_type=media_type,
        filename=filename,
    )
