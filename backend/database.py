"""
数据库连接管理

复用 my_reservation 的连接模式: 同步 mysql-connector-python
"""

from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling
from backend.config_loader import load_config


CONFIG = load_config()


class Database:
    """数据库连接管理 (带连接池，支持并发)"""

    def __init__(self):
        self.config = CONFIG["database"]
        self._pool = pooling.MySQLConnectionPool(
            pool_name="portal_pool",
            pool_size=8,
            pool_reset_session=True,
            host=self.config["host"],
            port=self.config["port"],
            database=self.config["database"],
            user=self.config["user"],
            password=self.config["password"],
            charset='utf8mb4',
            use_unicode=True,
        )

    def get_connection(self):
        return self._pool.get_connection()

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
