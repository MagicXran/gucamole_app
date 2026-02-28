# FastAPI + Guacamole 1.6.0 Encrypted JSON Auth 完整集成方案

> **部署方式**：Docker Compose ｜ **网络方式**：方案 A — 直接暴露两个端口（FastAPI :8000 + Guacamole :8080），不使用反向代理
>
> **可靠性说明**：本文档中所有加密算法、JSON 结构、环境变量映射均已通过阅读 Apache Guacamole 官方 GitHub 源码逐一验证，关键源文件包括 `CryptoService.java`、`UserDataService.java`、`UserData.java`、`ConfigurationService.java` 以及 Docker 镜像的 `010-map-guacamole-extensions.sh` 和 `100-generate-guacamole-home.sh`。

---

## 一、架构总览

```
用户浏览器
  │
  ├── http://your-server:8000  ──→  FastAPI 门户（卡片页、权限、加密发牌）
  │
  └── http://your-server:8080/guacamole  ──→  Guacamole Web 应用
                                               ├── guacamole-auth-jdbc-mysql （管理员原生登录）
                                               └── guacamole-auth-json      （FastAPI 发牌登录）

服务间通信（Docker 内部网络）：
  FastAPI ──POST /api/tokens──→ guacamole:8080
  guacamole ──→ guacd:4822 ──→ 目标 RDP/SSH/VNC 主机
```

### 两类用户

| 角色 | 入口 | 认证方式 |
|------|------|---------|
| **管理员** | `http://your-server:8080/guacamole` | MySQL/JDBC 原生登录（guacadmin） |
| **普通用户** | `http://your-server:8000`（FastAPI 门户） | 点击卡片 → FastAPI 加密 JSON → 换 authToken → 自动跳转 Guacamole |

### 完整流程时序

```
用户浏览器                    FastAPI (:8000)              Guacamole (:8080)           guacd → RDP主机
    │                            │                              │                         │
    │  1. POST /launch/42        │                              │                         │
    │  (带 JWT)                  │                              │                         │
    ├───────────────────────────▶│                              │                         │
    │                            │  2. 查权限 ✓                 │                         │
    │                            │  3. 构建 JSON payload        │                         │
    │                            │  4. HMAC签名 + AES加密       │                         │
    │                            │  5. POST /api/tokens         │                         │
    │                            │     data=<base64>            │                         │
    │                            ├─────────────────────────────▶│                         │
    │                            │                              │  6. 解密验签 ✓          │
    │                            │  7. { authToken: "xxx" }     │                         │
    │                            │◀─────────────────────────────┤                         │
    │  8. { redirect_url }       │                              │                         │
    │◀───────────────────────────┤                              │                         │
    │                            │                              │                         │
    │  9. GET /guacamole/#/client/...?token=xxx                 │                         │
    ├──────────────────────────────────────────────────────────▶│                         │
    │                            │                              │  10. WebSocket 建立     │
    │◀═══════════════════════════════════════════════════════════╪════════════════════════▶│
    │                            │                              │   RDP RemoteApp 会话     │
```

---

## 二、Docker Compose 部署 Guacamole（含 JSON Auth 扩展）

### 2.1 目录结构

```
guacamole-deploy/
├── docker-compose.yml
└── init/                  ← 数据库初始化脚本（自动生成）
    └── initdb.sql
```

### 2.2 第一步：生成数据库初始化脚本

```bash
mkdir -p guacamole-deploy/init
cd guacamole-deploy

# 用官方镜像自带工具导出 MySQL schema
docker run --rm guacamole/guacamole:1.6.0 \
  /opt/guacamole/bin/initdb.sh --mysql > init/initdb.sql
```

这会生成约 23 张表的建表语句，包含默认管理员账号 `guacadmin / guacadmin`。

> **注意**：如果你已有一个正在运行的 MySQL 实例和已初始化的 guacamole_db，跳过此步，直接复用现有数据。你的现有 `docker-compose.yml` 中已经有 `./initdb.sql` 挂载，确认数据库已初始化即可。

### 2.3 第二步：生成共享密钥

```bash
# 生成 128 位随机密钥（32 位十六进制 = 16 字节）
openssl rand -hex 16
# 示例输出：a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
```

**记下这个值**，`docker-compose.yml` 和 FastAPI 配置中都要用到，必须完全一致。

> **为什么是 16 字节？** Guacamole 源码 `ConfigurationService.java` 中使用 `ByteArrayProperty` 读取 `json-secret-key`，并将其作为 AES 密钥。`CryptoService.java` 使用 `AES/CBC/PKCS5Padding`，对应 AES-128 需要 16 字节密钥（32 位十六进制）。

### 2.4 第三步：docker-compose.yml

