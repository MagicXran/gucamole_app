"""
Guacamole 服务层

职责: 加密 → POST /api/tokens → 构建重定向 URL
"""

import base64
import logging

import httpx

from backend.guacamole_crypto import GuacamoleCrypto

logger = logging.getLogger(__name__)


class GuacamoleService:
    """Guacamole 连接启动服务"""

    def __init__(
        self,
        secret_key_hex: str,
        internal_url: str,
        external_url: str,
        expire_minutes: int = 5,
    ):
        """
        Args:
            secret_key_hex: 32位hex密钥，与 Guacamole JSON_SECRET_KEY 一致
            internal_url: 服务端访问 Guacamole 的地址 (如 http://localhost:8080/guacamole)
            external_url: 用户浏览器访问 Guacamole 的地址
            expire_minutes: token 过期时间（分钟）
        """
        self.crypto = GuacamoleCrypto(secret_key_hex)
        self.internal_url = internal_url.rstrip('/')
        self.external_url = external_url.rstrip('/')
        self.expire_minutes = expire_minutes

    async def launch_connection(
        self,
        username: str,
        connections: dict,
        target_connection_name: str,
    ) -> str:
        """一站式启动: 加密 → 换 token → 拼 URL

        Args:
            username: 用户标识
            connections: Guacamole 连接定义 (由 GuacamoleCrypto.build_rdp_connection 构建)
            target_connection_name: 目标连接名称 (connections dict 中的某个 key)

        Returns:
            完整的 Guacamole 客户端重定向 URL

        Raises:
            httpx.HTTPStatusError: Guacamole 返回非 200 响应
            ValueError: 连接名在 connections 中不存在
        """
        if target_connection_name not in connections:
            raise ValueError(
                f"连接名 '{target_connection_name}' 不在 connections 中: "
                f"{list(connections.keys())}"
            )

        # 1. 构建 payload 并加密
        payload = self.crypto.build_payload(
            username=username,
            connections=connections,
            expire_minutes=self.expire_minutes,
        )
        encrypted_data = self.crypto.encrypt(payload)

        # 2. POST 到 Guacamole /api/tokens
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
            "获取 authToken 成功, username=%s, dataSource=%s",
            username, data_source,
        )

        # 3. 构建连接标识符: base64(name + \0 + c + \0 + dataSource)
        identifier_raw = f"{target_connection_name}\x00c\x00{data_source}"
        identifier = base64.b64encode(
            identifier_raw.encode('utf-8')
        ).decode('ascii')

        # 4. 拼接最终 URL
        redirect_url = (
            f"{self.external_url}/#/client/{identifier}?token={auth_token}"
        )
        return redirect_url
