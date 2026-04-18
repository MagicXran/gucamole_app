from fastapi import HTTPException, status

from backend.database import db


class BookingService:
    def __init__(self, db=db):
        self.db = db

    def list_bookings(self, *, user_id: int) -> list[dict]:
        return self.db.execute_query(
            """
            SELECT
                id,
                user_id,
                app_name,
                scheduled_for,
                purpose,
                note,
                status,
                created_at,
                cancelled_at
            FROM booking_register
            WHERE user_id = %(user_id)s
            ORDER BY scheduled_for DESC, id DESC
            """,
            {"user_id": user_id},
        )

    def create_booking(self, *, user_id: int, payload: dict) -> dict:
        params = {
            "user_id": user_id,
            "app_name": payload["app_name"].strip(),
            "scheduled_for": payload["scheduled_for"],
            "purpose": payload["purpose"].strip(),
            "note": payload.get("note", "").strip(),
        }

        with self.db.transaction() as conn:
            self.db.execute_update(
                """
                INSERT INTO booking_register
                    (user_id, app_name, scheduled_for, purpose, note, status)
                VALUES
                    (%(user_id)s, %(app_name)s, %(scheduled_for)s, %(purpose)s, %(note)s, 'active')
                """,
                params,
                conn=conn,
            )
            inserted = self.db.execute_query(
                "SELECT LAST_INSERT_ID() AS id",
                fetch_one=True,
                conn=conn,
            )
            return self._get_booking(
                booking_id=int(inserted["id"]),
                user_id=user_id,
                conn=conn,
            )

    def cancel_booking(self, *, booking_id: int, user_id: int) -> dict:
        booking = self._get_booking(booking_id=booking_id, user_id=user_id)
        if booking is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
        if booking["status"] != "active":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="预约已取消")

        updated = self.db.execute_update(
            """
            UPDATE booking_register
            SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
            WHERE id = %(booking_id)s AND user_id = %(user_id)s AND status = 'active'
            """,
            {"booking_id": booking_id, "user_id": user_id},
        )
        if updated == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
        return self._get_booking(booking_id=booking_id, user_id=user_id)

    def _get_booking(self, *, booking_id: int, user_id: int, conn=None) -> dict | None:
        return self.db.execute_query(
            """
            SELECT
                id,
                user_id,
                app_name,
                scheduled_for,
                purpose,
                note,
                status,
                created_at,
                cancelled_at
            FROM booking_register
            WHERE id = %(booking_id)s AND user_id = %(user_id)s
            """,
            {"booking_id": booking_id, "user_id": user_id},
            fetch_one=True,
            conn=conn,
        )
