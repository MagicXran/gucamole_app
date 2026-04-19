import importlib
import sys

import mysql.connector.pooling
import pytest

import backend.config_loader as config_loader


def _fake_config():
    return {
        "database": {
            "host": "127.0.0.1",
            "port": 3306,
            "database": "portal",
            "user": "portal",
            "password": "portal",
        }
    }


def _import_database_module(monkeypatch, pool_cls):
    monkeypatch.setattr(config_loader, "_config_cache", config_loader._CONFIG_UNSET, raising=False)
    monkeypatch.setattr(config_loader, "load_config", _fake_config)
    monkeypatch.setattr(mysql.connector.pooling, "MySQLConnectionPool", pool_cls)
    sys.modules.pop("backend.database", None)
    return importlib.import_module("backend.database")


def test_import_backend_database_does_not_initialize_pool(monkeypatch):
    pool_init_calls = 0

    class FakePool:
        def __init__(self, **kwargs):
            nonlocal pool_init_calls
            pool_init_calls += 1

        def get_connection(self):
            return object()

    _import_database_module(monkeypatch, FakePool)

    assert pool_init_calls == 0


def test_database_pool_initializes_on_first_use(monkeypatch):
    pool_init_calls = 0
    sentinel_connection = object()

    class FakePool:
        def __init__(self, **kwargs):
            nonlocal pool_init_calls
            pool_init_calls += 1

        def get_connection(self):
            return sentinel_connection

    database_module = _import_database_module(monkeypatch, FakePool)

    assert pool_init_calls == 0
    assert database_module.db.get_connection() is sentinel_connection
    assert pool_init_calls == 1
    assert database_module.db.get_connection() is sentinel_connection
    assert pool_init_calls == 1


def test_database_pool_retry_after_lazy_init_failure(monkeypatch):
    init_attempts = 0
    sentinel_connection = object()

    class FlakyPool:
        def __init__(self, **kwargs):
            nonlocal init_attempts
            init_attempts += 1
            if init_attempts == 1:
                raise RuntimeError("pool init failed")

        def get_connection(self):
            return sentinel_connection

    database_module = _import_database_module(monkeypatch, FlakyPool)

    assert init_attempts == 0
    with pytest.raises(RuntimeError, match="pool init failed"):
        database_module.db.get_connection()
    assert init_attempts == 1

    assert database_module.db.get_connection() is sentinel_connection
    assert init_attempts == 2


def test_get_db_returns_module_singleton(monkeypatch):
    class FakePool:
        def __init__(self, **kwargs):
            pass

        def get_connection(self):
            return object()

    database_module = _import_database_module(monkeypatch, FakePool)

    assert database_module.get_db() is database_module.db
