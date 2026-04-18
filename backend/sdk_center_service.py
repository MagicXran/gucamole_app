"""
SDK 中心只读服务：包 -> 版本 -> 资产。
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit
from typing import Any, Literal


SdkPackageKind = Literal["cloud_platform", "simulation_app"]


class SdkCenterServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class SdkCenterService:
    db: Any

    @staticmethod
    def _has_safe_download_url(value: str | None) -> bool:
        normalized = str(value or "").strip()
        if not normalized:
            return False
        parsed = urlsplit(normalized)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)

    @classmethod
    def _safe_url_or_empty(cls, value: str | None) -> str:
        normalized = str(value or "").strip()
        return normalized if cls._has_safe_download_url(normalized) else ""

    @classmethod
    def _sanitize_asset(cls, asset: dict) -> dict:
        safe_download_url = cls._safe_url_or_empty(asset.get("download_url"))
        if not safe_download_url:
            return {}
        return {
            **asset,
            "download_url": safe_download_url,
        }

    @classmethod
    def _sanitize_package(cls, package: dict) -> dict:
        return {
            **package,
            "homepage_url": cls._safe_url_or_empty(package.get("homepage_url")),
        }

    def list_packages(self, package_kind: SdkPackageKind) -> list[dict]:
        rows = self.db.execute_query(
            """
            SELECT id, package_kind, name, summary, homepage_url
            FROM sdk_package
            WHERE package_kind = %(package_kind)s AND is_active = 1
            ORDER BY sort_order ASC, id ASC
            """,
            {"package_kind": package_kind},
        )
        return [self._sanitize_package(row) for row in rows]

    def get_package_detail(self, package_id: int) -> dict:
        package = self.db.execute_query(
            """
            SELECT id, package_kind, name, summary, homepage_url
            FROM sdk_package
            WHERE id = %(package_id)s AND is_active = 1
            LIMIT 1
            """,
            {"package_id": package_id},
            fetch_one=True,
        )
        if not package:
            raise SdkCenterServiceError(404, "sdk_package_not_found", "SDK package not found")
        package = self._sanitize_package(package)

        versions = self.db.execute_query(
            """
            SELECT id, package_id, version, release_notes, released_at
            FROM sdk_version
            WHERE package_id = %(package_id)s AND is_active = 1
            ORDER BY sort_order ASC, id ASC
            """,
            {"package_id": package_id},
        )
        detail_versions = []
        for version in versions:
            version_id = int(version["id"])
            assets = self.db.execute_query(
                """
                SELECT id, version_id, asset_kind, display_name, download_url, size_bytes, sort_order
                FROM sdk_asset
                WHERE version_id = %(version_id)s AND is_active = 1
                ORDER BY sort_order ASC, id ASC
                """,
                {"version_id": version_id},
            )
            safe_assets = [safe_asset for asset in assets if (safe_asset := self._sanitize_asset(asset))]
            detail_versions.append({**version, "assets": safe_assets})

        return {**package, "versions": detail_versions}

    def get_download_asset(self, asset_id: int) -> dict:
        asset = self.db.execute_query(
            """
            SELECT a.id, a.version_id, a.asset_kind, a.display_name, a.download_url, a.size_bytes, a.sort_order
            FROM sdk_asset a
            JOIN sdk_version v ON v.id = a.version_id
            JOIN sdk_package p ON p.id = v.package_id
            WHERE a.id = %(asset_id)s
              AND a.is_active = 1
              AND v.is_active = 1
              AND p.is_active = 1
            LIMIT 1
            """,
            {"asset_id": asset_id},
            fetch_one=True,
        )
        if not asset:
            raise SdkCenterServiceError(404, "sdk_asset_not_found", "SDK asset not found")
        safe_asset = self._sanitize_asset(asset)
        if not safe_asset:
            raise SdkCenterServiceError(404, "sdk_asset_not_found", "SDK asset not found")
        return safe_asset
