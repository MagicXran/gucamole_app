import json
import importlib
import os
import sys
from types import ModuleType, SimpleNamespace


SAMPLE_CONFIG = {
    "database": {
        "host": "127.0.0.1",
        "port": 33060,
        "database": "guacamole_portal_db",
        "user": "root",
        "password": "change-me-db-password",
    },
    "guacamole": {
        "json_secret_key": "00112233445566778899aabbccddeeff",
        "internal_url": "http://localhost:8080",
        "external_url": "http://localhost:8080",
        "drive": {
            "base_path": "/drive",
            "results_root": "Output",
        },
    },
    "auth": {
        "jwt_secret": "change-me-portal-jwt-secret",
    },
}


class FakePool:
    created_kwargs = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakePool.created_kwargs.append(kwargs)

    def get_connection(self):
        return SimpleNamespace(
            ping=lambda **kwargs: None,
            close=lambda: None,
        )


def _load_database_module(monkeypatch):
    FakePool.created_kwargs = []
    fake_pooling = SimpleNamespace(MySQLConnectionPool=FakePool)
    fake_connector = ModuleType("mysql.connector")
    fake_connector.pooling = fake_pooling
    fake_mysql = ModuleType("mysql")
    fake_mysql.connector = fake_connector

    monkeypatch.setitem(sys.modules, "mysql", fake_mysql)
    monkeypatch.setitem(sys.modules, "mysql.connector", fake_connector)
    monkeypatch.delitem(sys.modules, "backend.database", raising=False)

    return importlib.import_module("backend.database")


def test_load_config_prefers_portal_specific_env_overrides(monkeypatch):
    monkeypatch.setenv("PORTAL_DB_PASSWORD", "portal-pass")
    monkeypatch.setenv("PORTAL_DB_USER", "portal-user")
    monkeypatch.setenv("PORTAL_DB_NAME", "portal-db")
    monkeypatch.setenv("PORTAL_DB_HOST", "portal-host")
    monkeypatch.setenv("PORTAL_DB_PORT", "4306")
    monkeypatch.setenv("GUACAMOLE_JSON_SECRET_KEY", "fedcba9876543210fedcba9876543210")
    monkeypatch.setenv("PORTAL_JWT_SECRET", "portal-jwt-secret")

    module = _load_database_module(monkeypatch)

    assert module.CONFIG["database"]["password"] == "portal-pass"
    assert module.CONFIG["database"]["user"] == "portal-user"
    assert module.CONFIG["database"]["database"] == "portal-db"
    assert module.CONFIG["database"]["host"] == "portal-host"
    assert module.CONFIG["database"]["port"] == 4306
    assert module.CONFIG["guacamole"]["json_secret_key"] == "fedcba9876543210fedcba9876543210"
    assert module.CONFIG["auth"]["jwt_secret"] == "portal-jwt-secret"
    assert module.db._pool is None
    module.db.get_connection()
    assert module.db._pool.kwargs["user"] == "portal-user"
    assert module.db._pool.kwargs["database"] == "portal-db"


def test_load_config_accepts_legacy_secret_aliases(monkeypatch):
    monkeypatch.delenv("PORTAL_DB_PASSWORD", raising=False)
    monkeypatch.delenv("GUACAMOLE_JSON_SECRET_KEY", raising=False)
    monkeypatch.setenv("MYSQL_ROOT_PASSWORD", "root-pass")
    monkeypatch.setenv("JSON_SECRET_KEY", "abcdef0123456789abcdef0123456789")

    module = _load_database_module(monkeypatch)

    assert module.CONFIG["database"]["password"] == "root-pass"
    assert module.CONFIG["guacamole"]["json_secret_key"] == "abcdef0123456789abcdef0123456789"
    assert module.CONFIG["auth"]["jwt_secret"] == "abcdef0123456789abcdef0123456789"

