"""
案例中心发布服务：把 succeeded 任务的公开结果复制成独立案例包。
"""

from __future__ import annotations

import json
import stat as statmod
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from secrets import token_urlsafe
from typing import Any, Callable

from backend.config_loader import load_config


class CaseCenterServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class _PublishableFile:
    source_artifact_id: int
    display_name: str
    source_relative_path: str
    source_path: Path
    package_relative_path: str
    size_bytes: int


@dataclass
class CaseCenterService:
    db: Any
    drive_root: str | Path
    package_root: str | Path | None = None
    results_root_name: str | None = None
    case_uid_factory: Callable[[], str] | None = None

    def __post_init__(self):
        self.drive_root = Path(self.drive_root)
        config = load_config()
        drive_cfg = config.get("guacamole", {}).get("drive", {})
        self._results_root_name = str(self.results_root_name or drive_cfg.get("results_root", "Output")).strip() or "Output"
        self._package_root = Path(self.package_root or (self.drive_root / "_public_case_packages"))
        self._case_uid_factory = self.case_uid_factory or (lambda: f"case_{token_urlsafe(12)}")

    def _user_root(self, user_id: int) -> Path:
        return (self.drive_root / f"portal_u{user_id}").resolve()

    @staticmethod
    def _is_symlink_or_reparse(path: Path) -> bool:
        try:
            if path.is_symlink():
                return True
            stat_result = path.lstat()
        except OSError:
            return False
        reparse_flag = getattr(statmod, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        file_attributes = getattr(stat_result, "st_file_attributes", 0)
        return bool(reparse_flag and file_attributes & reparse_flag)

    @staticmethod
    def _normalize_relative_path(value: str | None) -> str | None:
        if not value:
            return None
        raw = str(value).replace("\\", "/").strip("/")
        if not raw:
            return None
        normalized = PurePosixPath(raw)
        if normalized.is_absolute() or any(part in {"..", ""} for part in normalized.parts):
            return None
        return normalized.as_posix()

    def _resolve_workspace_output(self, *, user_id: int, relative_path: str) -> Path | None:
        normalized = self._normalize_relative_path(relative_path)
        if not normalized:
            return None
        parts = PurePosixPath(normalized).parts
        if not parts or parts[0] != self._results_root_name:
            return None
        user_root = self._user_root(user_id)
        logical_target = user_root / Path(*parts)
        if self._is_symlink_or_reparse(logical_target):
            return None
        target = logical_target.resolve()
        allowed_output_root = (user_root / self._results_root_name).resolve()
        try:
            target.relative_to(allowed_output_root)
        except ValueError:
            return None
        return target

    @staticmethod
    def _is_within_root(candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _ensure_parent_chain_is_directories(*, target_parent: Path, root: Path) -> bool:
        current = target_parent
        while True:
            if current.exists() and not current.is_dir():
                return False
            if current == root:
                return True
            try:
                current.relative_to(root)
            except ValueError:
                return False
            parent = current.parent
            if parent == current:
                return False
            current = parent

    def _collect_safe_directory_files(self, source_path: Path) -> list[Path]:
        source_root = source_path.resolve()
        safe_files: list[Path] = []
        for file_path in sorted(path for path in source_path.rglob("*") if path.is_file()):
            try:
                if file_path.is_symlink():
                    continue
                resolved_file = file_path.resolve()
            except OSError:
                continue
            if not self._is_within_root(resolved_file, source_root):
                continue
            if not resolved_file.is_file():
                continue
            safe_files.append(resolved_file)
        return safe_files

    def _iter_publishable_files(self, *, task: dict, artifacts: list[dict]) -> list[_PublishableFile]:
        publishable: list[_PublishableFile] = []
        seen_package_paths: set[str] = set()
        user_id = int(task["user_id"])
        for artifact in artifacts:
            if artifact.get("artifact_kind") != "workspace_output":
                continue
            normalized_source = self._normalize_relative_path(artifact.get("relative_path"))
            source_path = self._resolve_workspace_output(
                user_id=user_id,
                relative_path=normalized_source,
            )
            if source_path is None or not source_path.exists():
                continue

            output_relative_parts = PurePosixPath(normalized_source).parts[1:] if normalized_source else (source_path.name,)
            if not output_relative_parts:
                output_relative_parts = (source_path.name,)
            display_name = str(artifact.get("display_name") or source_path.name).strip() or source_path.name
            if source_path.is_file():
                package_relative_path = PurePosixPath("assets", *output_relative_parts).as_posix()
                if package_relative_path in seen_package_paths:
                    continue
                seen_package_paths.add(package_relative_path)
                publishable.append(
                    _PublishableFile(
                        source_artifact_id=int(artifact["id"]),
                        display_name=display_name,
                        source_relative_path=normalized_source or source_path.name,
                        source_path=source_path,
                        package_relative_path=package_relative_path,
                        size_bytes=source_path.stat().st_size,
                    )
                )
                continue

            if source_path.is_dir():
                for file_path in self._collect_safe_directory_files(source_path):
                    rel_in_dir = file_path.relative_to(source_path.resolve()).as_posix()
                    package_relative_path = PurePosixPath("assets", *output_relative_parts, rel_in_dir).as_posix()
                    if package_relative_path in seen_package_paths:
                        continue
                    seen_package_paths.add(package_relative_path)
                    publishable.append(
                        _PublishableFile(
                            source_artifact_id=int(artifact["id"]),
                            display_name=file_path.name,
                            source_relative_path=f"{normalized_source}/{rel_in_dir}" if normalized_source else rel_in_dir,
                            source_path=file_path,
                            package_relative_path=package_relative_path,
                            size_bytes=file_path.stat().st_size,
                        )
                    )
        return publishable

    def _fetch_task(self, task_id: str) -> dict | None:
        return self.db.execute_query(
            """
            SELECT id, task_id, user_id, app_id, status, result_summary_json
            FROM platform_task
            WHERE task_id = %(task_id)s
            LIMIT 1
            """,
            {"task_id": task_id},
            fetch_one=True,
        )

    def _fetch_task_artifacts(self, task_db_id: int) -> list[dict]:
        return self.db.execute_query(
            """
            SELECT id, artifact_kind, display_name, relative_path, size_bytes
            FROM platform_task_artifact
            WHERE task_id = %(task_db_id)s
            ORDER BY id ASC
            """,
            {"task_db_id": task_db_id},
        )

    def _fetch_public_case_rows(self) -> list[dict]:
        return self.db.execute_query(
            """
            SELECT c.id, c.case_uid, c.title, c.summary, c.app_id, c.visibility, c.status,
                   c.published_at, p.package_root, p.archive_path, p.archive_size_bytes, p.asset_count
            FROM simulation_case c
            JOIN simulation_case_package p ON p.case_id = c.id
            WHERE c.visibility = 'public' AND c.status = 'published'
            ORDER BY c.published_at DESC, c.id DESC
            """
        )

    def _fetch_public_case_row(self, case_id: int) -> dict | None:
        return self.db.execute_query(
            """
            SELECT c.id, c.case_uid, c.title, c.summary, c.app_id, c.visibility, c.status,
                   c.published_at, p.package_root, p.archive_path, p.archive_size_bytes, p.asset_count
            FROM simulation_case c
            JOIN simulation_case_package p ON p.case_id = c.id
            WHERE c.visibility = 'public' AND c.status = 'published' AND c.id = %(case_id)s
            LIMIT 1
            """,
            {"case_id": case_id},
            fetch_one=True,
        )

    def _fetch_case_assets(self, case_id: int) -> list[dict]:
        return self.db.execute_query(
            """
            SELECT id, case_id, asset_kind, display_name, package_relative_path, size_bytes, sort_order
            FROM simulation_case_asset
            WHERE case_id = %(case_id)s
            ORDER BY sort_order ASC, id ASC
            """,
            {"case_id": case_id},
        )

    def _resolve_public_case_dir(self, case_uid: str) -> Path | None:
        logical_case_root = self._package_root / case_uid
        if self._is_symlink_or_reparse(logical_case_root):
            return None
        resolved_case_root = logical_case_root.resolve()
        if not resolved_case_root.exists() or not resolved_case_root.is_dir():
            return None
        return resolved_case_root

    def _resolve_public_package_dir(self, *, case_uid: str, stored_path: str) -> Path | None:
        case_root = self._resolve_public_case_dir(case_uid)
        if case_root is None:
            return None
        candidate = Path(stored_path)
        if self._is_symlink_or_reparse(candidate):
            return None
        resolved_candidate = candidate.resolve()
        expected_package_dir = (case_root / "package").resolve()
        if resolved_candidate != expected_package_dir or not resolved_candidate.is_dir():
            return None
        return resolved_candidate

    def _resolve_public_archive_path(self, *, case_uid: str, stored_path: str) -> Path | None:
        case_root = self._resolve_public_case_dir(case_uid)
        if case_root is None:
            return None
        candidate = Path(stored_path)
        if self._is_symlink_or_reparse(candidate):
            return None
        resolved_candidate = candidate.resolve()
        expected_archive_path = (case_root / f"{case_uid}.zip").resolve()
        if resolved_candidate != expected_archive_path or not resolved_candidate.is_file():
            return None
        return resolved_candidate

    @staticmethod
    def _serialize_case_row(row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "case_uid": row["case_uid"],
            "title": row["title"],
            "summary": row.get("summary") or "",
            "app_id": row.get("app_id"),
            "published_at": row.get("published_at"),
            "asset_count": int(row.get("asset_count") or 0),
        }

    @staticmethod
    def _serialize_case_asset(row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "asset_kind": row["asset_kind"],
            "display_name": row["display_name"],
            "package_relative_path": row["package_relative_path"],
            "size_bytes": row.get("size_bytes"),
            "sort_order": int(row.get("sort_order") or 0),
        }

    def list_public_cases(self) -> list[dict]:
        rows = self._fetch_public_case_rows()
        return [self._serialize_case_row(row) for row in rows]

    def get_public_case(self, case_id: int) -> dict:
        row = self._fetch_public_case_row(case_id)
        if not row:
            raise CaseCenterServiceError(404, "case_not_found", "case does not exist")

        payload = self._serialize_case_row(row)
        payload["assets"] = [
            self._serialize_case_asset(asset_row)
            for asset_row in self._fetch_case_assets(int(row["id"]))
        ]
        return payload

    def get_case_download(self, case_id: int) -> dict:
        row = self._fetch_public_case_row(case_id)
        if not row:
            raise CaseCenterServiceError(404, "case_not_found", "case does not exist")

        archive_path = self._resolve_public_archive_path(
            case_uid=row["case_uid"],
            stored_path=row["archive_path"],
        )
        if archive_path is None:
            raise CaseCenterServiceError(404, "case_archive_missing", "case archive is unavailable")

        return {
            "case_id": int(row["id"]),
            "case_uid": row["case_uid"],
            "archive_path": archive_path,
            "filename": f"{row['case_uid']}.zip",
        }

    def transfer_case_to_workspace(self, *, case_id: int, user_id: int) -> dict:
        row = self._fetch_public_case_row(case_id)
        if not row:
            raise CaseCenterServiceError(404, "case_not_found", "case does not exist")

        package_dir = self._resolve_public_package_dir(
            case_uid=row["case_uid"],
            stored_path=row["package_root"],
        )
        if package_dir is None:
            raise CaseCenterServiceError(404, "case_package_missing", "case package is unavailable")

        user_root = self._user_root(user_id)
        target_root = (user_root / "Cases" / row["case_uid"]).resolve()
        try:
            target_root.relative_to(user_root)
        except ValueError as exc:
            raise CaseCenterServiceError(400, "invalid_transfer_target", "case transfer target is invalid") from exc
        if not self._ensure_parent_chain_is_directories(target_parent=target_root.parent, root=user_root):
            raise CaseCenterServiceError(409, "case_transfer_conflict", "target workspace path conflicts with an existing file")
        if target_root.exists():
            raise CaseCenterServiceError(409, "case_transfer_conflict", "target workspace path already exists")

        safe_files = self._collect_safe_directory_files(package_dir)
        target_root.mkdir(parents=True, exist_ok=False)
        try:
            for file_path in safe_files:
                relative_path = file_path.relative_to(package_dir.resolve())
                target_path = target_root / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, target_path)
        except Exception:
            shutil.rmtree(target_root, ignore_errors=True)
            raise

        return {
            "case_id": int(row["id"]),
            "case_uid": row["case_uid"],
            "target_path": PurePosixPath("Cases", row["case_uid"]).as_posix(),
            "asset_count": int(row.get("asset_count") or len(safe_files)),
        }

    def _insert_case(self, *, conn: Any, payload: dict) -> int:
        self.db.execute_update(
            """
            INSERT INTO simulation_case (
                case_uid, title, summary, app_id, visibility, status,
                published_by_user_id, published_at
            )
            VALUES (
                %(case_uid)s, %(title)s, %(summary)s, %(app_id)s, %(visibility)s, %(status)s,
                %(published_by_user_id)s, NOW()
            )
            """,
            payload,
            conn=conn,
        )
        row = self.db.execute_query("SELECT LAST_INSERT_ID() AS id", fetch_one=True, conn=conn)
        return int(row["id"])

    def _insert_source(self, *, conn: Any, payload: dict):
        self.db.execute_update(
            """
            INSERT INTO simulation_case_source (
                case_id, source_type, source_task_id, source_task_public_id,
                source_user_id, source_status, source_summary_json
            )
            VALUES (
                %(case_id)s, %(source_type)s, %(source_task_id)s, %(source_task_public_id)s,
                %(source_user_id)s, %(source_status)s, %(source_summary_json)s
            )
            """,
            payload,
            conn=conn,
        )

    def _insert_asset(self, *, conn: Any, payload: dict):
        self.db.execute_update(
            """
            INSERT INTO simulation_case_asset (
                case_id, source_artifact_id, asset_kind, display_name,
                package_relative_path, size_bytes, sort_order
            )
            VALUES (
                %(case_id)s, %(source_artifact_id)s, %(asset_kind)s, %(display_name)s,
                %(package_relative_path)s, %(size_bytes)s, %(sort_order)s
            )
            """,
            payload,
            conn=conn,
        )

    def _insert_package(self, *, conn: Any, payload: dict):
        self.db.execute_update(
            """
            INSERT INTO simulation_case_package (
                case_id, package_root, archive_path, archive_size_bytes, asset_count
            )
            VALUES (
                %(case_id)s, %(package_root)s, %(archive_path)s, %(archive_size_bytes)s, %(asset_count)s
            )
            """,
            payload,
            conn=conn,
        )

    def publish_case_from_task(
        self,
        *,
        task_id: str,
        publisher_user_id: int,
        title: str,
        summary: str = "",
    ) -> dict:
        normalized_title = str(title).strip()
        if not normalized_title:
            raise CaseCenterServiceError(400, "invalid_case_title", "case title is required")

        task = self._fetch_task(task_id)
        if not task:
            raise CaseCenterServiceError(404, "task_not_found", "task does not exist")
        if int(task["user_id"]) != int(publisher_user_id):
            raise CaseCenterServiceError(403, "task_publish_forbidden", "only the task owner can publish this case")
        if task.get("status") != "succeeded":
            raise CaseCenterServiceError(409, "task_not_publishable", "only succeeded tasks can be published")

        artifacts = self._fetch_task_artifacts(int(task["id"]))
        publishable_files = self._iter_publishable_files(task=task, artifacts=artifacts)
        if not publishable_files:
            raise CaseCenterServiceError(409, "no_publishable_artifacts", "task has no publishable workspace output")

        case_uid = self._case_uid_factory()
        case_root = (self._package_root / case_uid).resolve()
        package_dir = case_root / "package"
        archive_path = case_root / f"{case_uid}.zip"

        case_root.mkdir(parents=True, exist_ok=False)
        try:
            for item in publishable_files:
                target = package_dir / Path(*PurePosixPath(item.package_relative_path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item.source_path, target)

            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for file_path in sorted(path for path in package_dir.rglob("*") if path.is_file()):
                    archive.write(file_path, arcname=file_path.relative_to(package_dir).as_posix())

            with self.db.transaction() as conn:
                case_id = self._insert_case(
                    conn=conn,
                    payload={
                        "case_uid": case_uid,
                        "title": normalized_title,
                        "summary": str(summary).strip(),
                        "app_id": task.get("app_id"),
                        "visibility": "public",
                        "status": "published",
                        "published_by_user_id": publisher_user_id,
                    },
                )
                self._insert_source(
                    conn=conn,
                    payload={
                        "case_id": case_id,
                        "source_type": "platform_task",
                        "source_task_id": int(task["id"]),
                        "source_task_public_id": task["task_id"],
                        "source_user_id": int(task["user_id"]),
                        "source_status": task.get("status"),
                        "source_summary_json": json.dumps(task.get("result_summary_json"), ensure_ascii=False) if task.get("result_summary_json") is not None else None,
                    },
                )
                for index, item in enumerate(publishable_files):
                    self._insert_asset(
                        conn=conn,
                        payload={
                            "case_id": case_id,
                            "source_artifact_id": item.source_artifact_id,
                            "asset_kind": "workspace_output",
                            "display_name": item.display_name,
                            "package_relative_path": item.package_relative_path,
                            "size_bytes": item.size_bytes,
                            "sort_order": index,
                        },
                    )
                self._insert_package(
                    conn=conn,
                    payload={
                        "case_id": case_id,
                        "package_root": str(package_dir.resolve()),
                        "archive_path": str(archive_path.resolve()),
                        "archive_size_bytes": archive_path.stat().st_size,
                        "asset_count": len(publishable_files),
                    },
                )
        except Exception:
            shutil.rmtree(case_root, ignore_errors=True)
            raise

        return {
            "case_uid": case_uid,
            "case_root": str(case_root.resolve()),
            "archive_path": str(archive_path.resolve()),
            "asset_count": len(publishable_files),
        }
