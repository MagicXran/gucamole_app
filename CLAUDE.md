# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Guacamole RemoteApp Portal — 一个基于 Apache Guacamole 的企业 RemoteApp 门户。通过 Encrypted JSON Auth 将 FastAPI 后端与 Guacamole 集成，用户在 Web 门户中点击应用卡片即可启动远程 Windows RemoteApp (RDP RAIL)。

## Architecture

```
Browser → Nginx (port 80) → ┬─ FastAPI (port 8000): Portal API + 静态前端
                             ├─ Guacamole Web (port 8080): 远程桌面渲染
                             └─ /internal-drive/: X-Accel 文件下载
                                    ↓
                               guacd ←→ RDP Server (Windows)
                                    ↓
                               MySQL 8.0 (两个 DB)
```

- **FastAPI 后端** (`backend/`): JWT 认证、应用管理、连接启动、文件管理、实时监控
- **Guacamole 1.6.0** (Docker): guacd (C 协议代理) + guac-web (Tomcat, AngularJS 前端)
- **Nginx**: 反向代理统一入口，WebSocket 升级，CSP 安全头，X-Accel-Redirect 零拷贝下载
- **MySQL 8.0**: `guacamole_db` (Guacamole 核心) + `guacamole_portal_db` (Portal 业务)

### 关键数据流: 启动 RemoteApp

1. 前端 POST `/api/remote-apps/launch/{app_id}` (JWT Bearer)
2. `router.py` ACL 校验 → `_build_all_connections()` 打包该用户所有可用连接
3. `guacamole_service.py` 复用/创建 Guacamole session (缓存 + 验证)
4. `guacamole_crypto.py` AES-128-CBC 加密 JSON payload → POST 到 Guacamole `/api/tokens`
5. 返回 `redirect_url`，前端在 `about:blank` 窗口中 iframe 打开

### 核心设计决策

- **Per-user token 复用**: Guacamole 用 localStorage 存 `GUAC_AUTH`，多标签共享。所有应用打包进同一 token，`_SessionCache` 双层缓存(内存+DB)避免多标签冲突。
- **Session 缓存失效**: admin 修改应用/ACL 后必须调用 `guac_service.invalidate_all_sessions()`。
- **Branding 扩展**: CSS+JS 注入屏蔽 Guacamole 侧边菜单 (Ctrl+Shift+Alt)，防止用户绕过 Portal。
- **Drive Redirection**: guacd 虚拟磁盘 per-user 隔离 (`/drive/portal_u{id}`)，非本地文件系统映射。

## Commands

### 本地开发 (宿主机)

```bash
# 启动依赖 (MySQL + Guacamole 三件套)
cd deploy && docker compose up -d guacd guac-sql guac-web

# 启动 FastAPI 后端
cd /path/to/gucamole_app
python backend/app.py
# 访问 http://localhost:8000

# 运行测试
python -m pytest tests/ -v
```

### Docker 全栈部署

```bash
cd deploy && docker compose up -d --build
# 访问 http://<PORTAL_HOST>:<PORTAL_PORT>
# 重置数据库: docker compose down -v && docker compose up -d --build
```

### 数据库迁移 (手动)

```bash
# 对已有环境执行增量迁移
docker exec -i nercar-portal-guac-sql mysql -uroot -p密码 --default-character-set=utf8mb4 < database/migrate_xxx.sql
```

## Project Structure

