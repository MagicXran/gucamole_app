"""
Guacamole Encrypted JSON Auth 加密模块

加密规范 (Apache Guacamole 1.6.0 官方):
  1. JSON → UTF-8 bytes
  2. HMAC-SHA256(key, json_bytes) → 32字节签名
  3. signature + json_bytes → 拼接
  4. PKCS7(128-bit) 填充
  5. AES-128-CBC(key, IV=零向量) 加密
  6. Base64 编码

参考:
  - https://guacamole.apache.org/doc/gug/json-auth.html
  - CryptoService.java (guacamole-auth-json)
  - encrypt-json.sh (官方参考脚本)
"""

import base64
import hashlib
import hmac
import json
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding


class GuacamoleCrypto:
    """Guacamole Encrypted JSON 加密器"""

    AES_BLOCK_BITS = 128
    IV = b'\x00' * 16  # 全零 IV，与 CryptoService.java 一致

    def __init__(self, secret_key_hex: str):
        """
        Args:
            secret_key_hex: 32位十六进制字符串 (128-bit AES 密钥)
        """
        try:
            self._key = bytes.fromhex(secret_key_hex)
        except ValueError:
            raise ValueError("密钥必须是合法的十六进制字符串")
        if len(self._key) != 16:
            raise ValueError(
                f"密钥必须是128-bit (16字节/32位hex)，当前: {len(self._key)} 字节"
            )

    def encrypt(self, payload: dict) -> str:
        """将 dict 加密为 Guacamole 可接受的 base64 字符串

        Args:
            payload: JSON payload (含 username, expires, connections)

        Returns:
            base64 编码的加密数据，可直接作为 /api/tokens 的 data 参数
        """
        # 1. JSON → 紧凑 UTF-8 bytes
        json_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

        # 2. HMAC-SHA256 签名
        signature = hmac.new(self._key, json_bytes, hashlib.sha256).digest()

        # 3. 签名在前 + JSON 在后
        plaintext = signature + json_bytes

        # 4. PKCS7 填充 (等价于 Java 的 PKCS5Padding for AES)
        padder = crypto_padding.PKCS7(self.AES_BLOCK_BITS).padder()
        padded = padder.update(plaintext) + padder.finalize()

        # 5. AES-128-CBC 加密，IV 全零
        encryptor = Cipher(
            algorithms.AES(self._key),
            modes.CBC(self.IV)
        ).encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()

        # 6. Base64 编码
        return base64.b64encode(encrypted).decode('ascii')

    def build_payload(
        self,
        username: str,
        connections: dict,
        expire_minutes: int = 5
    ) -> dict:
        """构建标准 Guacamole JSON Auth payload

        Args:
            username: 用户标识（在 Guacamole 中显示的用户名）
            connections: 连接定义 dict，格式见 build_rdp_connection()
            expire_minutes: 过期时间（分钟），默认5分钟

        Returns:
            完整的 JSON payload dict
        """
        expires_ms = int((time.time() + expire_minutes * 60) * 1000)
        return {
            "username": username,
            "expires": expires_ms,
            "connections": connections,
        }

    @staticmethod
    def build_rdp_connection(
        name: str,
        hostname: str,
        port: int = 3389,
        username: str = "",
        password: str = "",
        domain: str = "",
        security: str = "nla",
        ignore_cert: bool = True,
        remote_app: str = "",
        remote_app_dir: str = "",
        remote_app_args: str = "",
        enable_drive: bool = False,
        drive_name: str = "GuacDrive",
        drive_path: str = "",
        create_drive_path: bool = True,
        # RDP 高级参数
        color_depth: int = None,
        disable_gfx: bool = True,
        resize_method: str = "display-update",
        enable_wallpaper: bool = False,
        enable_font_smoothing: bool = True,
        disable_copy: bool = False,
        disable_paste: bool = False,
        enable_audio: bool = True,
        enable_audio_input: bool = False,
        enable_printing: bool = False,
        timezone: str = None,
        keyboard_layout: str = None,
    ) -> dict:
        """构建 RDP 连接参数

        Args:
            name: 连接显示名称（同时作为 JSON 中的 key）
            hostname: RDP 目标主机
            port: RDP 端口
            username/password/domain: RDP 认证
            security: 安全模式 (nla/tls/rdp/any)
            ignore_cert: 是否忽略证书
            remote_app/remote_app_dir/remote_app_args: RemoteApp 配置
            enable_drive/drive_name/drive_path/create_drive_path: 虚拟磁盘
            color_depth: 色深 8/16/24, None=自动
            disable_gfx: 禁用 GFX Pipeline (GUACAMOLE-2123)
            resize_method: display-update / reconnect
            enable_wallpaper: 显示桌面壁纸
            enable_font_smoothing: ClearType
            disable_copy/disable_paste: 剪贴板控制 (CLIPRDR)
            enable_audio/enable_audio_input: 音频
            enable_printing: 虚拟打印机
            timezone: 如 Asia/Shanghai
            keyboard_layout: 如 en-us-qwerty

        Returns:
            {name: {protocol, parameters}} 格式的 dict，可直接合并到 connections
        """
        params = {
            "hostname": hostname,
            "port": str(port),
            "security": security,
            "ignore-cert": "true" if ignore_cert else "false",
            "resize-method": resize_method,
        }

        if username:
            params["username"] = username
        if password:
            params["password"] = password
        if domain:
            params["domain"] = domain
        if remote_app:
            params["remote-app"] = remote_app
        if remote_app_dir:
            params["remote-app-dir"] = remote_app_dir
        if remote_app_args:
            params["remote-app-args"] = remote_app_args

        # 显示与性能
        if color_depth in (8, 16, 24):
            params["color-depth"] = str(color_depth)
        if disable_gfx:
            params["disable-gfx"] = "true"
        if enable_wallpaper:
            params["enable-wallpaper"] = "true"
        if enable_font_smoothing:
            params["enable-font-smoothing"] = "true"

        # 安全与剪贴板
        if disable_copy:
            params["disable-copy"] = "true"
        if disable_paste:
            params["disable-paste"] = "true"

        # 音频
        if enable_audio:
            params["enable-audio"] = "true"
            if enable_audio_input:
                params["enable-audio-input"] = "true"

        # 设备
        if enable_printing:
            params["enable-printing"] = "true"

        # 本地化
        if timezone:
            params["timezone"] = timezone
        if keyboard_layout:
            params["server-layout"] = keyboard_layout

        # Drive redirection: guacd 模拟虚拟磁盘，通过 RDP RDPDR 映射到远程会话
        # 远程端通过 \\tsclient\{drive_name} 访问；Download 子文件夹自动触发浏览器下载
        if enable_drive and drive_path:
            params["enable-drive"] = "true"
            params["drive-name"] = drive_name
            params["drive-path"] = drive_path
            params["create-drive-path"] = "true" if create_drive_path else "false"

        return {
            name: {
                "protocol": "rdp",
                "parameters": params,
            }
        }
