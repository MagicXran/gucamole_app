"""
Guacamole 服务层

职责: 加密 → POST /api/tokens → 构建重定向 URL
核心设计: per-user session 复用，解决 localStorage 多标签冲突
"""

import base64
import logging
import time
import threading

import httpx

from backend.guacamole_crypto import GuacamoleCrypto

logger = logging.getLogger(__name__)


class _SessionCache:
    """双层 per-user authToken 缓存 (内存 + 数据库)

    Guacamole 客户端用 localStorage 存 GUAC_AUTH_TOKEN，同源标签共享。
    如果每次 launch 都创建新 token，新标签会覆盖旧标签的 session，
    导致旧标签被踢回登录页。

    解决方案: 同一用户的所有 launch 复用同一个 authToken。
    内存缓存提供快速访问，数据库缓存确保后端重启后仍能复用 token。
    """

    def __init__(self, ttl_seconds: int, db):
        self._lock = threading.Lock()
        self._memory: dict[str, dict] = {}
        self._ttl = ttl_seconds
        self._db = db

    def get(self, username: str) -> dict | None:
        """获取缓存的 session（先内存后数据库）

        Returns:
            dict with auth_token, data_source, created_at.
            如果从数据库恢复，额外包含 needs_validation=True。
            None 如果无缓存。
        """
        # 内存快速路径
        with self._lock:
            entry = self._memory.get(username)
            if entry and (time.time() - entry["created_at"]) < self._ttl:
                return entry
            if entry:
                del self._memory[username]

        # 数据库回退（后端重启后）
        try:
            row = self._db.execute_query(
                "SELECT auth_token, data_source, created_at "
                "FROM token_cache WHERE username = %(username)s",
                {"username": username},
                fetch_one=True,
            )
        except Exception:
            logger.warning("token_cache 表读取失败，视为缓存未命中")
            return None

        if not row:
            return None

        if time.time() - row["created_at"] > self._ttl:
            try:
                self._db.execute_update(
                    "DELETE FROM token_cache WHERE username = %(username)s",
                    {"username": username},
                )
            except Exception:
                pass
            return None

        return {
            "auth_token": row["auth_token"],
            "data_source": row["data_source"],
            "created_at": row["created_at"],
            "needs_validation": True,
        }

    def put(self, username: str, auth_token: str, data_source: str):
        """存储到内存和数据库双层缓存"""
        now = time.time()
        entry = {
            "auth_token": auth_token,
            "data_source": data_source,
            "created_at": now,
        }
        with self._lock:
            self._memory[username] = entry
        try:
            self._db.execute_update(
                "REPLACE INTO token_cache "
                "(username, auth_token, data_source, created_at) "
                "VALUES (%(username)s, %(auth_token)s, "
                "%(data_source)s, %(created_at)s)",
                {
                    "username": username,
                    "auth_token": auth_token,
                    "data_source": data_source,
                    "created_at": now,
                },
            )
        except Exception:
            logger.warning("token_cache 表写入失败，仅保留内存缓存")

    def promote(self, username: str, entry: dict):
        """将数据库恢复的条目提升到内存缓存"""
        clean = {k: v for k, v in entry.items() if k != "needs_validation"}
        with self._lock:
            self._memory[username] = clean

    def invalidate(self, username: str):
        """从双层缓存中移除"""
        with self._lock:
            self._memory.pop(username, None)
        try:
            self._db.execute_update(
                "DELETE FROM token_cache WHERE username = %(username)s",
                {"username": username},
            )
        except Exception:
            pass

    def invalidate_all(self):
        """清空全部缓存（admin 修改应用/权限后调用）"""
        with self._lock:
            self._memory.clear()
        try:
            self._db.execute_update("DELETE FROM token_cache")
        except Exception:
            logger.warning("token_cache 全量清除失败")