```
backend/
  app.py              # FastAPI 入口, lifespan 管理后台任务
  database.py         # 连接池 + CONFIG 加载 (环境变量覆盖 config.json)
  auth.py             # JWT 登录/验证, get_current_user/require_admin 依赖注入
  router.py           # 核心 API: 应用列表 + launch (构建连接 + 复用 session)
  guacamole_crypto.py # Encrypted JSON Auth 加密 (HMAC-SHA256 + AES-128-CBC)
  guacamole_service.py # Session 管理: _SessionCache 双层缓存 + token 验证
  admin_router.py     # 管理 API: CRUD 应用/用户/ACL/审计日志
  monitor.py          # 实时监控: 心跳/session-end/admin overview
  file_router.py      # 个人空间: 分片上传/断点续传/X-Accel 下载/配额
  audit.py            # 审计日志写入
  models.py           # Pydantic 模型

frontend/             # 纯静态 HTML/JS/CSS (无构建工具)
  index.html          # 应用门户主页
  login.html          # 登录页
  admin.html          # 管理后台 (5 Tab)
  viewer.html         # VTK.js 3D 查看器 (PoC)

config/config.json    # 主配置 (DB/API/Guacamole/Auth/Monitor/FileTransfer)
deploy/               # Docker 部署: compose + Dockerfile + Nginx + initdb
database/             # SQL: init.sql (全量) + migrate_*.sql (增量)
branding/             # Guacamole 品牌覆盖 (CSS/JS → JAR)
```

## Configuration

`config/config.json` 是主配置文件，敏感值通过环境变量覆盖:

| 环境变量 | 覆盖字段 | 用途 |
|----------|----------|------|
| `PORTAL_DB_HOST` / `PORTAL_DB_PORT` | database.host/port | DB 地址 (Docker: `guac-sql`/`3306`) |
| `PORTAL_DB_PASSWORD` | database.password | DB 密码 |
| `GUACAMOLE_JSON_SECRET_KEY` | guacamole.json_secret_key | 128-bit hex, 必须与 Guac 容器一致 |
| `GUACAMOLE_INTERNAL_URL` | guacamole.internal_url | 后端→Guacamole (Docker: `http://guac-web:8080/guacamole`) |
| `GUACAMOLE_EXTERNAL_URL` | guacamole.external_url | 浏览器→Guacamole (动态从 Request Host 构建) |
| `PORTAL_JWT_SECRET` | auth.jwt_secret | Portal JWT 签名密钥 |

## Database

两个数据库共存于同一 MySQL 实例:
- `guacamole_db`: Guacamole 核心 (由 guac-web 自动管理)
- `guacamole_portal_db`: Portal 业务表

Portal 核心表: `remote_app`, `remote_app_acl`, `portal_user`, `token_cache`, `active_session`, `audit_log`

新部署: `database/init.sql` + `deploy/initdb/01-portal-init.sql`
已有环境增量: `database/migrate_*.sql`

## Known Gotchas

- **BOM 致命**: Dockerfile/YAML/.env/nginx.conf/SQL 文件 **不能有 BOM**，否则 Docker/Nginx/MySQL 解析失败。仅 Python/HTML/JS/CSS 用 UTF-8-BOM。
- **BAN Extension**: Guacamole 1.6 默认启用暴力破解保护，Docker 反代下所有请求共享 IP，必须 `BAN_ENABLED=false`。
- **MySQL 执行 SQL 必须** `--default-character-set=utf8mb4`，否则中文双重编码成不可逆乱码。
- **Nginx X-Accel 中文路径**: Starlette Response header 用 Latin-1，中文路径需 URL encode 每段。
- **Guacamole 菜单**: CSS `display:none` 不够，必须 JS 定时重置 `menu.shown=false`，否则键盘输入被隐形菜单截获。
- **`disable-gfx: true`**: GUACAMOLE-2123 workaround，不加则 RemoteApp 窗口不更新。
- **Branding JAR 路径**: 用 Python `zipfile` 打包，PowerShell `Compress-Archive` 创建的 ZIP 用 `\` 路径导致 404。

## Auth Flow

1. `POST /api/auth/login` → bcrypt 验证 → JWT (含 user_id, username, is_admin, exp)
2. 所有 API 通过 `Depends(get_current_user)` 提取 JWT 用户信息
3. 管理 API 通过 `Depends(require_admin)` 额外校验 is_admin
4. 登录限流: 每 IP 每分钟 5 次 (滑动窗口, 内存实现)

## Seed Data

- admin/admin123 (管理员, 全部应用权限)
- test/test123 (普通用户, 仅记事本)