以下是基于你现有配置改造的完整版本。改动点用 `# ★ 新增/修改` 标注：

```yaml
services:

  # ============================================================
  # 1. guacd —— Guacamole 协议代理守护进程
  # ============================================================
  guacd:
    container_name: guacd
    image: guacamole/guacd:1.6.0          # ★ 建议锁定版本
    restart: unless-stopped

  # ============================================================
  # 2. MySQL —— Guacamole 后端数据库
  # ============================================================
  guac-sql:
    container_name: guac-sql
    image: mysql:8
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: xran                     # ⚠️ 生产环境请用强密码
      MYSQL_DATABASE: guacamole_db
      MYSQL_USER: guacamole_user
      MYSQL_PASSWORD: xran                          # ⚠️ 生产环境请用强密码
    volumes:
      - ./init/initdb.sql:/docker-entrypoint-initdb.d/initdb.sql  # ★ 注意路径
      - /home/xran/data:/var/lib/mysql
    ports:
      - "127.0.0.1:33060:3306"

  # ============================================================
  # 3. Guacamole —— Web 应用（Tomcat）
  #    同时启用 JDBC + JSON 两个认证扩展
  # ============================================================
  guac_web:
    container_name: guac_web
    image: guacamole/guacamole:1.6.0      # ★ 建议锁定版本
    restart: unless-stopped
    ports:
      - 8080:8080
    environment:
      # ---- guacd 连接 ----
      GUACD_HOSTNAME: guacd
      GUACD_PORT: "4822"

      # ---- MySQL/JDBC 认证（管理员登录 + 连接管理）----
      MYSQL_HOSTNAME: guac-sql
      MYSQL_PORT: "3306"
      MYSQL_DATABASE: guacamole_db
      MYSQL_USER: guacamole_user
      MYSQL_PASSWORD: xran

      # ---- ★ Encrypted JSON 认证（FastAPI 发牌用）----
      # 只需这一个环境变量！扩展自动启用！
      JSON_SECRET_KEY: "你生成的32位hex密钥"

    depends_on:
      - guac-sql
      - guacd
```

#### 为什么只需一个环境变量就能启用 JSON Auth 扩展？

这是 Docker 镜像内部的自动化机制，不是魔法。以下是精确的原理链（来自官方源码）：

1. **构建阶段**（`010-map-guacamole-extensions.sh`）：镜像构建时，将 `guacamole-auth-json` 扩展的 jar 包映射到环境变量前缀 `JSON_`：
   ```
   guacamole-auth-json.........................JSON_
   ```

2. **启动阶段**（`700-configure-features.sh`）：容器启动时，遍历 `/opt/guacamole/environment/` 下所有前缀目录。对于 `JSON_` 前缀，检查是否存在任何以 `JSON_` 开头的环境变量。如果存在（比如 `JSON_SECRET_KEY`），就自动将对应的 jar 包链接到 `GUACAMOLE_HOME/extensions/`。

3. **属性映射**（`100-generate-guacamole-home.sh`）：`guacamole.properties` 中写入 `enable-environment-properties: true`，这使得环境变量 `JSON_SECRET_KEY` 自动映射为 Guacamole 属性 `json-secret-key`（规则：大写→小写，下划线→连字符）。

4. **扩展读取**（`ConfigurationService.java`）：`guacamole-auth-json` 扩展启动时，通过 `json-secret-key` 属性读取密钥。

**结论：你不需要手动下载 jar 包，不需要挂载 extensions 目录，不需要编辑 guacamole.properties。设置 `JSON_SECRET_KEY` 环境变量就够了。**

### 2.5 第四步：启动

```bash
cd guacamole-deploy
docker compose up -d
```

> **从你现有环境迁移**：如果你的旧 `docker-compose.yml` 正在运行，只需在 `guac_web` 服务的 `environment` 中加上 `JSON_SECRET_KEY` 和版本锁定，然后 `docker compose up -d`（Docker 会自动重建变更的容器）。MySQL 数据不受影响。

### 2.6 第五步：验证扩展加载

```bash
# 1. 查看日志，确认两个扩展都已加载
docker logs guac_web 2>&1 | grep -iE "extension|loaded|json|jdbc"

# 期望看到类似：
#   Extension "MySQL Authentication" loaded.
#   Extension "JSON Authentication" loaded.

# 如果只看到 MySQL 没看到 JSON，检查：
# - 环境变量名是否完全正确：JSON_SECRET_KEY（不是 JSON_SECRET 或 JSON_KEY）
# - 密钥格式：32 位十六进制字符串（16 字节）
# - 尝试显式加上 JSON_ENABLED: "true"
```

```bash
# 2. 管理员登录测试
#    浏览器打开 http://your-server:8080/guacamole
#    用 guacadmin / guacadmin 登录（首次登录后立即改密码！）
```

