from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CASE_EVENT_ACTIONS = ("view_case_detail", "download_case", "transfer_case")


def _normalize_department(value: Any) -> str:
    normalized = str(value or "").strip()
    return normalized or "未设置"


@dataclass
class AdminAnalyticsService:
    db: Any

    def _fetch_overview_totals(self) -> dict[str, int]:
        row = self.db.execute_query(
            """
            /* analytics:overview_totals */
            SELECT
                COALESCE(SUM(CASE WHEN a.action = 'launch_app' THEN 1 ELSE 0 END), 0) AS software_launches,
                COALESCE(SUM(CASE WHEN a.action IN ('view_case_detail', 'download_case', 'transfer_case') THEN 1 ELSE 0 END), 0) AS case_events,
                COUNT(DISTINCT a.user_id) AS active_users,
                COUNT(
                    DISTINCT COALESCE(NULLIF(TRIM(u.department), ''), '未设置')
                ) AS department_count
            FROM audit_log a
            LEFT JOIN portal_user u ON u.id = a.user_id
            WHERE a.action = 'launch_app'
               OR a.action IN ('view_case_detail', 'download_case', 'transfer_case')
            """,
            fetch_one=True,
        ) or {}
        return {
            "software_launches": int(row.get("software_launches") or 0),
            "case_events": int(row.get("case_events") or 0),
            "active_users": int(row.get("active_users") or 0),
            "department_count": int(row.get("department_count") or 0),
        }

    def _fetch_software_ranking(self) -> list[dict[str, Any]]:
        rows = self.db.execute_query(
            """
            /* analytics:software_ranking */
            SELECT
                a.target_id AS app_id,
                COALESCE(MAX(r.name), MAX(a.target_name), CONCAT('App#', a.target_id)) AS app_name,
                COUNT(*) AS launch_count
            FROM audit_log a
            LEFT JOIN remote_app r ON r.id = a.target_id
            WHERE a.action = 'launch_app'
              AND a.target_type = 'app'
              AND a.target_id IS NOT NULL
            GROUP BY a.target_id
            ORDER BY launch_count DESC, app_id ASC
            LIMIT 10
            """
        )
        return [
            {
                "app_id": int(row["app_id"]),
                "app_name": str(row.get("app_name") or f"App#{row['app_id']}"),
                "launch_count": int(row.get("launch_count") or 0),
            }
            for row in rows
        ]

    def _fetch_case_ranking(self) -> list[dict[str, Any]]:
        rows = self.db.execute_query(
            """
            /* analytics:case_ranking */
            SELECT
                a.target_id AS case_id,
                COALESCE(MAX(c.case_uid), CONCAT('case-', a.target_id)) AS case_uid,
                COALESCE(MAX(c.title), MAX(a.target_name), CONCAT('案例#', a.target_id)) AS case_title,
                SUM(CASE WHEN a.action = 'view_case_detail' THEN 1 ELSE 0 END) AS detail_count,
                SUM(CASE WHEN a.action = 'download_case' THEN 1 ELSE 0 END) AS download_count,
                SUM(CASE WHEN a.action = 'transfer_case' THEN 1 ELSE 0 END) AS transfer_count,
                COUNT(*) AS event_count
            FROM audit_log a
            LEFT JOIN simulation_case c ON c.id = a.target_id
            WHERE a.action IN ('view_case_detail', 'download_case', 'transfer_case')
              AND a.target_type = 'case'
              AND a.target_id IS NOT NULL
            GROUP BY a.target_id
            ORDER BY event_count DESC, case_id ASC
            LIMIT 10
            """
        )
        return [
            {
                "case_id": int(row["case_id"]),
                "case_uid": str(row.get("case_uid") or f"case-{row['case_id']}"),
                "case_title": str(row.get("case_title") or f"案例#{row['case_id']}"),
                "detail_count": int(row.get("detail_count") or 0),
                "download_count": int(row.get("download_count") or 0),
                "transfer_count": int(row.get("transfer_count") or 0),
                "event_count": int(row.get("event_count") or 0),
            }
            for row in rows
        ]

    def _fetch_user_ranking(self) -> list[dict[str, Any]]:
        rows = self.db.execute_query(
            """
            /* analytics:user_ranking */
            SELECT
                a.user_id,
                COALESCE(NULLIF(MAX(u.username), ''), MAX(a.username), CONCAT('user-', a.user_id)) AS username,
                COALESCE(NULLIF(MAX(u.display_name), ''), COALESCE(NULLIF(MAX(u.username), ''), MAX(a.username), CONCAT('user-', a.user_id))) AS display_name,
                COALESCE(NULLIF(MAX(TRIM(u.department)), ''), '未设置') AS department,
                SUM(CASE WHEN a.action = 'launch_app' THEN 1 ELSE 0 END) AS software_launch_count,
                SUM(CASE WHEN a.action IN ('view_case_detail', 'download_case', 'transfer_case') THEN 1 ELSE 0 END) AS case_event_count,
                COUNT(*) AS event_count
            FROM audit_log a
            LEFT JOIN portal_user u ON u.id = a.user_id
            WHERE a.action = 'launch_app'
               OR a.action IN ('view_case_detail', 'download_case', 'transfer_case')
            GROUP BY a.user_id
            ORDER BY event_count DESC, a.user_id ASC
            LIMIT 10
            """
        )
        return [
            {
                "user_id": int(row["user_id"]),
                "username": str(row.get("username") or f"user-{row['user_id']}"),
                "display_name": str(row.get("display_name") or row.get("username") or f"user-{row['user_id']}"),
                "department": _normalize_department(row.get("department")),
                "software_launch_count": int(row.get("software_launch_count") or 0),
                "case_event_count": int(row.get("case_event_count") or 0),
                "event_count": int(row.get("event_count") or 0),
            }
            for row in rows
        ]

    def _fetch_department_ranking(self) -> list[dict[str, Any]]:
        rows = self.db.execute_query(
            """
            /* analytics:department_ranking */
            SELECT
                COALESCE(NULLIF(TRIM(u.department), ''), '未设置') AS department,
                COUNT(DISTINCT a.user_id) AS user_count,
                COUNT(*) AS event_count
            FROM audit_log a
            LEFT JOIN portal_user u ON u.id = a.user_id
            WHERE a.action = 'launch_app'
               OR a.action IN ('view_case_detail', 'download_case', 'transfer_case')
            GROUP BY COALESCE(NULLIF(TRIM(u.department), ''), '未设置')
            ORDER BY event_count DESC, department ASC
            LIMIT 10
            """
        )
        return [
            {
                "department": _normalize_department(row.get("department")),
                "user_count": int(row.get("user_count") or 0),
                "event_count": int(row.get("event_count") or 0),
            }
            for row in rows
        ]

    def get_overview(self) -> dict[str, Any]:
        overview = self._fetch_overview_totals()
        software_ranking = self._fetch_software_ranking()
        case_ranking = self._fetch_case_ranking()
        user_ranking = self._fetch_user_ranking()
        department_ranking = self._fetch_department_ranking()

        return {
            "overview": overview,
            "software_ranking": software_ranking,
            "case_ranking": case_ranking,
            "user_ranking": user_ranking,
            "department_ranking": department_ranking,
        }
