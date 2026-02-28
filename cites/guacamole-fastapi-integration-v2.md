# FastAPI + Guacamole 1.6.0 Encrypted JSON Auth 集成方案

> **部署方式**：Docker Compose ｜ **网络方式**：方案 A — 直接暴露两个端口，不使用反向代理

---

## 一、架构总览

```
用户浏览器
  │
  ├── http://your-server:8000  ──→  FastAPI 门户（卡片页、权限、加密发牌）
  │
  └── http://your-server:8080/guacamole  ──→  Guacamole（远程桌面会话）
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

### 2.3 第二步：生成共享密钥

```bash
# 生成 128 位随机密钥（32 位十六进制）
openssl rand -hex 16
# 示例输出：a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
```

**记下这个值**，下面 `docker-compose.yml` 和 FastAPI 配置中都要用到，必须完全一致。

### 2.4 第三步：docker-compose.yml

```yaml
services:

  # ============================================================
  # 1. MySQL —— Guacamole 后端数据库
  # ============================================================
  guac-db:
    image: mysql:8.0
    container_name: guac-db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: "your_root_password"     # 改成强密码
      MYSQL_DATABASE: "guacamole_db"
      MYSQL_USER: "guacamole_user"
      MYSQL_PASSWORD: "your_guac_db_password"       # 改成强密码
    volumes:
      # 首次启动时自动执行 init 目录下的 .sql 文件
      - ./init:/docker-entrypoint-initdb.d:ro
      # 数据持久化
      - guac-db-data:/var/lib/mysql

  # ============================================================
  # 2. guacd —— Guacamole 协议代理守护进程
  # ============================================================
  guacd:
    image: guacamole/guacd:1.6.0
    container_name: guacd
    restart: unless-stopped

  # ============================================================
  # 3. Guacamole —— Web 应用（Tomcat）
  #    同时启用 JDBC + JSON 两个认证扩展
  # ============================================================
  guacamole:
    image: guacamole/guacamole:1.6.0
    container_name: guacamole
    restart: unless-stopped
    ports:
      - "8080:8080"                                 # 外部访问端口
    environment:
      # ---- guacd 连接 ----
      GUACD_HOSTNAME: "guacd"
      GUACD_PORT: "4822"

      # ---- MySQL/JDBC 认证（管理员登录 + 连接管理）----
      MYSQL_HOSTNAME: "guac-db"
      MYSQL_PORT: "3306"
      MYSQL_DATABASE: "guacamole_db"
      MYSQL_USER: "guacamole_user"
      MYSQL_PASSWORD: "your_guac_db_password"       # 与上面一致

      # ---- Encrypted JSON 认证（FastAPI 发牌用）----
      # 只需设置这一个环境变量，扩展自动启用！
      JSON_SECRET_KEY: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"  # ← 替换为你生成的密钥

    depends_on:
      - guacd
      - guac-db

volumes:
  guac-db-data:
```

#### 关键说明

| 环境变量 | 作用 |
|---------|------|
| `MYSQL_*` | 启用 `guacamole-auth-jdbc-mysql` 扩展，管理员通过用户名/密码登录 |
| `JSON_SECRET_KEY` | 启用 `guacamole-auth-json` 扩展，接受外部系统（FastAPI）的加密 JSON |

Docker 镜像内部检测到 `JSON_SECRET_KEY` 后，会自动将 `guacamole-auth-json-1.6.0.jar` 拷入 `extensions/` 目录并写入 `guacamole.properties`。**你不需要手动下载 jar 包。**

### 2.5 第四步：启动

```bash
docker compose up -d
```

### 2.6 第五步：验证

```bash
# 1. 查看日志，确认两个扩展都已加载
docker logs guacamole 2>&1 | grep -i "extension\|loaded\|json\|jdbc"
# 期望看到：
#   Extension "guacamole-auth-jdbc-mysql" loaded.
#   Extension "guacamole-auth-json" loaded.

# 2. 管理员登录测试
#    浏览器打开 http://your-server:8080/guacamole
#    用 guacadmin / guacadmin 登录（首次登录后立即改密码！）

# 3. JSON Auth 测试（下一节用 Python 脚本验证）
```

### 2.7 验证 JSON Auth 扩展工作正常

在任意有 Python 的机器上运行：

```python
# verify_json_auth.py
# 用法：python verify_json_auth.py
# 如果返回 authToken 说明扩展配置正确