### 2.7 第六步：验证 JSON Auth 端到端

在任意有 Python + cryptography 库的机器上运行以下脚本：

```python
#!/usr/bin/env python3
"""
verify_json_auth.py
验证 Guacamole Encrypted JSON Auth 扩展是否配置正确。
如果返回 authToken 说明扩展工作正常。

依赖：pip install cryptography
"""

import json, hmac, hashlib, base64, time, urllib.request, urllib.parse
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

# ===== ↓↓↓ 改成你的实际值 ↓↓↓ =====
SECRET_KEY_HEX = "你生成的32位hex密钥"
GUACAMOLE_URL  = "http://your-server:8080/guacamole"
# ===== ↑↑↑ 改成你的实际值 ↑↑↑ =====

key = bytes.fromhex(SECRET_KEY_HEX)

# 构建 JSON payload
payload = {
    "username": "verify_test",
    "expires": int((time.time() + 300) * 1000),  # 5分钟后过期（毫秒）
    "connections": {
        "Test Connection": {
            "protocol": "ssh",
            "parameters": {
                "hostname": "127.0.0.1",
                "port": "22"
            }
        }
    }
}

# 加密流程：JSON → HMAC签名 → 拼接 → PKCS7填充 → AES-CBC加密 → base64
json_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
signature = hmac.new(key, json_bytes, hashlib.sha256).digest()

padder = sym_padding.PKCS7(128).padder()
padded = padder.update(signature + json_bytes) + padder.finalize()

cipher = Cipher(algorithms.AES(key), modes.CBC(b'\x00' * 16))
encrypted = cipher.encryptor().update(padded) + cipher.encryptor().finalize()

# ⚠️ 上面的写法有 bug（两次 encryptor()），正确写法：
encryptor = Cipher(algorithms.AES(key), modes.CBC(b'\x00' * 16)).encryptor()
encrypted = encryptor.update(padded) + encryptor.finalize()

b64 = base64.b64encode(encrypted).decode('ascii')

# POST 到 Guacamole /api/tokens
data = urllib.parse.urlencode({"data": b64}).encode('ascii')
req = urllib.request.Request(f"{GUACAMOLE_URL}/api/tokens", data=data)
req.add_header("Content-Type", "application/x-www-form-urlencoded")

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        print("✅ 成功！JSON Auth 扩展工作正常")
        print(f"   authToken : {result['authToken'][:20]}...")
        print(f"   dataSource: {result.get('dataSource', 'N/A')}")
        print(f"   username  : {result.get('username', 'N/A')}")
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8', errors='replace')
    print(f"❌ HTTP {e.code}: {body}")
    print("   排查清单：")
    print("   1. 密钥是否与 docker-compose.yml 中 JSON_SECRET_KEY 完全一致？")
    print("   2. Guacamole 是否已启动？docker logs guac_web")
    print("   3. 扩展是否已加载？docker logs guac_web | grep -i json")
except Exception as e:
    print(f"❌ 连接失败: {e}")
    print("   请检查 GUACAMOLE_URL 是否正确、网络是否可达")
```

---

## 三、加密算法详解（官方源码验证）

### 3.1 算法规范

| 步骤 | 操作 | 对应 Guacamole 源码 |
|------|------|-------------------|
| 1 | JSON 序列化为 UTF-8 字节 | `UserDataService.java` 反序列化时使用 UTF-8 |
| 2 | HMAC-SHA256(key, json_bytes) → 32 字节签名 | `CryptoService.sign()` — `HmacSHA256` |
| 3 | plaintext = signature + json_bytes | `UserDataService.java:141-142` — split at SIGNATURE_LENGTH(32) |
| 4 | PKCS7 填充至 AES 块大小（16 字节） | `AES/CBC/PKCS5Padding`（Java 的 PKCS5=PKCS7 for AES） |
| 5 | AES-128-CBC 加密，IV = 16 个 0x00 | `CryptoService.decrypt()` — `NULL_IV` |
| 6 | base64 编码 | `UserDataService.java:134` — `BaseEncoding.base64().decode(base64)` |

### 3.2 Guacamole 解密流程（源码 UserDataService.java）

```
base64 string
    ↓ base64 decode
ciphertext bytes
    ↓ AES/CBC/PKCS5Padding decrypt (key, IV=0x00*16)
decrypted bytes
    ↓ split at byte 32
[0:32]  = received_signature
[32:]   = json_bytes
    ↓ HMAC-SHA256(key, json_bytes)
computed_signature
    ↓ compare received_signature == computed_signature
    ↓ if match: parse json_bytes as UserData
    ↓ check expires > now
UserData { username, expires, connections }
```

