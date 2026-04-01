"""
数据库连接管理

复用 my_reservation 的连接模式: 同步 mysql-connector-python
"""

import json
import os
from pathlib import Path

import mysql.connector
from mysql.connector import pooling


def load_config() -> dict:
    """加载配置文件，敏感值支持环境变量覆盖"""
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

    # 环境变量覆盖敏感配置
    config["database"]["password"] = os.environ.get(
        "PORTAL_DB_PASSWORD", config["database"]["password"]
    )
    config["guacamole"]["json_secret_key"] = os.environ.get(
        "GUACAMOLE_JSON_SECRET_KEY", config["guacamole"]["json_secret_key"]
    )
    config["auth"]["jwt_secret"] = os.environ.get(
        "PORTAL_JWT_SECRET", config["auth"]["jwt_secret"]
    )

    # 环境变量覆盖连接地址（Docker 部署时容器名替代 localhost）
    config["database"]["host"] = os.environ.get(
        "PORTAL_DB_HOST", config["database"]["host"]
    )
    config["database"]["port"] = int(os.environ.get(
        "PORTAL_DB_PORT", config["database"]["port"]
    ))
    config["guacamole"]["internal_url"] = os.environ.get(
        "GUACAMOLE_INTERNAL_URL", config["guacamole"]["internal_url"]
    )
    config["guacamole"]["external_url"] = os.environ.get(
        "GUACAMOLE_EXTERNAL_URL", config["guacamole"]["external_url"]
    )
    drive_cfg = config.setdefault("guacamole", {}).setdefault("drive", {})
    drive_cfg["base_path"] = os.environ.get(
        "GUACAMOLE_DRIVE_BASE_PATH", drive_cfg.get("base_path", "/drive")
    )
    drive_cfg["results_root"] = os.environ.get(
        "GUACAMOLE_DRIVE_RESULTS_ROOT", drive_cfg.get("results_root", "Output")
    )
    return config


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

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        """执行查询，返回字典列表或单条字典"""
        conn = self.get_connection()
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
            conn.close()

    def execute_update(self, query: str, params=None) -> int:
        """执行写操作 (INSERT/UPDATE/DELETE)，返回影响行数"""
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or {})
            conn.commit()
            return cursor.rowcount
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()


db = Database()
