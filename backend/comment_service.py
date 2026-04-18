from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.models import UserInfo


class CommentServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class CommentService:
    db: Any

    @staticmethod
    def _normalize_target_type(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"app", "case"}:
            raise CommentServiceError(400, "invalid_comment_target", "target_type 只允许 app 或 case")
        return normalized

    @staticmethod
    def _normalize_content(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise CommentServiceError(400, "empty_comment_content", "content 不能为空")
        return normalized

    def _ensure_target_exists(self, *, target_type: str, target_id: int, user_id: int | None = None):
        if target_type == "app":
            row = self.db.execute_query(
                """
                SELECT 1 AS ok
                FROM remote_app
                JOIN remote_app_acl ON remote_app_acl.app_id = remote_app.id
                WHERE remote_app.id = %(target_id)s
                  AND remote_app.is_active = 1
                  AND remote_app_acl.user_id = %(user_id)s
                LIMIT 1
                """,
                {"target_id": target_id, "user_id": user_id},
                fetch_one=True,
            )
            if row:
                return
            raise CommentServiceError(404, "comment_target_not_found", "应用不存在或当前用户无权访问")

        row = self.db.execute_query(
            """
            SELECT 1 AS ok
            FROM simulation_case
            WHERE id = %(target_id)s
              AND visibility = 'public'
              AND status = 'published'
            LIMIT 1
            """,
            {"target_id": target_id},
            fetch_one=True,
        )
        if row:
            return
        raise CommentServiceError(404, "comment_target_not_found", "案例不存在或未发布")

    @staticmethod
    def _to_comment_payload(row: dict[str, Any]) -> dict[str, Any]:
        author_name = str(row.get("author_name") or row.get("display_name") or row.get("username") or "")
        return {
            "id": int(row["id"]),
            "target_type": str(row["target_type"]),
            "target_id": int(row["target_id"]),
            "user_id": int(row["user_id"]),
            "author_name": author_name,
            "content": str(row["content"]),
            "created_at": row.get("created_at"),
        }

    def list_comments(self, *, target_type: str, target_id: int, user: UserInfo) -> list[dict[str, Any]]:
        normalized_target_type = self._normalize_target_type(target_type)
        self._ensure_target_exists(
            target_type=normalized_target_type,
            target_id=target_id,
            user_id=user.user_id,
        )
        rows = self.db.execute_query(
            """
            SELECT c.id, c.target_type, c.target_id, c.user_id, c.content, c.created_at,
                   COALESCE(NULLIF(u.display_name, ''), u.username) AS author_name
            FROM portal_comment c
            JOIN portal_user u ON u.id = c.user_id
            WHERE c.target_type = %(target_type)s
              AND c.target_id = %(target_id)s
            ORDER BY c.created_at ASC, c.id ASC
            """,
            {"target_type": normalized_target_type, "target_id": target_id},
        )
        return [self._to_comment_payload(row) for row in rows]

    def create_comment(self, *, target_type: str, target_id: int, content: str, user: UserInfo) -> dict[str, Any]:
        normalized_target_type = self._normalize_target_type(target_type)
        normalized_content = self._normalize_content(content)
        self._ensure_target_exists(
            target_type=normalized_target_type,
            target_id=target_id,
            user_id=user.user_id,
        )
        with self.db.transaction() as conn:
            self.db.execute_update(
                """
                INSERT INTO portal_comment (target_type, target_id, user_id, content)
                VALUES (%(target_type)s, %(target_id)s, %(user_id)s, %(content)s)
                """,
                {
                    "target_type": normalized_target_type,
                    "target_id": target_id,
                    "user_id": user.user_id,
                    "content": normalized_content,
                },
                conn=conn,
            )
            inserted = self.db.execute_query("SELECT LAST_INSERT_ID() AS id", fetch_one=True, conn=conn) or {}
            inserted_id = int(inserted.get("id") or 0)
            if inserted_id:
                row = self.db.execute_query(
                    """
                    SELECT c.id, c.target_type, c.target_id, c.user_id, c.content, c.created_at,
                           COALESCE(NULLIF(u.display_name, ''), u.username) AS author_name
                    FROM portal_comment c
                    JOIN portal_user u ON u.id = c.user_id
                    WHERE c.id = %(comment_id)s
                    LIMIT 1
                    """,
                    {"comment_id": inserted_id},
                    fetch_one=True,
                    conn=conn,
                )
                if row:
                    return self._to_comment_payload(row)

        return {
            "id": inserted_id,
            "target_type": normalized_target_type,
            "target_id": target_id,
            "user_id": user.user_id,
            "author_name": user.display_name or user.username,
            "content": normalized_content,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