### 3.3 JSON Payload 结构（源码 UserData.java）

```json
{
    "username": "string (必需)",
    "expires": 1234567890123,
    "singleUse": false,
    "connections": {
        "连接名称（即 identifier）": {
            "id": "string (可选，用于 join)",
            "protocol": "rdp|vnc|ssh|telnet",
            "parameters": {
                "hostname": "192.168.1.100",
                "port": "3389",
                ...
            }
        }
    }
}
```

**字段说明**（来自 `UserData.java`）：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `username` | string | ✅ | 用户名，用于 `${GUAC_USERNAME}` 令牌替换 |
| `expires` | long/null | 建议 | UNIX 毫秒时间戳，过期后数据无效。null = 永不过期 |
| `singleUse` | boolean | 否 | 默认 false。设为 true 后数据只能使用一次（需配合 expires） |
| `connections` | map | ✅ | key = 连接标识符（同时也是显示名称），value = Connection 对象 |

**Connection 对象字段**（来自 `UserData.Connection`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `protocol` | string | 协议名：`rdp`, `vnc`, `ssh`, `telnet` |
| `parameters` | map | 协议参数，key-value 均为 string |
| `id` | string | 可选。唯一 ID，允许其他连接通过 `join` 加入此连接（屏幕共享） |
| `join` | string | 可选。要加入的连接的 `id`，设置后 protocol 被忽略 |
| `singleUse` | boolean | 可选。连接级别的一次性标记，使用后立即从目录中移除 |

### 3.4 RDP RemoteApp 参数示例

```json
{
    "username": "user1",
    "expires": 1772200000000,
    "connections": {
        "Excel": {
            "protocol": "rdp",
            "parameters": {
                "hostname": "192.168.1.50",
                "port": "3389",
                "username": "CORP\\user1",
                "password": "pass123",
                "domain": "CORP",
                "security": "nla",
                "ignore-cert": "true",
                "remote-app": "||Excel",
                "remote-app-dir": "C:\\Program Files\\Microsoft Office\\root\\Office16",
                "remote-app-args": "/e",
                "enable-wallpaper": "false",
                "enable-font-smoothing": "true",
                "color-depth": "24",
                "width": "1920",
                "height": "1080",
                "resize-method": "reconnect"
            }
        }
    }
}
```

> **参数命名规则**：JSON 中的参数名使用**小写连字符**格式（如 `remote-app`, `ignore-cert`），与 Guacamole 官方文档一致。不是下划线格式。

### 3.5 常用 RDP 参数速查

| 参数 | 说明 | 示例 |
|------|------|------|
| `hostname` | RDP 主机地址 | `192.168.1.50` |
| `port` | 端口 | `3389` |
| `username` | 登录用户 | `CORP\\user1` |
| `password` | 密码 | `pass123` |
| `domain` | Windows 域 | `CORP` |
| `security` | 安全模式 | `nla`, `tls`, `rdp`, `any` |
| `ignore-cert` | 忽略证书 | `true` / `false` |
| `remote-app` | RemoteApp 程序路径 | `\|\|Excel` |
| `remote-app-dir` | 工作目录 | `C:\\...` |
| `remote-app-args` | 程序参数 | `/e` |
| `width` / `height` | 分辨率 | `1920` / `1080` |
| `color-depth` | 色深 | `8`, `16`, `24`, `32` |
| `enable-font-smoothing` | 字体平滑 | `true` |
| `resize-method` | 窗口缩放 | `display-update`, `reconnect` |
| `disable-audio` | 禁用音频 | `true` |
| `enable-drive` | 文件传输 | `true` |
| `drive-path` | 共享目录 | `/share` |
| `enable-printing` | 打印重定向 | `true` |

---

## 四、FastAPI 侧实现

### 4.1 核心加密模块