import json, hmac, hashlib, base64, time, urllib.request, urllib.parse
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.backends import default_backend

# ===== 改成你的实际值 =====
SECRET_KEY_HEX = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
GUACAMOLE_URL   = "http://your-server:8080/guacamole"
# ==========================

key = bytes.fromhex(SECRET_KEY_HEX)

payload = {
    "username": "verify_test",
    "expires": int((time.time() + 300) * 1000),
    "connections": {
        "Dummy": {
            "protocol": "ssh",
            "parameters": {"hostname": "127.0.0.1", "port": "22"}
        }
    }
}

json_bytes = json.dumps(payload, separators=(',', ':')).encode()
sig = hmac.new(key, json_bytes, hashlib.sha256).digest()

padder = sym_padding.PKCS7(128).padder()
padded = padder.update(sig + json_bytes) + padder.finalize()

enc = Cipher(algorithms.AES(key), modes.CBC(b'\x00'*16), default_backend()).encryptor()
encrypted = enc.update(padded) + enc.finalize()
b64 = base64.b64encode(encrypted).decode()

data = urllib.parse.urlencode({"data": b64}).encode()
req = urllib.request.Request(f"{GUACAMOLE_URL}/api/tokens", data=data)
try:
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    print("✅ 成功！JSON Auth 扩展工作正常")
    print(f"   authToken: {result['authToken'][:20]}...")
    print(f"   dataSource: {result['dataSource']}")
except Exception as e:
    print(f"❌ 失败: {e}")
    print("   请检查：密钥是否一致？Guacamole 是否已启动？")
```

---

## 三、FastAPI 侧配置

### 3.1 配置文件

```python
# config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---- 你现有的配置 ----
    DATABASE_URL: str = "mysql+asyncmy://user:pass@localhost/fastapi_db"
    SECRET_KEY: str = "your-fastapi-jwt-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ---- Guacamole 集成（新增）----
    # 必须与 docker-compose.yml 中的 JSON_SECRET_KEY 完全一致
    GUACAMOLE_JSON_SECRET_KEY: str = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"

    # FastAPI 容器/进程访问 Guacamole 的地址（服务端内部通信）
    # 如果 FastAPI 也在同一个 Docker 网络中：
    GUACAMOLE_INTERNAL_URL: str = "http://guacamole:8080/guacamole"
    # 如果 FastAPI 在宿主机上运行：
    # GUACAMOLE_INTERNAL_URL: str = "http://localhost:8080/guacamole"

    # 用户浏览器跳转用的地址
    GUACAMOLE_EXTERNAL_URL: str = "http://your-server:8080/guacamole"

    # 加密 JSON 有效期（分钟），防止重放攻击
    GUACAMOLE_TOKEN_EXPIRE_MINUTES: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
```

### 3.2 核心加密模块

上一版交付的 `guacamole_crypto.py` 和 `guacamole_service.py` **无需任何修改**，直接使用。

唯一需要调整的是 `GuacamoleService` 的初始化参数，使用上面的配置：

```python
# 在你的 FastAPI app 中初始化
from guacamole_service import GuacamoleService
from config import settings

guac_service = GuacamoleService(
    secret_key_hex=settings.GUACAMOLE_JSON_SECRET_KEY,
    internal_url=settings.GUACAMOLE_INTERNAL_URL,
    external_url=settings.GUACAMOLE_EXTERNAL_URL,
    default_expire_minutes=settings.GUACAMOLE_TOKEN_EXPIRE_MINUTES,
)
```

### 3.3 API 路由（启动 RemoteApp）

```python
# routers/remote_app.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/remote-apps", tags=["remote-apps"])


@router.post("/launch/{app_id}")
async def launch_app(
    app_id: int,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
):
    """点击卡片 → 生成加密 JSON → 换 Token → 返回跳转 URL"""

    # 1. 查权限
    app = await check_permission_and_get_app(db, current_user.id, app_id)

    # 2. 构建连接
    connections = guac_service.crypto.build_rdp_connection(
        connection_name=app.name,
        hostname=app.hostname,
        port=app.port,
        username=app.rdp_username,
        password=app.rdp_password,
        domain=app.domain,
        security=app.security or "nla",
        ignore_cert=app.ignore_cert,
        remote_app=app.remote_app,           # "||Excel"
        remote_app_dir=app.remote_app_dir,
        remote_app_args=app.remote_app_args,
    )

    # 3. 一站式：加密 → 换 token → 拼 URL
    redirect_url = await guac_service.launch_connection(
        username=current_user.username,
        connections=connections,
        target_connection_name=app.name,
    )

    # 4. 返回 URL，前端 window.open() 跳转
    return JSONResponse({"redirect_url": redirect_url})
