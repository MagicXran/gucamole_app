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
    """Per-user authToken 缓存

    Guacamole 客户端用 localStorage 存 GUAC_AUTH_TOKEN，同源标签共享。
    如果每次 launch 都创建新 token，新标签会覆盖旧标签的 session，
    导致旧标签被踢回登录页。

    解决方案: 同一用户的所有 launch 复用同一个 authToken。
    """

    def __init__(self, ttl_seconds: int = 1500):
        self._lock = threading.Lock()
        self._store: dict[str, dict] = {}
        self._ttl = ttl_seconds

    def get(self, username: str) -> dict | None:
        with self._lock:
            entry = self._store.get(username)
            if entry and (time.time() - entry["created_at"]) < self._ttl:
                return entry
            if entry:
                del self._store[username]
            return None

    def put(self, username: str, auth_token: str, data_source: str):
        with self._lock:
            self._store[username] = {
                "auth_token": auth_token,
                "data_source": data_source,
                "created_at": time.time(),
            }

    def invalidate(self, username: str):
        with self._lock:
            self._store.pop(username, None)


class GuacamoleService:
    """Guacamole 连接启动服务"""

    def __init__(
        self,
        secret_key_hex: str,
        internal_url: str,
        external_url: str,
        expire_minutes: int = 30,
    ):
        self.crypto = GuacamoleCrypto(secret_key_hex)
        self.internal_url = internal_url.rstrip('/')
        self.external_url = external_url.rstrip('/')
        self.expire_minutes = expire_minutes
        self._cache = _SessionCache(ttl_seconds=expire_minutes * 60 - 60)

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
    ) -> str:
        """启动连接: 复用或创建 session → 拼 URL

        核心逻辑:
        - 同一 username 复用已有 authToken（解决 localStorage 多标签冲突）
        - authToken 过期后自动重建
        - connections 必须包含该用户所有可用应用（确保 session 覆盖完整）
        """
        if target_connection_name not in connections:
            raise ValueError(
                f"连接名 '{target_connection_name}' 不在 connections 中: "
                f"{list(connections.keys())}"
            )

        # 尝试复用缓存的 session
        cached = self._cache.get(username)
        if cached:
            auth_token = cached["auth_token"]
            data_source = cached["data_source"]
            logger.debug("复用 session: username=%s", username)
        else:
            auth_token, data_source = await self._create_session(
                username, connections
            )
            self._cache.put(username, auth_token, data_source)

        # 构建连接标识符: base64(name + \0 + c + \0 + dataSource)
        identifier_raw = f"{target_connection_name}\x00c\x00{data_source}"
        identifier = base64.b64encode(
            identifier_raw.encode('utf-8')
        ).decode('ascii')

        redirect_url = (
            f"{self.external_url}/#/client/{identifier}?token={auth_token}"
        )
        return redirect_url