```python
# guacamole_crypto.py
"""
Guacamole Encrypted JSON Auth — 加密模块
算法严格匹配 Apache Guacamole CryptoService.java（AES/CBC/PKCS5Padding + HMAC-SHA256）
"""

import json
import hmac
import hashlib
import base64
import time
from typing import Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding


class GuacamoleCrypto:
    """Guacamole Encrypted JSON 加密器"""

    SIGNATURE_LENGTH = 32  # HMAC-SHA256 输出长度（字节），对应 CryptoService.SIGNATURE_LENGTH

    def __init__(self, secret_key_hex: str):
        """
        Args:
            secret_key_hex: 32 位十六进制字符串（16 字节 = AES-128 密钥）
        """
        self._key = bytes.fromhex(secret_key_hex)
        if len(self._key) != 16:
            raise ValueError(
                f"密钥必须是 16 字节（32 位 hex），当前 {len(self._key)} 字节。"
                f"请用 openssl rand -hex 16 生成。"
            )
        self._null_iv = b'\x00' * 16

    def encrypt(self, payload: dict) -> str:
        """
        加密 JSON payload，返回 base64 字符串，可直接用于 POST /api/tokens 的 data 参数。

        加密流程（对应 Guacamole 解密的逆过程）：
        1. JSON → UTF-8 bytes（紧凑格式，无多余空格）
        2. HMAC-SHA256(key, json_bytes) → 32 字节签名
        3. plaintext = signature + json_bytes
        4. PKCS7 填充至 16 字节倍数
        5. AES-128-CBC(key, IV=0x00*16) 加密
        6. base64 编码
        """
        # 1. JSON 序列化
        json_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

        # 2. HMAC-SHA256 签名
        signature = hmac.new(self._key, json_bytes, hashlib.sha256).digest()

        # 3. 拼接
        plaintext = signature + json_bytes

        # 4. PKCS7 填充
        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()

        # 5. AES-128-CBC 加密
        encryptor = Cipher(
            algorithms.AES(self._key),
            modes.CBC(self._null_iv)
        ).encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()

        # 6. base64 编码
        return base64.b64encode(ciphertext).decode('ascii')

    def build_payload(
        self,
        username: str,
        connections: dict,
        expire_minutes: int = 5,
        single_use: bool = False,
    ) -> dict:
        """
        构建符合 UserData.java 结构的 JSON payload。

        Args:
            username: 用户名
            connections: 连接字典，格式见 build_rdp_connection()
            expire_minutes: 过期时间（分钟），默认 5
            single_use: 是否单次使用

        Returns:
            可直接传给 encrypt() 的 dict
        """
        payload = {
            "username": username,
            "expires": int((time.time() + expire_minutes * 60) * 1000),
            "connections": connections,
        }
        if single_use:
            payload["singleUse"] = True
        return payload

    @staticmethod
    def build_rdp_connection(
        connection_name: str,
        hostname: str,
        port: str = "3389",
        username: str = "",
        password: str = "",
        domain: str = "",
        security: str = "nla",
        ignore_cert: bool = True,
        remote_app: str = "",
        remote_app_dir: str = "",
        remote_app_args: str = "",
        width: str = "1920",
        height: str = "1080",
        color_depth: str = "24",
        **extra_params,
    ) -> dict:
        """
        构建 RDP 连接参数字典。

        Returns:
            {connection_name: {"protocol": "rdp", "parameters": {...}}}
        """
        params = {
            "hostname": hostname,
            "port": str(port),
            "security": security,
            "ignore-cert": str(ignore_cert).lower(),
            "width": str(width),
            "height": str(height),
            "color-depth": str(color_depth),
            "enable-font-smoothing": "true",
            "resize-method": "reconnect",
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

        # 合并额外参数
        for k, v in extra_params.items():
            params[k.replace('_', '-')] = str(v)

        return {
            connection_name: {
                "protocol": "rdp",
                "parameters": params,
            }
        }

    @staticmethod
    def build_ssh_connection(
        connection_name: str,
        hostname: str,
        port: str = "22",
        username: str = "",
        password: str = "",
        private_key: str = "",
        **extra_params,
    ) -> dict:
        """构建 SSH 连接参数字典。"""
        params = {
            "hostname": hostname,
            "port": str(port),
        }
        if username:
            params["username"] = username
        if password:
            params["password"] = password
        if private_key:
            params["private-key"] = private_key

        for k, v in extra_params.items():
            params[k.replace('_', '-')] = str(v)

        return {
            connection_name: {
                "protocol": "ssh",
                "parameters": params,
            }
        }

    @staticmethod
    def build_vnc_connection(
        connection_name: str,
        hostname: str,
        port: str = "5900",
        password: str = "",
        **extra_params,
    ) -> dict:
        """构建 VNC 连接参数字典。"""
        params = {
            "hostname": hostname,
            "port": str(port),
        }
        if password:
            params["password"] = password

        for k, v in extra_params.items():
            params[k.replace('_', '-')] = str(v)

        return {
            connection_name: {
                "protocol": "vnc",
                "parameters": params,
            }
        }
```

### 4.2 Token 交换服务