def test_load_config_reads_local_deploy_env_file_without_polluting_env(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    config_dir = project_root / "config"
    deploy_dir = project_root / "deploy"
    config_dir.mkdir(parents=True)
    deploy_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps(SAMPLE_CONFIG),
        encoding="utf-8",
    )
    (deploy_dir / ".env").write_text(
        "\n".join(
            [
                "MYSQL_ROOT_PASSWORD=file-root-pass",
                "JSON_SECRET_KEY=1234567890abcdef1234567890abcdef",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("PORTAL_DB_PASSWORD", raising=False)
    monkeypatch.delenv("MYSQL_ROOT_PASSWORD", raising=False)
    monkeypatch.delenv("GUACAMOLE_JSON_SECRET_KEY", raising=False)
    monkeypatch.delenv("JSON_SECRET_KEY", raising=False)

    module = _load_database_module(monkeypatch)
    monkeypatch.delenv("MYSQL_ROOT_PASSWORD", raising=False)
    monkeypatch.delenv("JSON_SECRET_KEY", raising=False)
    config = module.load_config(project_root=project_root)

    assert config["database"]["password"] == "file-root-pass"
    assert config["guacamole"]["json_secret_key"] == "1234567890abcdef1234567890abcdef"
    assert config["auth"]["jwt_secret"] == "1234567890abcdef1234567890abcdef"
    assert "MYSQL_ROOT_PASSWORD" not in os.environ
    assert "JSON_SECRET_KEY" not in os.environ


def test_load_config_prefers_deploy_env_over_root_env(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    config_dir = project_root / "config"
    deploy_dir = project_root / "deploy"
    config_dir.mkdir(parents=True)
    deploy_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps(SAMPLE_CONFIG),
        encoding="utf-8",
    )
    (project_root / ".env").write_text(
        "MYSQL_ROOT_PASSWORD=root-env-pass\n",
        encoding="utf-8",
    )
    (deploy_dir / ".env").write_text(
        "MYSQL_ROOT_PASSWORD=deploy-env-pass\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PORTAL_DB_PASSWORD", raising=False)
    monkeypatch.delenv("MYSQL_ROOT_PASSWORD", raising=False)

    module = _load_database_module(monkeypatch)
    monkeypatch.delenv("MYSQL_ROOT_PASSWORD", raising=False)
    config = module.load_config(project_root=project_root)

    assert config["database"]["password"] == "deploy-env-pass"
    assert "MYSQL_ROOT_PASSWORD" not in os.environ


def test_load_config_strips_wrapping_quotes_from_local_env(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    config_dir = project_root / "config"
    deploy_dir = project_root / "deploy"
    config_dir.mkdir(parents=True)
    deploy_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps(SAMPLE_CONFIG),
        encoding="utf-8",
    )
    (deploy_dir / ".env").write_text(
        '\n'.join(
            [
                'MYSQL_ROOT_PASSWORD="quoted-pass"',
                "JSON_SECRET_KEY='abcdef0123456789abcdef0123456789'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("PORTAL_DB_PASSWORD", raising=False)
    monkeypatch.delenv("MYSQL_ROOT_PASSWORD", raising=False)
    monkeypatch.delenv("JSON_SECRET_KEY", raising=False)

    module = _load_database_module(monkeypatch)
    monkeypatch.delenv("MYSQL_ROOT_PASSWORD", raising=False)
    monkeypatch.delenv("JSON_SECRET_KEY", raising=False)
    config = module.load_config(project_root=project_root)

    assert config["database"]["password"] == "quoted-pass"
    assert config["guacamole"]["json_secret_key"] == "abcdef0123456789abcdef0123456789"
    assert config["auth"]["jwt_secret"] == "abcdef0123456789abcdef0123456789"


def test_database_pool_is_lazy_on_import(monkeypatch):
    module = _load_database_module(monkeypatch)

    assert module.db._pool is None
    assert FakePool.created_kwargs == []

    module.db.get_connection()

    assert len(FakePool.created_kwargs) == 1
