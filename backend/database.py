"""
数据库连接管理

复用 my_reservation 的连接模式: 同步 mysql-connector-python
"""

import json
import os
from pathlib import Path

import mysql.connector
from mysql.connector import pooling


def _first_env(local_env: dict[str, str], *names: str, default=None):
    for source in (os.environ, local_env):
        for name in names:
            value = source.get(name)
            if value not in (None, ""):
                return value
    return default


def _load_local_env(project_root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for env_path in (project_root / ".env", project_root / "deploy" / ".env"):
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if key:
                values[key] = value
    return values


def load_config(project_root: Path | None = None) -> dict:
    """加载配置文件，敏感值支持环境变量覆盖"""
    project_root = project_root or Path(__file__).parent.parent
    local_env = _load_local_env(project_root)
    config_path = project_root / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

    db_cfg = config.setdefault("database", {})
    guac_cfg = config.setdefault("guacamole", {})
    auth_cfg = config.setdefault("auth", {})

    # 环境变量覆盖敏感配置
    db_cfg["password"] = _first_env(
        local_env,
        "PORTAL_DB_PASSWORD",
        "MYSQL_ROOT_PASSWORD",
        "GUAC_DB_ROOT_PASSWORD",
        default=db_cfg.get("password"),
    )
    guac_cfg["json_secret_key"] = _first_env(
        local_env,
        "GUACAMOLE_JSON_SECRET_KEY",
        "JSON_SECRET_KEY",
        default=guac_cfg.get("json_secret_key"),
    )
    auth_cfg["jwt_secret"] = _first_env(
        local_env,
        "PORTAL_JWT_SECRET",
        "JSON_SECRET_KEY",
        "GUACAMOLE_JSON_SECRET_KEY",
        default=auth_cfg.get("jwt_secret"),
    )

    # 环境变量覆盖连接地址（Docker 部署时容器名替代 localhost）
    db_cfg["host"] = _first_env(
        local_env,
        "PORTAL_DB_HOST",
        default=db_cfg["host"],
    )
    db_cfg["port"] = int(_first_env(
        local_env,
        "PORTAL_DB_PORT",
        default=db_cfg["port"],
    ))
    db_cfg["user"] = _first_env(
        local_env,
        "PORTAL_DB_USER",
        default=db_cfg["user"],
    )
    db_cfg["database"] = _first_env(
        local_env,
        "PORTAL_DB_NAME",
        default=db_cfg["database"],
    )
    guac_cfg["internal_url"] = _first_env(
        local_env,
        "GUACAMOLE_INTERNAL_URL",
        default=guac_cfg["internal_url"],
    )
    guac_cfg["external_url"] = _first_env(
        local_env,
        "GUACAMOLE_EXTERNAL_URL",
        default=guac_cfg["external_url"],
    )
    drive_cfg = guac_cfg.setdefault("drive", {})
    drive_cfg["base_path"] = _first_env(
        local_env,
        "GUACAMOLE_DRIVE_BASE_PATH",
        default=drive_cfg.get("base_path", "/drive"),
    )
    drive_cfg["results_root"] = _first_env(
        local_env,
        "GUACAMOLE_DRIVE_RESULTS_ROOT",
        default=drive_cfg.get("results_root", "Output"),
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