```python
# guacamole_service.py
"""
Guacamole Token 交换服务：
加密 JSON → POST /api/tokens → 拿到 authToken → 拼 URL
"""

import base64
import urllib.parse
import httpx

from guacamole_crypto import GuacamoleCrypto


class GuacamoleService:
    """与 Guacamole 服务端交互的服务层"""

    def __init__(
        self,
        secret_key_hex: str,
        internal_url: str,
        external_url: str,
        default_expire_minutes: int = 5,
    ):
        """
        Args:
            secret_key_hex: 共享密钥
            internal_url: FastAPI 进程访问 Guacamole 的地址（Docker 内部或 localhost）
                          例如 "http://guac_web:8080/guacamole"
            external_url: 用户浏览器跳转到 Guacamole 的地址
                          例如 "http://your-server:8080/guacamole"
            default_expire_minutes: 加密 JSON 默认有效期
        """
        self.crypto = GuacamoleCrypto(secret_key_hex)
        self.internal_url = internal_url.rstrip('/')
        self.external_url = external_url.rstrip('/')
        self.default_expire_minutes = default_expire_minutes

    async def get_auth_token(self, encrypted_data: str) -> dict:
        """
        将加密数据 POST 到 Guacamole /api/tokens，获取 authToken。

        Args:
            encrypted_data: base64 加密后的 data 字符串

        Returns:
            Guacamole API 响应，包含 authToken, username, dataSource 等

        Raises:
            httpx.HTTPStatusError: Guacamole 返回错误（如 403）
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.internal_url}/api/tokens",
                data={"data": encrypted_data},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            return resp.json()

    def build_client_url(
        self,
        auth_token: str,
        connection_name: str,
    ) -> str:
        """
        构建用户浏览器直接跳转的 URL。

        Guacamole 前端 URL 格式：
        /guacamole/#/client/<encoded_id>?token=<authToken>

        其中 encoded_id = base64(connection_identifier + NUL + "c" + NUL + "json")
        - connection_identifier = connections 字典中的 key
        - "c" 表示 connection 类型
        - "json" 是 JSON Auth 的 dataSource 标识

        注意：当 JSON payload 中只有一个连接时，Guacamole 会自动连接该连接，
        即使 URL 中不指定 client 路径也能工作（仅携带 token 参数即可）。
        但显式指定 connection 路径是更可靠的做法。
        """
        # 构建连接标识符：connectionName + NUL + "c" + NUL + "json"
        identifier = f"{connection_name}\x00c\x00json"
        encoded_id = base64.b64encode(identifier.encode('utf-8')).decode('ascii')

        # 移除 base64 padding 的 '='（Guacamole 前端的约定）
        encoded_id = encoded_id.rstrip('=')

        return f"{self.external_url}/#/client/{encoded_id}?token={auth_token}"

    async def launch_connection(
        self,
        username: str,
        connections: dict,
        target_connection_name: str,
        expire_minutes: int = None,
        single_use: bool = False,
    ) -> str:
        """
        一站式操作：构建 payload → 加密 → 换 token → 返回跳转 URL。

        Args:
            username: 用户名
            connections: 连接字典（来自 build_rdp_connection 等方法）
            target_connection_name: 要跳转到的连接名（connections 中的 key）
            expire_minutes: 过期时间，默认使用初始化时的值
            single_use: 是否单次使用

        Returns:
            完整的跳转 URL
        """
        if expire_minutes is None:
            expire_minutes = self.default_expire_minutes

        # 1. 构建 payload
        payload = self.crypto.build_payload(
            username=username,
            connections=connections,
            expire_minutes=expire_minutes,
            single_use=single_use,
        )

        # 2. 加密
        encrypted = self.crypto.encrypt(payload)

        # 3. 换 token
        result = await self.get_auth_token(encrypted)
        auth_token = result["authToken"]

        # 4. 拼 URL
        return self.build_client_url(auth_token, target_connection_name)
```

### 4.3 配置

```python
# config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---- 你现有的 FastAPI 配置 ----
    DATABASE_URL: str = "mysql+asyncmy://user:pass@localhost/fastapi_db"
    SECRET_KEY: str = "your-fastapi-jwt-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ---- Guacamole 集成（新增）----
    # 必须与 docker-compose.yml 中的 JSON_SECRET_KEY 完全一致
    GUACAMOLE_JSON_SECRET_KEY: str = "你生成的32位hex密钥"

    # FastAPI 进程访问 Guacamole 的地址
    # - FastAPI 也在同一个 Docker Compose 中：用容器名
    GUACAMOLE_INTERNAL_URL: str = "http://guac_web:8080/guacamole"
    # - FastAPI 在宿主机上运行：
    # GUACAMOLE_INTERNAL_URL: str = "http://localhost:8080/guacamole"

    # 用户浏览器跳转用的地址（公网/内网 IP）
    GUACAMOLE_EXTERNAL_URL: str = "http://your-server:8080/guacamole"

    # 加密 JSON 有效期（分钟）
    GUACAMOLE_TOKEN_EXPIRE_MINUTES: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
```

### 4.4 初始化服务实例

