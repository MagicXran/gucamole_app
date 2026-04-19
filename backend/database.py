"""
数据库连接管理

复用 my_reservation 的连接模式: 同步 mysql-connector-python
"""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

import mysql.connector
from mysql.connector import pooling
from backend.config_loader import get_config


class _LazyConfigProxy:
    def _config(self) -> dict:
        return get_config()

    def __getitem__(self, key):
        return self._config()[key]

    def get(self, key, default=None):
        return self._config().get(key, default)

    def setdefault(self, key, default=None):
        return self._config().setdefault(key, default)

    def copy(self) -> dict:
        return dict(self._config())

    def __contains__(self, key) -> bool:
        return key in self._config()

    def __iter__(self) -> Iterator:
        return iter(self._config())

    def __len__(self) -> int:
        return len(self._config())

    def __repr__(self) -> str:
        return "<LazyConfigProxy>"


CONFIG = _LazyConfigProxy()


class Database:
    """数据库连接管理 (带连接池，支持并发)"""

    def __init__(self):
        self._pool = None
        self._pool_lock = Lock()

    def _create_pool(self):
        db_config = get_config()["database"]
        return pooling.MySQLConnectionPool(
            pool_name="portal_pool",
            pool_size=8,
            pool_reset_session=True,
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
            charset="utf8mb4",
            use_unicode=True,
        )

    def _get_pool(self):
        if self._pool is not None:
            return self._pool
        with self._pool_lock:
            if self._pool is None:
                self._pool = self._create_pool()
            return self._pool

    def get_connection(self):
        return self._get_pool().get_connection()

    @contextmanager
    def transaction(self):
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_query(self, query: str, params=None, fetch_one: bool = False, conn=None):
        """执行查询，返回字典列表或单条字典"""
        own_conn = conn is None
        conn = conn or self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or {})
            if fetch_one:
                return cursor.fetchone()
            return cursor.fetchall()
        finally:
            if cursor is not None:
                cursor.close()
            if own_conn:
                conn.close()

    def execute_update(self, query: str, params=None, conn=None) -> int:
        """执行写操作 (INSERT/UPDATE/DELETE)，返回影响行数"""
        own_conn = conn is None
        conn = conn or self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or {})
            if own_conn:
                conn.commit()
            return cursor.rowcount
        finally:
            if cursor is not None:
                cursor.close()
            if own_conn:
                conn.close()


db = Database()


def get_db() -> Database:
    return db