```

前端收到后：

```javascript
const resp = await fetch(`/api/remote-apps/launch/${appId}`, { method: 'POST', ... });
const { redirect_url } = await resp.json();
window.open(redirect_url, '_blank');  // 新标签页直接进入 RemoteApp
```

用户浏览器将跳转到类似：
```
http://your-server:8080/guacamole/#/client/LTEyMzQ1NgBjAGpzb24=?token=C90FE116...
```

---

## 四、完整流程时序

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

## 五、常见问题

### Q1：`JSON_SECRET_KEY` 设置后扩展没加载？

检查日志：
```bash
docker logs guacamole 2>&1 | grep -i json
```

如果没看到 json 相关输出，尝试显式启用：
```yaml
# docker-compose.yml 中加上
JSON_ENABLED: "true"
JSON_SECRET_KEY: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
```

然后 `docker compose up -d`（会自动重建容器）。

### Q2：POST /api/tokens 返回 `INVALID_CREDENTIALS`？

按以下顺序排查：

1. **密钥不一致**：对比 `docker-compose.yml` 中的 `JSON_SECRET_KEY` 和 FastAPI `config.py` 中的值，必须一模一样（大小写敏感）
2. **JSON 已过期**：检查两台服务器系统时间是否同步（`expires` 是毫秒时间戳）
3. **Base64 损坏**：确保传输时没有引入换行符

查看 Guacamole 详细错误：
```bash
docker logs guacamole 2>&1 | grep -i "warn\|error\|json"
```

### Q3：管理员登录页会不会被 JSON Auth 影响？

不会。两个扩展各管各的：
- 用户名/密码登录 → JDBC 处理
- `data` 参数提交 → JSON Auth 处理
- 管理员登录页正常显示，无变化

### Q4：FastAPI 也放进同一个 Docker Compose 可以吗？

完全可以，把 FastAPI 服务加进去，共享 Docker 网络：

```yaml
  fastapi:
    build: ./your-fastapi-project
    ports:
      - "8000:8000"
    environment:
      GUACAMOLE_INTERNAL_URL: "http://guacamole:8080/guacamole"  # 容器名直接访问
      GUACAMOLE_EXTERNAL_URL: "http://your-server:8080/guacamole"
      GUACAMOLE_JSON_SECRET_KEY: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    depends_on:
      - guacamole
```

注意区分两个 URL：
- `INTERNAL_URL`：FastAPI **进程**访问 Guacamole（走 Docker 内部网络，用容器名）
- `EXTERNAL_URL`：**用户浏览器**跳转到 Guacamole（走宿主机端口）

### Q5：JSON Auth 创建的连接，管理员在 Guacamole 后台能看到吗？

看不到。JSON Auth 创建的用户和连接是临时的（ephemeral），仅在会话存活期间存在，不写入 MySQL。这正好符合需求：管理员管理自己的连接，普通用户的连接完全由 FastAPI 控制。

---

## 六、实施清单

```
[ ] 1. mkdir guacamole-deploy/init && cd guacamole-deploy
[ ] 2. docker run --rm guacamole/guacamole:1.6.0 /opt/guacamole/bin/initdb.sh --mysql > init/initdb.sql
[ ] 3. openssl rand -hex 16  →  记录密钥
[ ] 4. 编写 docker-compose.yml（填入密码和密钥）
[ ] 5. docker compose up -d
[ ] 6. docker logs guacamole  →  确认两个扩展都 loaded
[ ] 7. 浏览器 http://your-server:8080/guacamole  →  guacadmin 登录成功
[ ] 8. 运行 verify_json_auth.py  →  拿到 authToken
[ ] 9. FastAPI config.py 填入同一个密钥
[ ] 10. 启动 FastAPI，测试完整流程：点击卡片 → 跳转到 Guacamole RemoteApp
```