```python
# app.py 或 dependencies.py
from guacamole_service import GuacamoleService
from config import settings

guac_service = GuacamoleService(
    secret_key_hex=settings.GUACAMOLE_JSON_SECRET_KEY,
    internal_url=settings.GUACAMOLE_INTERNAL_URL,
    external_url=settings.GUACAMOLE_EXTERNAL_URL,
    default_expire_minutes=settings.GUACAMOLE_TOKEN_EXPIRE_MINUTES,
)
```

### 4.5 API 路由

```python
# routers/remote_app.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/remote-apps", tags=["remote-apps"])


@router.post("/launch/{app_id}")
async def launch_app(
    app_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    点击卡片 → 生成加密 JSON → 换 Token → 返回跳转 URL

    前端收到 redirect_url 后：
    window.open(redirect_url, '_blank');
    """
    # 1. 查权限 + 获取应用配置
    app = await check_permission_and_get_app(db, current_user.id, app_id)
    if not app:
        raise HTTPException(status_code=403, detail="无权限访问此应用")

    # 2. 构建连接参数
    connections = guac_service.crypto.build_rdp_connection(
        connection_name=app.name,
        hostname=app.hostname,
        port=app.port,
        username=app.rdp_username,
        password=app.rdp_password,
        domain=app.domain or "",
        security=app.security or "nla",
        ignore_cert=app.ignore_cert if app.ignore_cert is not None else True,
        remote_app=app.remote_app or "",           # 如 "||Excel"
        remote_app_dir=app.remote_app_dir or "",
        remote_app_args=app.remote_app_args or "",
    )

    # 3. 一站式：加密 → 换 token → 拼 URL
    try:
        redirect_url = await guac_service.launch_connection(
            username=current_user.username,
            connections=connections,
            target_connection_name=app.name,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Guacamole 服务不可用: {str(e)}"
        )

    # 4. 返回 URL
    return JSONResponse({"redirect_url": redirect_url})
```

### 4.6 前端调用

```javascript
// 卡片点击事件
async function launchApp(appId) {
    try {
        const resp = await fetch(`/api/remote-apps/launch/${appId}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });

        if (!resp.ok) {
            const err = await resp.json();
            alert(`启动失败: ${err.detail}`);
            return;
        }

        const { redirect_url } = await resp.json();
        window.open(redirect_url, '_blank');  // 新标签页打开远程桌面
    } catch (e) {
        alert(`网络错误: ${e.message}`);
    }
}
```

用户浏览器将跳转到类似：
```
http://your-server:8080/guacamole/#/client/RXhjZWwAYwBqc29u?token=C90FE116...
```

### 4.7 FastAPI 加入同一个 Docker Compose（可选）

如果你希望 FastAPI 也容器化部署：

```yaml
  fastapi:
    build: ./your-fastapi-project
    container_name: fastapi
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      GUACAMOLE_INTERNAL_URL: "http://guac_web:8080/guacamole"  # 容器名直接访问
      GUACAMOLE_EXTERNAL_URL: "http://your-server:8080/guacamole"
      GUACAMOLE_JSON_SECRET_KEY: "你生成的32位hex密钥"
    depends_on:
      - guac_web
