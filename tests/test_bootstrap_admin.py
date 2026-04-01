import bcrypt
import pytest

from backend.bootstrap_admin import ensure_bootstrap_admin


class FakeDB:
    def __init__(self, existing=None, first_admin=None):
        self.existing = existing
        self.first_admin = first_admin
        self.insert_params = None
        self.update_params = None

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "SELECT id, username FROM portal_user WHERE is_admin = 1" in query:
            return self.first_admin
        if "SELECT id, is_admin, is_active FROM portal_user" in query:
            return self.existing
        if "SELECT id FROM portal_user" in query and self.insert_params:
            return {"id": 99}
        return None if fetch_one else []

    def execute_update(self, query: str, params=None) -> int:
        if "UPDATE portal_user" in query:
            self.update_params = dict(params or {})
        else:
            self.insert_params = dict(params or {})
        return 1


def test_bootstrap_admin_is_disabled_without_required_env_when_admin_exists():
    result = ensure_bootstrap_admin(
        FakeDB(first_admin={"id": 1, "username": "portaladmin"}),
        env={},
    )

    assert result == {"created": False, "reason": "disabled"}


def test_bootstrap_admin_requires_credentials_when_no_admin_exists():
    with pytest.raises(RuntimeError, match="未检测到管理员账号"):
        ensure_bootstrap_admin(FakeDB(), env={})


def test_bootstrap_admin_creates_admin_when_missing():
    db = FakeDB()

    result = ensure_bootstrap_admin(
        db,
        env={
            "PORTAL_BOOTSTRAP_ADMIN_USERNAME": "portaladmin",
            "PORTAL_BOOTSTRAP_ADMIN_PASSWORD": "ChangeMe123!",
            "PORTAL_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Portal 管理员",
        },
    )

    assert result == {
        "created": True,
        "reason": "created",
        "user_id": 99,
        "username": "portaladmin",
    }
    assert db.insert_params["username"] == "portaladmin"
    assert db.insert_params["display_name"] == "Portal 管理员"
    assert bcrypt.checkpw(
        b"ChangeMe123!",
        db.insert_params["password_hash"].encode("utf-8"),
    )


def test_bootstrap_admin_noops_when_admin_exists():
    db = FakeDB(existing={"id": 5, "is_admin": 1, "is_active": 1})

    result = ensure_bootstrap_admin(
        db,
        env={
            "PORTAL_BOOTSTRAP_ADMIN_USERNAME": "portaladmin",
            "PORTAL_BOOTSTRAP_ADMIN_PASSWORD": "ChangeMe123!",
        },
    )

    assert result == {
        "created": False,
        "reason": "exists",
        "user_id": 5,
        "username": "portaladmin",
    }
    assert db.insert_params is None
    assert db.update_params is None


def test_bootstrap_admin_rejects_conflicting_non_admin_user():
    db = FakeDB(existing={"id": 7, "is_admin": 0, "is_active": 1})

    with pytest.raises(RuntimeError, match="非管理员用户冲突"):
        ensure_bootstrap_admin(
            db,
            env={
                "PORTAL_BOOTSTRAP_ADMIN_USERNAME": "portaladmin",
                "PORTAL_BOOTSTRAP_ADMIN_PASSWORD": "ChangeMe123!",
            },
        )


def test_bootstrap_admin_reactivates_disabled_admin():
    db = FakeDB(existing={"id": 8, "is_admin": 1, "is_active": 0})

    result = ensure_bootstrap_admin(
        db,
        env={
            "PORTAL_BOOTSTRAP_ADMIN_USERNAME": "portaladmin",
            "PORTAL_BOOTSTRAP_ADMIN_PASSWORD": "ChangeMe123!",
            "PORTAL_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Portal 管理员",
        },
    )

    assert result == {
        "created": True,
        "reason": "reactivated",
        "user_id": 8,
        "username": "portaladmin",
    }
    assert db.insert_params is None
    assert db.update_params["id"] == 8
    assert db.update_params["display_name"] == "Portal 管理员"
    assert bcrypt.checkpw(
        b"ChangeMe123!",
        db.update_params["password_hash"].encode("utf-8"),
    )