class GuacamoleService:
    """Guacamole 连接启动服务"""

    def __init__(
        self,
        secret_key_hex: str,
        internal_url: str,
        external_url: str,
        expire_minutes: int,
        db,
    ):
        self.crypto = GuacamoleCrypto(secret_key_hex)
        self.internal_url = internal_url.rstrip('/')
        self.external_url = external_url.rstrip('/')
        self.expire_minutes = expire_minutes
        self._cache = _SessionCache(
            ttl_seconds=expire_minutes * 60 - 60,
            db=db,
        )

    def invalidate_all_sessions(self):
        """清空所有用户的 Guacamole session 缓存"""
        self._cache.invalidate_all()
        logger.info("已清空全部 Guacamole session 缓存")

    async def _validate_token(self, auth_token: str) -> bool:
        """向 Guacamole 验证 authToken 是否仍然有效

        使用 /api/session/data/json/self/permissions 端点，
        因为 JSON auth 数据源的 /api/session/data 会返回 404。
        """
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{self.internal_url}/api/session/data"
                    f"/json/self/permissions",
                    params={"token": auth_token},
                )
                return resp.status_code == 200
        except Exception:
            logger.warning("Guacamole token 验证失败（网络错误）")
            return False

    async def _create_session(
        self,
        username: str,
        connections: dict,
    ) -> tuple[str, str]:
        """创建 Guacamole session，返回 (authToken, dataSource)"""
        payload = self.crypto.build_payload(
            username=username,
            connections=connections,
            expire_minutes=self.expire_minutes,
        )
        encrypted_data = self.crypto.encrypt(payload)

        token_url = f"{self.internal_url}/api/tokens"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                token_url,
                data={"data": encrypted_data},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code != 200:
            logger.error(
                "Guacamole /api/tokens 返回 %d: %s", resp.status_code, resp.text
            )
            resp.raise_for_status()

        try:
            result = resp.json()
        except Exception:
            logger.error("Guacamole 返回非JSON响应: %s", resp.text[:500])
            raise RuntimeError("Guacamole 返回了非预期的响应格式")

        auth_token = result.get("authToken")
        if not auth_token:
            logger.error("Guacamole 响应缺少 authToken: %s", result)
            raise RuntimeError("Guacamole 响应中无 authToken")
        data_source = result.get("dataSource", "json")

        logger.info(
            "创建新 session, username=%s, dataSource=%s", username, data_source,
        )
        return auth_token, data_source

    async def launch_connection(
        self,
        username: str,
        connections: dict,
        target_connection_name: str,
        external_url: str = "",
    ) -> str:
        """启动连接: 复用或创建 session → 拼 URL

        三级回退策略:
        1. 内存缓存命中 → 直接复用 (最快，零额外开销)
        2. 数据库缓存命中 → 验证 Guacamole 有效性 → 恢复到内存
        3. 无缓存 → 创建新 session → 写入双层缓存
        """
        if target_connection_name not in connections:
            raise ValueError(
                f"连接名 '{target_connection_name}' 不在 connections 中: "
                f"{list(connections.keys())}"
            )

        cached = self._cache.get(username)

        if cached:
            if cached.get("needs_validation"):
                if await self._validate_token(cached["auth_token"]):
                    self._cache.promote(username, cached)
                    logger.info("从数据库恢复 session: username=%s", username)
                else:
                    self._cache.invalidate(username)
                    cached = None
                    logger.info(
                        "数据库缓存 token 已失效: username=%s", username
                    )
            else:
                logger.debug("复用内存 session: username=%s", username)

        if not cached:
            auth_token, data_source = await self._create_session(
                username, connections
            )
            self._cache.put(username, auth_token, data_source)
            cached = {"auth_token": auth_token, "data_source": data_source}

        # 构建连接标识符: base64(name + \0 + c + \0 + dataSource)
        identifier_raw = f"{target_connection_name}\x00c\x00{cached['data_source']}"
        identifier = base64.b64encode(
            identifier_raw.encode('utf-8')
        ).decode('ascii')

        base_url = external_url.rstrip('/') if external_url else self.external_url
        redirect_url = (
            f"{base_url}/#/client/{identifier}"
            f"?token={cached['auth_token']}"
        )
        return redirect_url