```

注意区分两个 URL：
- `INTERNAL_URL`：FastAPI **进程**访问 Guacamole（走 Docker 内部网络，用容器名 `guac_web`）
- `EXTERNAL_URL`：**用户浏览器**跳转到 Guacamole（走宿主机端口映射）

### 4.8 数据模型建议

你只需要保证点击某卡片时能回答两个问题：这个用户是否允许访问这个应用？应用对应的连接参数是什么？

```sql
-- apps 表：应用/连接模板
CREATE TABLE apps (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,          -- 显示名称，同时作为连接标识符
    icon        VARCHAR(255),                    -- 卡片图标
    hostname    VARCHAR(255) NOT NULL,          -- RDP 主机地址
    port        INT DEFAULT 3389,
    rdp_username VARCHAR(255),
    rdp_password VARCHAR(255),                  -- ⚠️ 建议加密存储
    domain      VARCHAR(255),
    security    VARCHAR(20) DEFAULT 'nla',
    ignore_cert BOOLEAN DEFAULT TRUE,
    remote_app  VARCHAR(255),                   -- 如 "||Excel"
    remote_app_dir VARCHAR(512),
    remote_app_args VARCHAR(512),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- app_acl 表：用户/角色 → 应用的访问控制
CREATE TABLE app_acl (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,                       -- 关联你的用户表
    app_id  INT NOT NULL,                       -- 关联 apps 表
    UNIQUE KEY uk_user_app (user_id, app_id)
);
```

---

## 五、常见问题

### Q1：JSON 扩展没有加载？

```bash
docker logs guac_web 2>&1 | grep -iE "json|extension|loaded"
```

如果没看到 JSON 相关输出：

1. 确认环境变量名完全正确：`JSON_SECRET_KEY`（不是 `JSON_KEY` 或 `GUACAMOLE_JSON_SECRET_KEY`）
2. 尝试显式启用：在 `environment` 中加上 `JSON_ENABLED: "true"`
3. 确认镜像版本：`guacamole/guacamole:1.6.0`（不带版本号的 `latest` 也可以，但锁定版本更安全）
4. 重建容器：`docker compose up -d --force-recreate guac_web`

### Q2：POST /api/tokens 返回 403 INVALID_CREDENTIALS？

按以下顺序排查：

1. **密钥不一致**：对比 `docker-compose.yml` 中的 `JSON_SECRET_KEY` 和 FastAPI 中的值，必须一模一样（大小写敏感）
2. **JSON 已过期**：检查两台服务器系统时间是否同步（`expires` 是 UNIX 毫秒时间戳）
3. **base64 损坏**：确保传输时没有引入换行符或 URL 编码问题
4. **查看详细日志**：
   ```bash
   docker logs guac_web 2>&1 | grep -iE "warn|error|json|signature|decrypt"
   ```

### Q3：管理员登录会不会被 JSON Auth 影响？

不会。两个扩展独立工作：
- 用户名/密码提交 → JDBC/MySQL 扩展处理
- `data` 参数提交 → JSON Auth 扩展处理
- 管理员登录页面不受任何影响

### Q4：JSON Auth 创建的连接，管理员在后台能看到吗？

看不到。JSON Auth 创建的用户和连接是临时的（ephemeral），仅在会话存活期间存在，不写入 MySQL。这正好符合需求：管理员管理自己的连接，普通用户的连接完全由 FastAPI 控制。

### Q5：可以限制哪些 IP 能使用 JSON Auth？

可以。通过环境变量设置受信网络：

```yaml
JSON_TRUSTED_NETWORKS: "172.16.0.0/12,192.168.0.0/16"
```

对应 `guacamole.properties` 中的 `json-trusted-networks`。只有来自这些网段的请求才能使用加密 JSON 认证。

### Q6：单连接时是否需要指定 client 路径？

当 JSON payload 中只包含一个连接时，Guacamole 前端会自动连接该连接，即使 URL 不包含 `#/client/xxx` 也能工作。但为了确定性（避免前端 SPA 路由问题），建议始终显式指定连接路径。

### Q7：`singleUse` 有什么用？

设为 `true` 后，该加密 JSON 只能使用一次。Guacamole 内部维护了一个 denylist（`UserDataDenylist`），已使用的签名会被记录，防止重放攻击。注意：`singleUse` 必须配合 `expires` 使用（没有过期时间的数据不支持单次使用检查）。

---

## 六、安全建议

1. **强密码**：生产环境中 MySQL 密码、guacadmin 密码务必使用强密码
2. **密钥保护**：`JSON_SECRET_KEY` 不要提交到版本控制。可以使用 Docker secrets 或 `.env` 文件
3. **HTTPS**：如果在公网部署，请在 FastAPI 和 Guacamole 前面加一层 TLS（Nginx/Caddy/云 LB）
4. **过期时间**：`expire_minutes` 建议 5 分钟以内，配合 `singleUse: true` 防止重放
5. **受信网络**：在 Guacamole 侧配置 `JSON_TRUSTED_NETWORKS` 限制只有 FastAPI 服务器能提交加密 JSON
6. **RDP 密码**：在 FastAPI 数据库中加密存储 RDP 密码（不要明文）

---

## 七、实施清单

```
[ ] 1. 准备目录：mkdir -p guacamole-deploy/init && cd guacamole-deploy
[ ] 2. 生成 initdb.sql（如果是全新部署）:
        docker run --rm guacamole/guacamole:1.6.0 /opt/guacamole/bin/initdb.sh --mysql > init/initdb.sql
[ ] 3. 生成密钥：openssl rand -hex 16 → 记录密钥
[ ] 4. 编写 docker-compose.yml（填入密码和 JSON_SECRET_KEY）
[ ] 5. 启动：docker compose up -d
[ ] 6. 确认扩展加载：docker logs guac_web | grep -i json
[ ] 7. 管理员登录测试：http://your-server:8080/guacamole → guacadmin
[ ] 8. 运行 verify_json_auth.py → 拿到 authToken
[ ] 9. FastAPI config.py 填入同一个密钥
[ ] 10. 复制 guacamole_crypto.py + guacamole_service.py 到 FastAPI 项目
[ ] 11. pip install cryptography httpx
[ ] 12. 添加 API 路由
[ ] 13. 启动 FastAPI → 测试完整流程：点击卡片 → 跳转到 Guacamole RemoteApp
```
