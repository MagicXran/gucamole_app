from __future__ import annotations

from contextlib import nullcontext
from typing import Any
from urllib.parse import urlsplit


class AppAttachmentService:
    def __init__(self, db):
        self._db = db

    @staticmethod
    def _empty_payload(pool_id: int) -> dict[str, Any]:
        return {
            "pool_id": pool_id,
            "tutorial_docs": [],
            "video_resources": [],
            "plugin_downloads": [],
        }

    @staticmethod
    def _normalize_safe_link_url(value: Any) -> str | None:
        normalized = str(value or "").strip()
        if not normalized:
            return None
        parsed = urlsplit(normalized)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        return normalized

    @classmethod
    def _build_attachment_item(cls, row: dict[str, Any]) -> dict[str, Any] | None:
        safe_link_url = cls._normalize_safe_link_url(row.get("url"))
        if not safe_link_url:
            return None
        return {
            "id": int(row["id"]),
            "title": str(row["title"]),
            "summary": str(row.get("summary") or ""),
            "link_url": safe_link_url,
            "sort_order": int(row.get("sort_order") or 0),
        }

    def _fetch_pool_attachment_rows(self, pool_id: int) -> list[dict[str, Any]]:
        return self._db.execute_query(
            """
            SELECT id, pool_id, attachment_kind, title, summary, url, sort_order
            FROM app_attachment
            WHERE pool_id = %(pool_id)s
              AND is_active = 1
            ORDER BY attachment_kind ASC, sort_order ASC, id ASC
            """,
            {"pool_id": pool_id},
        )

    def _group_attachment_rows(self, pool_id: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
        payload = self._empty_payload(pool_id)
        kind_map = {
            "tutorial_doc": "tutorial_docs",
            "video_resource": "video_resources",
            "plugin_download": "plugin_downloads",
        }
        for row in rows:
            key = kind_map.get(str(row.get("attachment_kind") or ""))
            if not key:
                continue
            item = self._build_attachment_item(row)
            if item:
                payload[key].append(item)
        return payload

    def list_pool_attachments(self, pool_id: int, user_id: int) -> dict[str, Any]:
        accessible = self._db.execute_query(
            """
            SELECT 1 AS ok FROM remote_app a
            JOIN remote_app_acl acl ON acl.app_id = a.id
            JOIN resource_pool p ON p.id = a.pool_id
            WHERE a.pool_id = %(pool_id)s
              AND acl.user_id = %(user_id)s
              AND a.is_active = 1
              AND p.is_active = 1
            LIMIT 1
            """,
            {"pool_id": pool_id, "user_id": user_id},
            fetch_one=True,
        )
        if not accessible:
            return self._empty_payload(pool_id)

        return self.list_pool_attachments_for_admin(pool_id)

    def list_pool_attachments_for_admin(self, pool_id: int) -> dict[str, Any]:
        rows = self._fetch_pool_attachment_rows(pool_id)
        return self._group_attachment_rows(pool_id, rows)

    def replace_pool_attachments(self, *, pool_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        kind_map = {
            "tutorial_docs": "tutorial_doc",
            "video_resources": "video_resource",
            "plugin_downloads": "plugin_download",
        }
        transaction = self._db.transaction() if hasattr(self._db, "transaction") else nullcontext(None)
        with transaction as conn:
            self._db.execute_update(
                """
                UPDATE app_attachment
                SET is_active = 0
                WHERE pool_id = %(pool_id)s
                """,
                {"pool_id": pool_id},
                conn=conn,
            )
            for group_key, attachment_kind in kind_map.items():
                for index, item in enumerate(payload.get(group_key) or []):
                    self._db.execute_update(
                        """
                        INSERT INTO app_attachment (
                            pool_id, attachment_kind, title, summary, url, sort_order, is_active
                        )
                        VALUES (
                            %(pool_id)s, %(attachment_kind)s, %(title)s, %(summary)s, %(url)s, %(sort_order)s, 1
                        )
                        """,
                        {
                            "pool_id": pool_id,
                            "attachment_kind": attachment_kind,
                            "title": item["title"],
                            "summary": str(item.get("summary") or ""),
                            "url": item["link_url"],
                            "sort_order": int(item.get("sort_order", index)),
                        },
                        conn=conn,
                    )
        return {
            "pool_id": pool_id,
            "tutorial_docs": [
                {
                    "id": 0,
                    "title": item["title"],
                    "summary": str(item.get("summary") or ""),
                    "link_url": item["link_url"],
                    "sort_order": int(item.get("sort_order", index)),
                }
                for index, item in enumerate(payload.get("tutorial_docs") or [])
            ],
            "video_resources": [
                {
                    "id": 0,
                    "title": item["title"],
                    "summary": str(item.get("summary") or ""),
                    "link_url": item["link_url"],
                    "sort_order": int(item.get("sort_order", index)),
                }
                for index, item in enumerate(payload.get("video_resources") or [])
            ],
            "plugin_downloads": [
                {
                    "id": 0,
                    "title": item["title"],
                    "summary": str(item.get("summary") or ""),
                    "link_url": item["link_url"],
                    "sort_order": int(item.get("sort_order", index)),
                }
                for index, item in enumerate(payload.get("plugin_downloads") or [])
            ],
        }
