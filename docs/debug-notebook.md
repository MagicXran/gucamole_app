# Guacamole RemoteApp 门户 — 调试错题本

> 本文档记录项目开发调试过程中遇到的所有问题、根因分析、解决方案及参考资料。
> 同时整理 Guacamole 核心原理知识点，从问题出发学习底层机制。
> **持续更新，每次调试新问题都追加到本文档。**

---

## 目录

- [一、Guacamole 核心架构知识](#一guacamole-核心架构知识)
- [二、问题记录](#二问题记录)
  - [BUG-001: localStorage 多标签 Token 冲突（核心 Bug）](#bug-001-localstorage-多标签-token-冲突核心-bug)
  - [BUG-002: GFX Pipeline 导致 RemoteApp 窗口不更新](#bug-002-gfx-pipeline-导致-remoteapp-窗口不更新)
  - [BUG-003: MySQL 无连接池导致并发性能差](#bug-003-mysql-无连接池导致并发性能差)
  - [BUG-004: Windows localhost 解析为 IPv6 导致连接超时](#bug-004-windows-localhost-解析为-ipv6-导致连接超时)
  - [BUG-005: Docker Compose initdb.sql 挂载路径错误](#bug-005-docker-compose-initdbsql-挂载路径错误)
  - [BUG-006: WebSocket 关闭时的 IllegalStateException](#bug-006-websocket-关闭时的-illegalstateexception)
  - [BUG-007: UI 和 URL 暴露 Guacamole 品牌标识](#bug-007-ui-和-url-暴露-guacamole-品牌标识)
  - [BUG-008: 容器重建后旧 Token 缓存导致登录页](#bug-008-容器重建后旧-token-缓存导致登录页)
  - [BUG-009: 两个 Docker Compose 文件创建重复容器组](#bug-009-两个-docker-compose-文件创建重复容器组)
  - [BUG-010: guac-sql 容器重建后 Portal 数据库丢失](#bug-010-guac-sql-容器重建后-portal-数据库丢失)
  - [BUG-011: Token 有效期与长时间使用（假问题分析）](#bug-011-token-有效期与长时间使用假问题分析)
  - [BUG-012: 页面刷新新建会话而非恢复](#bug-012-页面刷新新建会话而非恢复)
  - [BUG-013: URL 泄露 Guacamole 内部地址与 Token](#bug-013-url-泄露-guacamole-内部地址与-token)
  - [BUG-014: 后端重启导致旧标签被踢回登录页](#bug-014-后端重启导致旧标签被踢回登录页)
  - [BUG-015: about:blank iframe 中键盘输入失效](#bug-015-aboutblank-iframe-中键盘输入失效)
  - [BUG-016: RemoteApp 空闲 ~20 分钟后卡死无响应](#bug-016-remoteapp-空闲-20-分钟后卡死无响应)
  - [BUG-017: Admin 修改应用后 Launch 仍用旧参数（Session 缓存未失效）](#bug-017-admin-修改应用后-launch-仍用旧参数session-缓存未失效)
- [三、参考资料汇总](#三参考资料汇总)

---

## 一、Guacamole 核心架构知识

### 1.1 整体架构

```
┌─────────────┐     ┌──────────────────┐     ┌─────────┐     ┌──────────────┐
│   浏览器     │────▶│  guacamole-client │────▶│  guacd   │────▶│ RDP/VNC/SSH  │
│  (Angular)   │ WS  │  (Tomcat/Java)   │ TCP │ (C守护)  │     │  目标服务器   │
└─────────────┘     └──────────────────┘     └─────────┘     └──────────────┘
```

**三层架构：**

| 组件 | 角色 | 技术栈 |
|------|------|--------|
| **guacamole-client** | Web 前端 + REST API + 认证 | Java (Tomcat)、Angular 前端 |
| **guacd** | 协议代理守护进程 | C 语言，内置 FreeRDP/libssh/libvnc |
| **Guacamole Protocol** | 客户端与 guacd 之间的通信协议 | 自定义文本协议，通过 WebSocket 传输 |

**关键数据流：**

1. 浏览器通过 **WebSocket** 连接到 guacamole-client
2. guacamole-client 通过 **TCP:4822** 连接到 guacd
3. guacd 使用 **FreeRDP** 发起 RDP 连接到目标 Windows 服务器
4. 屏幕画面通过 Guacamole Protocol 编码为图片指令回传浏览器
5. 浏览器端 Canvas 渲染画面，键鼠事件反向传输

> 📖 参考: [Guacamole Architecture](https://guacamole.apache.org/doc/gug/guacamole-architecture.html)

### 1.2 Encrypted JSON Authentication（加密 JSON 认证）

我们项目使用的认证方式。核心流程：

```
FastAPI 后端                    Guacamole
    │                              │
    │  1. 构建 JSON payload        │
    │     (用户名+连接参数+过期时间)  │
    │                              │
    │  2. HMAC-SHA256 签名          │
    │     AES-128-CBC 加密          │
    │                              │
    │  3. POST /api/tokens         │
    │     data=<加密数据>           │
    │──────────────────────────────▶│
    │                              │  4. 解密验证
    │  5. 返回 authToken            │     创建临时用户和连接
    │◀──────────────────────────────│
    │                              │
    │  6. 拼接 URL:                 │
    │     /#/client/<id>?token=xxx │
    │                              │
```

**加密细节：**
- 密钥：128-bit hex string（如 `4c0b569e4c96df157eee1b65dd0e4d41`）
- 签名：HMAC-SHA256(secret_key, json_payload)
- 加密：AES-128-CBC(secret_key, IV=签名前16字节, json_payload)
- 编码：base64(IV + 密文)

**JSON Payload 结构：**
```json
{
  "username": "portal_u1",
  "expires": "1709330000000",
  "connections": {
    "app_1": {
      "protocol": "rdp",
      "parameters": {
        "hostname": "192.168.1.8",
        "port": "3389",
        "username": "admin",
        "password": "password",
        "remote-app": "||notepad",
        "disable-gfx": "true"
      }
    }
  }
}
```

> 📖 参考: [JSON Authentication](https://guacamole.apache.org/doc/gug/json-auth.html)

### 1.3 GUAC_AUTH_TOKEN 与 localStorage

Guacamole 前端将 `authToken` 存储在浏览器的 **localStorage** 中（key: `GUAC_AUTH`），而非 sessionStorage。

**关键影响：**
- localStorage 在同源（same-origin）所有标签页之间共享
- 新标签获取新 token 会覆盖 localStorage 中的旧 token
- 旧标签的 token 失效 → 被踢回登录页

这是 [BUG-001](#bug-001-localstorage-多标签-token-冲突核心-bug) 的根本原因。

### 1.4 RemoteApp (RAIL) 机制

RemoteApp 使用 RDP 的 **RAIL（Remote Application Integrated Locally）** 扩展协议：

- 不显示完整远程桌面，只显示单个应用窗口
- RDP 参数中通过 `remote-app` 指定应用（如 `||notepad`）
- `||` 前缀表示应用别名（注册在 Windows RemoteApp 列表中）
- guacd 内部使用 **FreeRDP** 的 RAIL 通道实现

**FreeRDP 版本兼容性：**
- FreeRDP 2.x：RAIL 正常工作
- FreeRDP 3.x：已知存在 RAIL 兼容性问题（Guacamole 1.6.0 官方镜像使用 2.11.7）

> 📖 参考: [FreeRDP RemoteApp Wiki](https://github.com/FreeRDP/FreeRDP/wiki/RemoteApp)
> 📖 参考: [MS-RDPERP Protocol Spec](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdperp/3aa1de2c-6353-4cc8-b33a-8907ca386c67)

### 1.5 Docker 镜像 entrypoint 机制

guacamole/guacamole Docker 镜像的启动流程：

```
/opt/guacamole/bin/entrypoint.sh
  ├── 000-migrate-docker-links.sh    # 兼容旧版 Docker link
  ├── 010-migrate-legacy-variables.sh # 环境变量迁移
  ├── 100-generate-guacamole-home.sh  # 创建临时 GUACAMOLE_HOME
  ├── 500-generate-tomcat-catalina-base.sh # 部署 WAR
  ├── 700-configure-features.sh       # 启用扩展
  └── 999-start-tomcat.sh             # 启动 Tomcat
```

**关键脚本逻辑：**

`100-generate-guacamole-home.sh`：
- 将 `$GUACAMOLE_HOME`（默认 `/etc/guacamole`）作为模板
- 创建 `/tmp/guacamole-home.XXXXXXXXXX` 临时目录
- 将模板中的 extensions/ 和 lib/ 下文件 **symlink** 到临时目录
- 复制 `guacamole.properties` 到临时目录

`500-generate-tomcat-catalina-base.sh`：
```bash
ln -sf /opt/guacamole/webapp/guacamole.war \
  $CATALINA_BASE/webapps/${WEBAPP_CONTEXT:-guacamole}.war
```
- `WEBAPP_CONTEXT` 环境变量控制 Tomcat context path
- 设为 `ROOT` → 部署为根路径（`/`）
- 不设 → 默认 `guacamole`（`/guacamole/`）

> 📖 参考: [100-generate-guacamole-home.sh](https://github.com/apache/guacamole-client/blob/main/guacamole-docker/entrypoint.d/100-generate-guacamole-home.sh)
> 📖 参考: [500-generate-tomcat-catalina-base.sh](https://github.com/apache/guacamole-client/blob/main/guacamole-docker/entrypoint.d/500-generate-tomcat-catalina-base.sh)

### 1.6 Branding Extension 机制

Guacamole 支持通过扩展覆盖翻译和样式，无需修改 WAR 包：

**扩展 JAR 结构：**
```
portal-branding.jar
├── guac-manifest.json        # 扩展清单
└── translations/
    ├── en.json               # 英文翻译覆盖
    └── zh.json               # 中文翻译覆盖
```

**翻译覆盖机制：**
- 只需提供要修改的 key，其余保持原样（merge/overlay）
- 支持覆盖 CSS、图片、HTML 模板
- 部署到 `$GUACAMOLE_HOME/extensions/` 目录
- Docker 中通过 volume 挂载到 `/etc/guacamole/extensions/`

> 📖 参考: [guacamole-ext](https://guacamole.apache.org/doc/gug/guacamole-ext.html)
> 📖 参考: [Branding Example](https://github.com/apache/guacamole-client/tree/main/doc/guacamole-branding-example)

---

## 二、问题记录

---

### BUG-001: localStorage 多标签 Token 冲突（核心 Bug）

**严重等级：** 🔴 致命

**现象：**
用户打开第一个 RemoteApp（如记事本），正常工作。打开第二个 RemoteApp（如计算器）后，第一个标签被踢回 Guacamole 登录页。

**根因分析：**

Guacamole 前端将 `GUAC_AUTH` token 存储在 `localStorage` 中。localStorage 在同源所有标签页之间共享。

```
标签1: 获取 token_A → localStorage["GUAC_AUTH"] = token_A → 正常连接
标签2: 获取 token_B → localStorage["GUAC_AUTH"] = token_B → 覆盖 token_A
标签1: 心跳/API调用 → 使用 localStorage 中的 token_B → 但 token_B 对应不同的 session
       → 服务端: session 不匹配 → 踢回登录页
```

初始设计中，每次 launch 都创建新 token（包含 UUID 的唯一连接名），导致每个标签有不同的 token。

**解决方案：Per-user Token 复用 + All-connections-in-one-token**

1. **`_SessionCache` 类**（`guacamole_service.py`）：线程安全的 per-user authToken 缓存
   - 同一用户所有 launch 请求复用同一个 token
   - TTL = `token_expire_minutes * 60 - 60` 秒（提前 1 分钟过期）

2. **`_build_all_connections()`**（`router.py`）：将用户所有可用应用打包到同一个 token
   - 确保一个 token 覆盖用户的所有应用
   - 新标签不需要新 token，共用现有 session

3. **稳定命名**：连接名 `app_{id}`、用户名 `portal_u{user_id}`（无 UUID）
   - 保证 token 内容可复用

**修改文件：**
- `backend/guacamole_service.py` — 新增 `_SessionCache` 类
- `backend/router.py` — 新增 `_build_all_connections()`，重写 launch 逻辑

**验证结果：**
- 打开记事本 → 打开计算器 → 记事本标签保持连接（截图确认文字 `1111` 仍在）
- 两个标签使用同一个 token

**参考：**
- [MDN: Window.localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)
- [Guacamole JSON Auth](https://guacamole.apache.org/doc/gug/json-auth.html)

---

### BUG-002: GFX Pipeline 导致 RemoteApp 窗口不更新

**严重等级：** 🟡 中等

**现象：**
RemoteApp 窗口打开后，部分区域不更新或显示异常。窗口拖动、输入文字时画面撕裂或冻结。

**根因分析：**

RDP 的 GFX Pipeline（Graphics Pipeline Extension）与 RAIL（RemoteApp）模式存在兼容性问题。GFX Pipeline 使用 surface-based 渲染，与 RAIL 的窗口级渲染模型冲突。

这是 Guacamole 的已知 Bug：**GUACAMOLE-2123**。

**解决方案：**

在 RDP 连接参数中禁用 GFX Pipeline：

```python
params = {
    "disable-gfx": "true",           # 禁用 GFX Pipeline
    "resize-method": "display-update", # 使用 display-update 替代 reconnect
}
```

**修改文件：**
- `backend/guacamole_crypto.py` — `build_rdp_connection()` 增加两个参数

**参考：**
- [GUACAMOLE-2123: Remote App Windows not updated with GFX Pipeline](https://issues.apache.org/jira/browse/GUACAMOLE-2123)
- [Guacamole RDP Parameters](https://guacamole.apache.org/doc/gug/configuring-guacamole.html)

---

### BUG-003: MySQL 无连接池导致并发性能差

**严重等级：** 🟡 中等

**现象：**
多用户并发请求时响应变慢，每次请求都重新建立 MySQL 连接。

**根因分析：**

原始 `Database` 类每次 `execute_query` 都创建新连接，用完关闭。TCP 三次握手 + MySQL 认证握手在每次请求中重复执行。

**解决方案：**

引入 MySQL 连接池：

```python
from mysql.connector import pooling

self._pool = pooling.MySQLConnectionPool(
    pool_name="portal_pool",
    pool_size=8,
    pool_reset_session=True,
    # ... 连接参数
)
```

**修改文件：**
- `backend/database.py` — 使用 `MySQLConnectionPool` 替代单次连接

**验证结果：**
- 10 并发请求在 1.22 秒内完成

---

### BUG-004: Windows localhost 解析为 IPv6 导致连接超时

**严重等级：** 🟡 中等

**现象：**
后端启动时连接数据库超时或拒绝连接。MySQL 端口 33060 在 Docker 容器中绑定到 `127.0.0.1:33060`。

**根因分析：**

Windows 11 的 `localhost` 解析优先使用 IPv6 `::1`，而 Docker 端口映射的 `127.0.0.1:33060` 只监听 IPv4。

```
Python: connect("localhost", 33060)
  → DNS: localhost → ::1 (IPv6 优先)
  → TCP: connect(::1, 33060) → 无人监听 → 超时
```

**解决方案：**

`config/config.json` 中将 `host` 从 `"localhost"` 改为 `"127.0.0.1"`：

```json
{
  "database": {
    "host": "127.0.0.1",
    "port": 33060
  }
}
```

**教训：**
在 Windows 环境中，涉及网络连接时始终使用 `127.0.0.1` 而非 `localhost`，除非确认 IPv6 也有对应的监听。

---

### BUG-005: Docker Compose initdb.sql 挂载路径错误

**严重等级：** 🟡 中等

**现象：**
数据库初始化脚本未执行，`guacamole_portal_db` 数据库不存在。

**根因分析：**

项目 `docker-compose.yml` 中 volume 路径写成了 `./initdb.sql`，但实际文件在 `./database/init.sql`。

**解决方案：**

```yaml
volumes:
  - ./database/init.sql:/docker-entrypoint-initdb.d/initdb.sql
```

**注意：** MySQL 的 `docker-entrypoint-initdb.d` 只在**首次初始化**（data 目录为空）时执行。如果数据已存在，需要手动执行 SQL：

```bash
docker exec -i guac-sql mysql -uroot -pxran < database/init.sql
```

---

### BUG-006: WebSocket 关闭时的 IllegalStateException

**严重等级：** 🟢 无害（日志噪音）

**现象：**
用户刷新或关闭 RemoteApp 标签页时，Guacamole 容器日志输出：
```
Exception in thread "Thread-56" java.lang.IllegalStateException:
  Message will not be sent because the WebSocket session has been closed
    at org.apache.tomcat.websocket.WsRemoteEndpointImplBase.writeMessagePart(...)
    at org.apache.guacamole.websocket.GuacamoleWebSocketTunnelEndpoint.sendInstruction(...)
```

**根因分析：**

经典的竞态条件（race condition）：

```
读线程                        WebSocket 事件
  │                              │
  │  从 guacd 读取指令            │
  │  准备调用 sendText()          │
  │                              │  用户关闭标签
  │                              │  onClose() 被调用
  │                              │  session.close()
  │  sendText() → session 已关闭  │
  │  → IllegalStateException     │
```

`GuacamoleWebSocketTunnelEndpoint.sendInstruction()` 没有 `session.isOpen()` 检查，也没有 try-catch 捕获 `IllegalStateException`。

这是 Guacamole 的已知问题 **GUACAMOLE-1015**（至今未修复），但**不影响功能**。

**官方说法：**
> "Normally, this error does not indicate a problem, but rather that the client has simply closed the connection." — [Guacamole Troubleshooting](https://guacamole.apache.org/doc/gug/troubleshooting.html)

**处理方式：** 可安全忽略。如需抑制日志，可通过 `logback.xml` 配置：

```xml
<logger name="org.apache.tomcat.websocket" level="OFF" />
```

**参考：**
- [GUACAMOLE-1015: Tunnel and WebSocket states out of sync](https://issues.apache.org/jira/browse/GUACAMOLE-1015)
- [GUACAMOLE-67: I/O error in WebSocket can cause connection tracking to fail](https://issues.apache.org/jira/browse/GUACAMOLE-67)
- [Guacamole Troubleshooting](https://guacamole.apache.org/doc/gug/troubleshooting.html)

---

### BUG-007: UI 和 URL 暴露 Guacamole 品牌标识

**严重等级：** 🟢 低（产品化需求）

**现象：**

1. **加载页面**：显示 "已连接到 Guacamole。正在等待应答..."
2. **浏览器标签标题**：显示 "Apache Guacamole"
3. **URL 路径**：`http://localhost:8080/guacamole/#/client/...`

**根因分析：**

- UI 文字来自前端 i18n 翻译文件 `translations/zh.json` 中的 `CLIENT.TEXT_CLIENT_STATUS_WAITING` 等 key
- URL 中的 `/guacamole/` 是 Tomcat WAR 包的 context path（WAR 文件名 = context path）

**解决方案：**

**问题 1+2：Branding Extension**

创建扩展 JAR 覆盖翻译 key：

```json
// branding/translations/zh.json
{
  "APP": { "NAME": "远程应用平台" },
  "CLIENT": {
    "TEXT_CLIENT_STATUS_CONNECTING": "正在连接服务器...",
    "TEXT_CLIENT_STATUS_WAITING": "已连接服务器，正在等待应答...",
    "TEXT_CLIENT_STATUS_UNSTABLE": "网络连接似乎不稳定。"
  }
}
```

打包为 JAR，通过 Docker volume 挂载到 `/etc/guacamole/extensions/`。

**问题 3：WEBAPP_CONTEXT 环境变量**

```yaml
# docker-compose.yml
environment:
  WEBAPP_CONTEXT: "ROOT"   # WAR 部署为 ROOT.war → context path = /
```

URL 变为：`http://localhost:8080/#/client/...`

**修改文件：**
- 新增 `branding/` 目录（guac-manifest.json + translations）
- `docker-compose.yml` — 增加 volume 挂载 + WEBAPP_CONTEXT
- `config/config.json` — URL 去掉 `/guacamole` 后缀

**参考：**
- [guacamole-ext 文档](https://guacamole.apache.org/doc/gug/guacamole-ext.html)
- [Branding Example](https://github.com/apache/guacamole-client/tree/main/doc/guacamole-branding-example)
- [500-generate-tomcat-catalina-base.sh](https://github.com/apache/guacamole-client/blob/main/guacamole-docker/entrypoint.d/500-generate-tomcat-catalina-base.sh)
- [Tomcat Context Path](https://tomcat.apache.org/tomcat-9.0-doc/config/context.html)

---

### BUG-008: 容器重建后旧 Token 缓存导致登录页

**严重等级：** 🟡 中等

**现象：**
修改 docker-compose 后重建容器（`docker compose up -d`），点击卡片跳转到 Guacamole 登录页而非 RemoteApp。

**根因分析：**

```
容器重建前:
  Guacamole 内存: token_A → session 有效
  后端 _SessionCache: user → token_A (缓存)

容器重建后:
  Guacamole 内存: 空（重启清空）
  后端 _SessionCache: user → token_A (旧缓存仍在！)

用户点击卡片:
  后端: 缓存命中 → 返回 token_A
  浏览器: 带 token_A 访问 Guacamole
  Guacamole: token_A 不存在 → 跳登录页
```

后端 `_SessionCache` 的 TTL 是 29 分钟，容器重建后缓存还没过期。

**解决方案：**

重启后端清空缓存。正常运维流程中：
1. 如果只改 Guacamole 容器配置 → 重建容器后也要重启后端
2. 或者在后端增加健康检查机制（验证缓存的 token 是否仍有效）

**未来改进方向（TODO）：**
- 在 `launch_connection` 中捕获 Guacamole 返回的认证错误
- 自动清除失效的缓存条目并重试

---

### BUG-009: 两个 Docker Compose 文件创建重复容器组

**严重等级：** 🔴 致命（端口冲突）

**现象：**
同时存在两组容器：
- `xran` 组：guacd, guac-sql, guac_web（来自 WSL `/home/xran/docker-compose.yml`）
- `gucamole_app` 组：guacd_app, guac-sql_app, guac_web_app（来自项目目录 `docker-compose.yml`）

两组都要绑定 `8080:8080` 和 `33060:3306`，互相抢端口，谁也启动不了。

**根因分析：**

项目目录 `D:\Nercar\NanGang\PSD\Apps\gucamole_app\` 下有自己的 `docker-compose.yml`（container_name 带 `_app` 后缀），误在该目录执行了 `docker compose up -d`，Docker Compose 用目录名 `gucamole_app` 作为项目名创建了第二组容器。

**解决方案：**

```bash
# 1. 删除意外创建的容器
docker rm guac_web_app guacd_app guac-sql_app

# 2. 统一使用 WSL 的 compose 文件
docker compose -f /home/xran/docker-compose.yml up -d
```

**教训：**
- 项目中的 `docker-compose.yml` 仅作为**配置参考/版本管理**，不直接用于启动容器
- 实际运行的 compose 文件统一在 WSL 的 `/home/xran/docker-compose.yml`
- 两个文件的 `container_name` 不同是一个保护机制（防止意外覆盖）

---

### BUG-010: guac-sql 容器重建后 Portal 数据库丢失

**严重等级：** 🟡 中等

**现象：**
后端启动报错 `Unknown database 'guacamole_portal_db'`。

**根因分析：**

`docker compose up -d` 触发了 guac-sql 容器重建。虽然 MySQL 数据目录通过 volume 挂载持久化（`/home/xran/data:/var/lib/mysql`），但 `guacamole_portal_db` 是**运行时手动创建的**（通过 `docker exec` 执行 SQL），不在 docker-entrypoint-initdb.d 的自动初始化范围内。

MySQL 的 `docker-entrypoint-initdb.d` **只在数据目录为空时执行**。数据目录已有 `guacamole_db`，所以 init.sql 不会再次运行。

**解决方案：**

手动重新执行初始化脚本：

```bash
docker exec -i guac-sql mysql -uroot -pxran < database/init.sql
```

脚本使用 `CREATE DATABASE IF NOT EXISTS` 和 `CREATE TABLE IF NOT EXISTS`，可安全重复执行。

**未来改进方向（TODO）：**
- 将 `guacamole_portal_db` 的创建也放入 docker-entrypoint-initdb.d
- 或使用单独的 MySQL 实例/卷管理 portal 数据库

---

### BUG-011: Token 有效期与长时间使用（假问题分析）

**严重等级：** 🟢 无影响（假问题）

**现象（担忧）：**
用户长时间使用 RemoteApp（如超过 30 分钟的 `token_expire_minutes`），token 过期后会话是否会被中断？

**根因分析：**

这个担忧基于对 Guacamole 认证机制的误解。系统中存在**三层独立的超时机制**，它们各司其职：

| 层级 | 机制 | 当前值 | 控制什么 |
|------|------|--------|---------|
| 1 | JSON payload 的 `expires` 字段 | now + 30min | 加密数据是否还能用于**新的认证请求** |
| 2 | Guacamole 的 `api-session-timeout` | 60min（默认） | authToken 在**无活动**时多久失效 |
| 3 | guacd tunnel 的 `receiveTimeout` | 15s | 通信级别超时（0 字节流动时） |

**关键事实：**

1. **`expires` 只在 token 交换时有意义**：一旦 Guacamole 接受了加密 JSON 并返回了 `authToken`，`expires` 字段就再也不起作用了。它不会终止已建立的连接。

2. **Keep-alive 机制**：Guacamole 的 JavaScript 客户端每 **5 秒**发送一次 `nop`（no-operation）消息到 guacd，guacd 回复 `sync` ping。这意味着：
   - 层级 3 的 15 秒 `receiveTimeout` 永远不会在正常连接中触发
   - 层级 2 的 `api-session-timeout` 把「连接着远程桌面」视为活动状态，60 分钟超时不断被重置

3. **实测验证**：有用户在社区报告连续运行 **11 天**不中断。

```
Guacamole JS Client (guacamole-common-js):
  pingInterval = setInterval(() => tunnel.sendMessage("nop"), 5000);

  ↕ 每 5 秒 nop/sync 保活 ↕

guacd (C daemon):
  收到 nop → 回复 sync → 重置所有超时计数器
```

**结论：**

✅ **活跃连接不受 `expires` 和 `api-session-timeout` 影响**，会无限续命直到用户主动断开。

~~唯一的边界场景：用户连接超过 29 分钟后 `_SessionCache` 过期，此时开第二个标签会生成新 TOKEN_B 覆盖 localStorage 中的 TOKEN_A。但已建立的 WebSocket 隧道不依赖 localStorage（只有初始连接时从 URL 读取 token），所以旧标签的连接不会受影响。~~

**⚠️ 勘误（BUG-014 补充）：** 上述"旧标签不受影响"的结论**不完全准确**。虽然 WebSocket 隧道本身不依赖 localStorage，但 Guacamole 的 Angular 客户端会监听浏览器 `storage` 事件。当 `GUAC_AUTH` 被新 token 覆盖时，旧标签检测到变化后触发重认证逻辑，导致被踢回登录页。此问题已在 [BUG-014](#bug-014-后端重启导致旧标签被踢回登录页) 中通过数据库持久化缓存彻底解决。

**处理方式：** Token 过期本身不影响活跃连接（结论正确）。localStorage 覆盖问题通过 BUG-014 的双层缓存解决。

**参考：**
- [Guacamole JSON Auth - expires 字段](https://guacamole.apache.org/doc/gug/json-auth.html)
- [Guacamole Client.js - nop keep-alive](https://github.com/apache/guacamole-client/blob/main/guacamole-common-js/src/main/webapp/modules/Client.js)
- [Guacamole Configuring - api-session-timeout](https://guacamole.apache.org/doc/gug/configuring-guacamole.html)
- [Mailing List: RDP idle timeout discussion](https://www.mail-archive.com/user@guacamole.apache.org/msg07792.html)

---

### BUG-012: 页面刷新新建会话而非恢复

**严重等级：** 🟡 中等（需要 Windows 配置配合）

**现象：**
在 RemoteApp 标签页中运行着一个应用，手动刷新页面（F5）后，看到的是新启动的应用而非之前未完成的会话。

**根因分析：**

页面刷新时发生的事件链：

```
F5
 → 浏览器销毁 JavaScript 上下文
 → WebSocket 连接关闭
 → guacd 日志: "Last user of connection '$uuid' disconnected"
 → guacd 日志: "Connection '$uuid' removed"
 → guacd 隧道彻底死亡（不可恢复）
```

guacd 隧道是 **ephemeral（短暂的）** 的 —— 这是 Guacamole 的设计决定。当最后一个用户从 guacd 连接断开时，guacd 立即移除该连接。**你不可能"恢复"一个死掉的 WebSocket 隧道。**

但问题的本质不在 guacd，在于 **RDP 会话是否在 Windows Server 端存活**：

| 组件 | 刷新后状态 |
|------|-----------|
| guacd 隧道 | **死亡**（不可恢复） |
| Guacamole authToken | 存活（localStorage 持久化，且在 `api-session-timeout` 内有效） |
| Windows RDP 会话 | **取决于 Windows 配置** — 可以保持「Disconnected」状态 |

**刷新后的重连流程：**

```
F5 → 页面重新加载
   → Guacamole Angular app 读取 localStorage 中的 GUAC_AUTH
   → 如果 authToken 有效 → 自动建立新 guacd 隧道
   → 新 guacd 隧道 → 新 RDP 连接（相同凭据）
   → Windows RDP Server 决定：
     ├── 如果有同用户的 Disconnected 会话 → 恢复旧会话（应用继续运行）
     └── 如果无 → 创建新会话（应用重新启动）
```

**对于 RemoteApp (RAIL) 的特殊性：**
- RemoteApp 不启动完整桌面，而是启动单个应用窗口
- RDP 会话断开后，应用在服务端仍可能在运行
- 重新连接时 RAIL 协议会尝试恢复窗口，但比桌面模式更脆弱

**解决方案：**

这需要**两端配合**，但代码端不需要改动。

**Windows Server 端（必须做）：**

配置 RDP 会话超时策略（通过组策略 `gpedit.msc` 或 `tsconfig.msc`）：

```
计算机配置 → 管理模板 → Windows 组件 → 远程桌面服务 → 远程桌面会话主机 → 会话时间限制

- "设置已中断会话的时间限制" → 已启用 → "从不" 或合理值（如 30 分钟）
- "达到时间限制时终止会话" → 已禁用
```

或通过 PowerShell：
```powershell
# 查看当前设置
(Get-WmiObject -Class Win32_TerminalServiceSetting -Namespace root\cimv2\TerminalServices).GetStringProperty("DisconnectedSessionLimit")

# 设置断开会话保持时间（毫秒，0 = 永不超时）
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" -Name "MaxDisconnectionTime" -Value 0
```

**Portal 代码端（已满足条件）：**
- ✅ 用户名一致：`portal_u{user_id}`（稳定命名，无 UUID）
- ✅ RDP 凭据一致：每个 app 从数据库读取固定凭据
- ✅ authToken 在 localStorage 中持久化

**注意：** 此方案依赖 about:blank + iframe 的改动（BUG-013）。刷新 `about:blank` 页面时，iframe 会重新加载 Guacamole 客户端，触发上述重连流程。

**局限性：**
- RemoteApp 重连质量完全取决于 Windows RDP 配置和 RAIL 协议的健壮性
- 某些应用可能不支持 RAIL 会话恢复（需逐个应用测试）
- guacd 隧道不可能跨刷新存活 —— 这是架构层面的限制，不是 bug

**参考：**
- [SourceForge: Guacamole reconnect discussion](https://sourceforge.net/p/guacamole/discussion/1110834/thread/6341b248/)
- [Guacamole Protocol - Connection ID and session sharing](https://guacamole.apache.org/doc/gug/guacamole-protocol.html)
- [Microsoft: RDP Session Timeout Settings](https://learn.microsoft.com/en-us/windows-server/remote/remote-desktop-services/clients/rdp-files)
- [guacamole-common-js: Client.js](https://guacamole.apache.org/doc/guacamole-common-js/Guacamole.Client.html)
- [guacamole-common-js: Tunnel.js](https://guacamole.apache.org/doc/guacamole-common-js/Guacamole.Tunnel.html)

---

### BUG-013: URL 泄露 Guacamole 内部地址与 Token

**严重等级：** 🔴 高（安全问题）

**现象：**
用户点击 RemoteApp 卡片后，新标签页地址栏显示完整的 Guacamole URL：

```
http://localhost:8080/#/client/YXBwXzEAYwBqc29u?token=ABC123DEF456...
```

暴露了：
- Guacamole 服务地址（`localhost:8080`）
- authToken（敏感凭据，可用于直接访问 Guacamole API）
- 连接编码（base64 可解码获取连接名 `app_1\x00c\x00json`）

用户可以复制此 URL 转发给他人，或绕过 Portal 系统直接访问 Guacamole。

**根因分析：**

原代码直接使用 `window.open(data.redirect_url, '_blank')`，将完整 URL 暴露在地址栏：

```javascript
// 原始代码
window.open(data.redirect_url, '_blank');
// 地址栏: http://localhost:8080/#/client/YXBwXzEAYwBqc29u?token=ABC123...
```

现代浏览器不允许隐藏地址栏（`location=no` 被 Chrome/Firefox 忽略），因此无法通过 `window.open` 的 features 参数解决。

**解决方案：about:blank + iframe**

利用 `window.open('about:blank')` 创建空白页面，然后通过 `document.write()` 注入全屏 iframe 加载 Guacamole 客户端：

```javascript
// 新代码（简化版）
var win = window.open('about:blank', '_blank');  // 地址栏: about:blank
win.document.write(
    '<iframe src="' + data.redirect_url + '" ' +
    'style="width:100vw;height:100vh;border:none"></iframe>'
);
win.document.close();
```

**实现细节：**

1. **同步打开窗口**：`window.open('about:blank')` 必须在 click 事件的同步调用栈中执行，否则被弹窗拦截器阻止。先打开窗口，再异步获取 redirect_url。

2. **加载状态**：窗口打开后立即写入 loading 页面（深色背景 + spinner），API 响应后替换为 iframe。

3. **错误处理**：如果 API 调用失败，在已打开的窗口中显示错误信息，不在 Portal 页面弹错。

4. **跨域 iframe**：Portal（`localhost:8000`）和 Guacamole（`localhost:8080`）不同端口 = 不同 origin。但 Guacamole 的 Canvas 渲染和 WebSocket 不需要跨 frame DOM 访问，功能不受影响。

**修改文件：**
- `frontend/js/app.js` — 重写 `launchApp()` 函数

**安全评估：**

| 维度 | 效果 |
|------|------|
| 地址栏 | 显示 `about:blank` ✅ |
| 浏览器历史 | 不记录 Guacamole URL ✅ |
| URL 复制/分享 | 无法获取内部地址 ✅ |
| 书签 | 收藏 `about:blank` 无意义 ✅ |
| DevTools Network | 仍可看到 iframe 请求 ⚠️（防君子不防小人） |

**注意事项：**
- Guacamole 默认不设置 `X-Frame-Options` 或 CSP `frame-ancestors`，因此 iframe 嵌入可以工作
- 如果未来 Guacamole 或反向代理配置了 frame 限制，需要添加例外
- 某些全局快捷键（如 Ctrl+W）不会被 iframe 内的 Guacamole 拦截，这实际上是好事

**参考：**
- [MDN: Window.open()](https://developer.mozilla.org/en-US/docs/Web/API/Window/open)
- [MDN: Same-origin policy](https://developer.mozilla.org/en-US/docs/Web/Security/Same-origin_policy)
- [WHATWG: about:blank semantics (Issue #546)](https://github.com/whatwg/html/issues/546)

---

### BUG-014: 后端重启导致旧标签被踢回登录页

**严重等级：** 🔴 高（影响用户体验 + 暴露架构缺陷）

**现象：**
1. 用户打开 RemoteApp Tab A，正常使用
2. 重启 FastAPI 后端进程
3. 用户打开 RemoteApp Tab B
4. Tab A 的 RemoteApp 被踢回 Guacamole 登录页

**根因分析：**

事件链精确重建：

```
Tab A 打开:
  后端: _SessionCache[portal_u1] = TOKEN_A (内存 dict)
  Guacamole: session map 有 TOKEN_A
  iframe localStorage: GUAC_AUTH = TOKEN_A

后端重启:
  _SessionCache = {} (内存 dict 被清空)
  Guacamole: TOKEN_A 仍有效 (容器没重启)

Tab B 打开:
  后端: _cache.get("portal_u1") → None (缓存空了)
  后端: _create_session() → POST /api/tokens → TOKEN_B
  后端: _cache.put("portal_u1", TOKEN_B)
  Tab B iframe: localStorage["GUAC_AUTH"] = TOKEN_B ← 覆盖了 TOKEN_A

Tab A 的 Guacamole Angular 客户端:
  浏览器 storage 事件 → 检测到 GUAC_AUTH 变化
  → 尝试用 TOKEN_B 重认证
  → TOKEN_B 对应不同的 Guacamole session
  → Tab A 的连接在 TOKEN_A 的 session 下
  → session 不匹配 → 踢回登录页
```

**本质问题：** `_SessionCache` 是纯内存 dict，后端重启即丢失。丢失后被迫创建新 token，新 token 覆盖 localStorage，Guacamole Angular 客户端的 `storage` 事件监听器触发重认证，旧标签被踢。

**⚠️ 对 BUG-011 的修正：** BUG-011 中"已建立的 WebSocket 隧道不依赖 localStorage，旧标签不受影响"的结论**不完全准确**。虽然 WebSocket 隧道自身不重新读取 localStorage，但 Guacamole 的 Angular 客户端会通过浏览器 `storage` 事件检测到 token 变化并触发重认证逻辑。

**同时修复了 BUG-008：** BUG-008（Guacamole 容器重建后缓存 token 无效）此前的解决方案是"重启后端清缓存"。新方案通过 Guacamole API 验证自动检测失效 token，彻底解决了该问题。

**解决方案：双层缓存（内存 + 数据库）+ Guacamole 验证**

将 `_SessionCache` 从纯内存 dict 升级为内存 + 数据库双层缓存：

```
┌───────────────────────────────────────────────────────────┐
│ launch_connection() 三级回退策略                            │
│                                                           │
│  1. 内存缓存命中 → 直接复用 (零额外开销，和改动前一样快)       │
│     ↓ miss                                                │
│  2. 数据库缓存命中 → GET /api/session/data 验证             │
│     ├── 有效 → promote 到内存，复用 (避免产生新 token)       │
│     └── 无效 → invalidate，走第 3 步                       │
│     ↓ miss                                                │
│  3. 创建新 session → 写入内存 + 数据库                      │
└───────────────────────────────────────────────────────────┘
```

**关键设计：**

1. **内存缓存（快速路径）**：`threading.Lock` + dict，和改动前完全一样
2. **数据库缓存（持久层）**：新增 `token_cache` 表，`REPLACE INTO` 原子写入
3. **Guacamole API 验证**：`GET /api/session/data?token=xxx`，返回 200 则有效
4. **优雅降级**：所有 DB 操作用 try-except 包裹，DB 故障时退化为纯内存模式

**性能影响：**

| 场景 | 额外开销 |
|------|---------|
| 正常使用（内存命中） | 零 — 和改动前完全一致 |
| 后端重启后首次请求 | DB SELECT + HTTP GET 验证（~50-200ms，仅一次） |
| Guacamole 重启后首次请求 | DB SELECT + HTTP GET 验证失败 + 创建新 session |

**修改文件：**
- `database/init.sql` — 新增 `token_cache` 表
- `backend/database.py` — 新增 `execute_update()` 方法
- `backend/guacamole_service.py` — 重写 `_SessionCache`（双层缓存）+ 新增 `_validate_token()`
- `backend/router.py` — 传 `db` 参数给 `GuacamoleService`

**数据库表结构：**
```sql
CREATE TABLE IF NOT EXISTS token_cache (
    username    VARCHAR(64)  PRIMARY KEY    COMMENT 'Guacamole 用户名',
    auth_token  VARCHAR(256) NOT NULL       COMMENT 'Guacamole authToken',
    data_source VARCHAR(64)  DEFAULT 'json' COMMENT '数据源标识',
    created_at  DOUBLE       NOT NULL       COMMENT 'Unix timestamp (秒)'
);
```

**验证场景：**

| 场景 | 预期行为 |
|------|---------|
| 正常开多标签 | 内存缓存命中 → 复用 token → 不覆盖 localStorage ✅ |
| 后端重启 + 开新标签 | DB 缓存命中 → 验证有效 → 复用旧 token → 不覆盖 localStorage ✅ |
| Guacamole 重启 + 开新标签 | DB 缓存命中 → 验证失败 → 创建新 token（此时旧连接已死，可接受） ✅ |
| 两者都重启 | DB 缓存命中 → 验证失败 → 创建新 token ✅ |
| token_cache 表不存在 | DB 操作 try-except 吞异常 → 退化为纯内存模式 ✅ |

**部署注意：**
需要在 MySQL 中创建 `token_cache` 表。重新执行 init.sql 即可（使用 `CREATE TABLE IF NOT EXISTS`）：
```bash
docker exec -i guac-sql mysql -uroot -pxran < database/init.sql
```

**参考：**
- [BUG-001: localStorage 多标签冲突](#bug-001-localstorage-多标签-token-冲突核心-bug)（本 bug 的前置问题）
- [BUG-008: 容器重建后旧 Token 缓存](#bug-008-容器重建后旧-token-缓存导致登录页)（被本方案一并修复）
- [BUG-011: Token 有效期分析](#bug-011-token-有效期与长时间使用假问题分析)（勘误说明）
- [MDN: Window.storage event](https://developer.mozilla.org/en-US/docs/Web/API/Window/storage_event)

---

### BUG-015: about:blank iframe 中键盘输入失效

**严重等级：** 🔴 高（核心功能不可用）

**现象：**
BUG-013 引入 about:blank + iframe 方案后，打开 RemoteApp（如记事本），键盘输入完全无效。鼠标点击正常，但无法在远程应用中打字。

**根因分析：**

about:blank + iframe 的跨域焦点问题：

```
about:blank 页面 (origin: localhost:8000 — 继承自 opener)
  └── <iframe src="localhost:8080/#/client/...">  (origin: localhost:8080)
        └── Guacamole Angular App
              └── 隐藏 textarea (Keyboard.js 的 input sink)
```

当 about:blank 页面加载完成后，浏览器焦点停留在 **parent document** 上。虽然 iframe 占满全屏，看起来用户在和 iframe 交互，但：

1. 键盘事件在 parent document 上触发（parent 持有焦点）
2. iframe 内的 Guacamole Keyboard.js 监听的是 iframe 内部 document 的键盘事件
3. 跨域 iframe 无法从 parent 捕获键盘事件
4. **结果：键盘输入全部丢失**

鼠标不受影响，因为鼠标事件直接在点击位置触发（iframe 的渲染区域），不受 document-level 焦点影响。

**解决方案：iframe 焦点管理**

三层焦点转发策略，确保 iframe 获得并保持焦点：

```javascript
// 1. iframe 加载完成后自动获取焦点
<iframe id="guac" ... onload="this.focus()"></iframe>

// 2. 点击 parent body 时转发焦点到 iframe（防止意外焦点丢失）
document.body.addEventListener('click', function() {
    document.getElementById('guac').focus();
});

// 3. parent 捕获阶段的 keydown 事件转发焦点（最后防线）
document.addEventListener('keydown', function() {
    document.getElementById('guac').focus();
}, true);  // capture phase，优先级最高
```

同时修正了 CSS：`*{overflow:hidden}` 改为 `html,body{overflow:hidden}`，避免 `*` 选择器意外影响 iframe 的交互行为。

**为什么三层而不是一层：**

| 层级 | 作用 | 覆盖场景 |
|------|------|---------|
| `onload="this.focus()"` | iframe 加载完成时自动聚焦 | 初始加载 |
| `body.onclick → iframe.focus()` | 用户点击任何区域时重新聚焦 | 焦点意外丢失（如 Alt+Tab 回来） |
| `document.onkeydown → iframe.focus()` | 首个按键丢失但立即修正焦点 | 极端 edge case（第一个键丢失，后续正常） |

**原理：**
一旦 iframe 元素获得 DOM 焦点（`iframe.focus()`），浏览器自动将后续键盘事件路由到 iframe 内部的 document。Guacamole 的 Keyboard.js 在 iframe 内正常工作——它不关心自己是否在 iframe 中，只关心键盘事件是否在它的 document 上触发。

**修改文件：**
- `frontend/js/app.js` — iframe HTML 增加 `id="guac"`、`onload`、焦点转发脚本、CSS 修正

**验证结果：**
- Playwright 自动化测试：focus iframe → 发送 H-E-L-L-O 按键 → 记事本中出现 "HELLO" ✅
- 地址栏仍显示 `about:blank` ✅
- 鼠标操作正常 ✅

**参考：**
- [MDN: HTMLElement.focus()](https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/focus)
- [MDN: Using keyboard events in iframes](https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent)
- [Guacamole Keyboard.js](https://github.com/apache/guacamole-client/blob/main/guacamole-common-js/src/main/webapp/modules/Keyboard.js)

---

### BUG-016: RemoteApp 空闲 ~20 分钟后卡死无响应

**严重等级：** 🔴 高（核心功能不可用）

**现象：**
用户通过门户打开 RemoteApp 后，如果约 20 分钟不进行任何操作（不动鼠标、不按键盘），RemoteApp 窗口会完全卡死——画面冻结、鼠标点击无反应、键盘输入无效。关闭弹窗重新打开后才能恢复，但之前的工作状态丢失。

guacd 日志中反复出现：
```
guacd: ERROR: User is not responding.
guacd: INFO:  User "..." disconnected (0 users remain)
guacd: WARNING: Client did not terminate in a timely manner. Forcibly terminating client and any child processes.
```

**根因分析：**

这是一个**多层超时链条问题**，不是单一原因。从浏览器到 Windows RDP 服务器共有 7 层超时机制，任何一层断裂都会导致连接死亡：

```
超时链条（木桶效应——最短的那层决定一切）:

┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ① Portal JWT Token              480分钟 (8小时)                         │
│     └─ 仅影响 Portal API 调用，已打开的 RemoteApp 不受影响                 │
│                                                                         │
│  ② JSON Auth Token (expires)     原30分钟 → 已改为480分钟                 │
│     └─ 仅影响首次认证，连接建立后不再检查                                   │
│                                                                         │
│  ③ Backend _SessionCache TTL     原29分钟 → 已改为~8小时                  │
│     └─ 仅影响 launch 新连接，不影响已建立的连接                             │
│                                                                         │
│  ④ Guacamole API Session         原60分钟(默认) → 已改为480分钟            │
│     └─ 有活跃 tunnel 时永不驱逐 (源码: session.hasTunnels())               │
│                                                                         │
│  ⑤ NOP Ping (guacd ↔ 浏览器)     5秒/次，15秒超时 (硬编码，不可配置)       │
│     └─ guacd 和 JS 客户端互发 nop/sync，任一方 15秒无响应则断连             │
│     └─ sync 回复是事件驱动（WebSocket onmessage），不受浏览器节流影响        │
│                                                                         │
│  ⑥ 网络/防火墙/NAT               本环境: localhost + 内网直连              │
│     └─ 无中间设备，NOP ping 保持 TCP 活跃                                  │
│                                                                         │
│  ⑦ Windows RDP GPO ← ← ← ← ← ← 这是真正的瓶颈！！！                     │
│     └─ MaxIdleTime: 默认由 GPO 控制 (通常 15~30 分钟)                      │
│     └─ Windows 踢掉空闲 RDP 会话 → guacd 收到 disconnect → 连接死亡        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**精确事件链（20 分钟卡死）：**

```
T=0:      用户打开 RemoteApp，连接正常
T=0~20m:  用户空闲，但 NOP ping 持续保活 guacd ↔ 浏览器的隧道
          然而 RDP 会话层面无用户输入 → Windows 计算空闲时间
T=~20m:   Windows RDP GPO 的 MaxIdleTime 到期
          → Windows 断开 RDP 会话
          → guacd 检测到 RDP 连接断开 → 关闭隧道
          → 浏览器端 WebSocket 断开 → 画面冻结
```

**关键洞察：** Guacamole 的 NOP ping 只保活 `浏览器 ↔ guacd` 这段，**不会向 RDP 服务器发送任何保活流量**。所以即使 Guacamole 隧道完好，Windows 仍然认为 RDP 会话是空闲的。

**解决方案（两部分）：**

#### Part A: 代码层修改（消除非 Windows 层的超时瓶颈）

**1. config/config.json — 延长 JSON Auth Token 过期时间**

```diff
- "token_expire_minutes": 30
+ "token_expire_minutes": 480
```

效果：JSON Auth Token 从 30 分钟延长至 8 小时，与 Portal JWT 对齐。`_SessionCache` TTL 随之从 29 分钟延长至 ~8 小时。

**2. docker-compose.yml — 新增 Guacamole API Session 超时**

```diff
  environment:
    ...
    WEBAPP_CONTEXT: "ROOT"
+   API_SESSION_TIMEOUT: "480"
```

效果：Guacamole 的 `api-session-timeout` 从默认 60 分钟延长至 480 分钟。注意：有活跃 tunnel 的 session 本身不会被驱逐（源码 `HashTokenSessionMap.java` 中 `session.hasTunnels()` 检查），此配置是安全兜底。

**3. frontend/js/app.js — Web Worker Keepalive**

在 RemoteApp 弹出窗口注入 Web Worker，每 30 秒通过 `postMessage` 保持 iframe 活跃：

```javascript
// Web Worker keepalive: 防止浏览器后台节流冻结 Guacamole 的 NOP ping
var wb = new Blob(["setInterval(function(){postMessage(1)},30000)"],
    {type:"text/javascript"});
var wk = new Worker(URL.createObjectURL(wb));
wk.onmessage = function(){
    try { f.contentWindow.postMessage("keepalive","*") } catch(e) {}
};
```

原理：Web Worker 运行在独立线程，**不受浏览器后台标签节流（Background Tab Throttling）影响**。即使用户最小化弹窗，Worker 仍正常执行，通过 postMessage 触发 iframe 的事件循环，防止 Guacamole JS 客户端被冻结。

**修改文件清单：**

| 文件 | 修改内容 |
|------|---------|
| `config/config.json` | `token_expire_minutes: 30 → 480` |
| `docker-compose.yml` | 新增 `API_SESSION_TIMEOUT: "480"` |
| `deploy/docker-compose.yml` | 新增 `API_SESSION_TIMEOUT: "480"` |
| `frontend/js/app.js` | 注入 Web Worker keepalive 脚本 |

**部署步骤：**

```bash
# 1. 重建 guac_web 容器（加载新环境变量）
cd /home/xran && docker compose up -d guac_web

# 2. 验证环境变量生效
docker exec guac_web env | grep API_SESSION_TIMEOUT
# 应输出: API_SESSION_TIMEOUT=480

# 3. 重启 FastAPI 后端（加载新 config.json）
# 在 Windows 上重启 backend/app.py
```

#### Part B: Windows RDP 服务器组策略配置（必须手动操作）

> **⚠️ 这是解决 20 分钟卡死的核心步骤。代码层修改只能消除上游瓶颈，真正掐断连接的是 Windows RDP GPO。不做这步 = 问题依然存在。**

**方法一：图形界面 (gpedit.msc)**

在 RDP 目标服务器上运行 `gpedit.msc`，导航至：

```
计算机配置
  └─ 管理模板
      └─ Windows 组件
          └─ 远程桌面服务
              └─ 远程桌面会话主机
                  └─ 会话时间限制
```

配置以下 4 项策略：

| 策略名称 | 设置 | 值 | 说明 |
|----------|------|-----|------|
| 设置活动但空闲的远程桌面服务会话的时间限制 | **已启用** | **从不** | **核心配置**：防止空闲 RDP 会话被踢，直接解决 20 分钟卡死 |
| 设置活动的远程桌面服务会话的时间限制 | **已启用** | **从不** | 防止正在使用的会话被强制中断 |
| 设置断开连接的会话的时间限制 | **已启用** | **5 分钟** | 用户关闭浏览器后，断开的会话 5 分钟后自动注销释放资源。设为"从不"会导致僵尸会话无限堆积 |
| 到达时间限制时终止会话 | **已禁用** | — | 防止到达时间限制时强制杀掉会话（而是断开连接，允许重连） |

**方法二：注册表命令 (reg add)**

```cmd
:: ===== 在 RDP 目标服务器上以管理员身份运行 =====

:: 1. 空闲会话超时 = 永不 (0 = 禁用)
::    解决 RemoteApp 空闲 ~20 分钟后卡死
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" /v MaxIdleTime /t REG_DWORD /d 0 /f

:: 2. 活动会话超时 = 永不 (0 = 禁用)
::    防止正在使用的会话被强制中断
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" /v MaxConnectionTime /t REG_DWORD /d 0 /f

:: 3. 断开连接的会话超时 = 5 分钟 (300000 毫秒)
::    用户关闭浏览器后，断开的会话 5 分钟后自动注销释放资源
::    ⚠️ 不要设为 0（永不），否则僵尸会话会无限堆积消耗服务器资源
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" /v MaxDisconnectionTime /t REG_DWORD /d 300000 /f

:: 4. 到达时间限制时不强制终止会话
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" /v fResetBroken /t REG_DWORD /d 0 /f

:: 5. 立即刷新策略
gpupdate /force
```

**方法三：PowerShell (适合批量部署)**

```powershell
# ===== 在 RDP 目标服务器上以管理员身份运行 =====

$regPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services"

# 确保注册表路径存在
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}

# 空闲会话超时 = 永不
Set-ItemProperty -Path $regPath -Name "MaxIdleTime" -Value 0 -Type DWord

# 活动会话超时 = 永不
Set-ItemProperty -Path $regPath -Name "MaxConnectionTime" -Value 0 -Type DWord

# 断开连接的会话超时 = 5 分钟 (300000ms)
Set-ItemProperty -Path $regPath -Name "MaxDisconnectionTime" -Value 300000 -Type DWord

# 不强制终止会话
Set-ItemProperty -Path $regPath -Name "fResetBroken" -Value 0 -Type DWord

# 刷新策略
gpupdate /force

Write-Host "✅ RDP 会话超时策略已配置完成" -ForegroundColor Green
```

**验证配置是否生效：**

```cmd
:: 查看当前策略值
reg query "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" /v MaxIdleTime
reg query "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" /v MaxConnectionTime
reg query "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" /v MaxDisconnectionTime

:: 或使用 gpresult 导出完整报告
gpresult /H C:\gpo_report.html
:: 打开 gpo_report.html，搜索 "远程桌面" 或 "Terminal Services" 查看生效的策略
```

预期输出：
```
MaxIdleTime         REG_DWORD    0x0          ← 空闲永不超时
MaxConnectionTime   REG_DWORD    0x0          ← 活动永不超时
MaxDisconnectionTime REG_DWORD   0x493e0      ← 300000ms = 5分钟
```

**注意事项：**

| 项目 | 说明 |
|------|------|
| 生效范围 | 策略写入后 `gpupdate /force` 立即生效，**不需要重启** RDP 服务器 |
| 已有连接 | 新策略只对**新建立**的 RDP 会话生效，已存在的会话仍按旧策略执行 |
| 域环境 | 如果服务器加入了 Active Directory 域，域 GPO 可能覆盖本地策略。需在域控上配置或确认域策略未设置此项 |
| 多服务器 | 如果门户连接多台 Windows 服务器，**每台都需要配置** |
| MaxDisconnectionTime | 设为 5 分钟 (300000ms) 是推荐值。太短（如 1 分钟）可能导致短暂网络抖动后无法重连；太长或"从不"会导致僵尸会话堆积 |

**修改后的完整超时链（所有层生效后）：**

| 层 | 组件 | 超时值 | 空闲时是否触发 |
|----|------|--------|--------------|
| ① | Portal JWT | 8 小时 | ❌ 不影响已打开的 RemoteApp |
| ② | JSON Auth Token | 8 小时 | ❌ 仅影响首次认证 |
| ③ | Session Cache | ~8 小时 | ❌ 仅影响 launch 新连接 |
| ④ | Guacamole API Session | 8 小时 (有 tunnel 时永不驱逐) | ❌ |
| ⑤ | NOP Ping | 5秒/次 (硬编码) | ❌ sync 事件驱动，持续保活 |
| ⑥ | 网络层 | localhost + 内网 | ❌ NOP ping 保持 TCP 活跃 |
| ⑦ | Windows RDP GPO | MaxIdleTime=0 (永不) | ❌ **已解决** |

**结论：所有层配置完成后，RemoteApp 连接可以无限期空闲而不卡死。**

**参考：**
- [Microsoft: Set time limit for active but idle RDS sessions](https://learn.microsoft.com/en-us/windows-server/remote/remote-desktop-services/clients/rdp-files)
- [Microsoft: RemoteApp sessions are disconnected](https://learn.microsoft.com/en-us/troubleshoot/windows-server/remote/remoteapp-sessions-disconnected)
- [Microsoft: Session Time Limits GPO](https://admx.help/?Category=Windows_10_2016&Policy=Microsoft.Policies.TerminalServer::TS_SESSIONS_Idle_Limit_1)
- [Apache Guacamole: Configuring (api-session-timeout)](https://guacamole.apache.org/doc/gug/configuring-guacamole.html)
- [Apache Guacamole: Docker (Environment Variables)](https://guacamole.apache.org/doc/gug/guacamole-docker.html)
- [GUACAMOLE-2081: NOP ping stops sending](https://issues.apache.org/jira/browse/GUACAMOLE-2081)
- [GUACAMOLE-2138: Add optional max connection timeout](https://issues.apache.org/jira/browse/GUACAMOLE-2138)
- [GUACAMOLE-1475: Make api-session-timeout adaptable in Docker](https://issues.apache.org/jira/browse/GUACAMOLE-1475)
- [HashTokenSessionMap.java (session eviction logic)](https://github.com/apache/guacamole-client/blob/main/guacamole/src/main/java/org/apache/guacamole/rest/auth/HashTokenSessionMap.java)
- [Guacamole Mailing List: RDP idle timeout](https://www.mail-archive.com/user@guacamole.apache.org/msg07792.html)
- [Guacamole Mailing List: Session Timeout](https://www.mail-archive.com/user@guacamole.apache.org/msg14605.html)

---

### BUG-017: Admin 修改应用后 Launch 仍用旧参数（Session 缓存未失效）

**日期**: 2026-03-08
**严重程度**: 🔴 高 — 管理后台修改应用配置后用户无法正常连接
**表现**: 管理员在后台修改 `remote_app` 表的应用信息（如 hostname、密码、remote_app 路径等），用户刷新页面后点击 Launch，Guacamole 报错：`No readable active connection for tunnel.`

#### 根因分析

这是一个**缓存失效策略缺失**的经典 bug。问题出在 Guacamole JSON Auth 的 token 设计与 Portal 的缓存策略之间的配合断层：

```
数据流分析:

1. Admin 修改 remote_app 表          → DB 数据已更新 ✅
2. GET /api/apps/ (列表刷新)         → 每次都 SELECT → 显示新数据 ✅
3. POST /launch/{id}                 → _build_all_connections() 读到新参数 ✅
4. GuacamoleService.launch_connection()
   → _SessionCache.get(username)     → 缓存命中 → 返回旧 token ❌
                                        ↑ 旧参数已加密烘焙进 token
5. 旧 token 中的连接参数与实际 DB 不一致 → Guacamole 报错 ❌
```

**核心机制**: Guacamole JSON Auth 的连接参数（hostname、port、密码、remote_app 路径等）在 `POST /api/tokens` 创建 token 时被**加密烘焙**进 JSON payload。token 一旦创建，内含的连接参数就**不可变**。

**缓存层**: `_SessionCache` 是双层缓存（内存 dict + DB `token_cache` 表），TTL ≈ 479 分钟（约 8 小时）。在 TTL 内，`launch_connection()` 直接复用旧 token，**完全不看新传入的 connections 参数**。

**断层**: `admin_router.py` 的 `update_app` / `delete_app` / `update_acl` 修改了 DB 数据，但**完全不知道 `GuacamoleService` 和 `_SessionCache` 的存在** —— 两个模块之间零耦合，写入端没有触发缓存失效的通道。

#### 解决方案

**原则**: 写入端负责失效缓存（Write-Through Invalidation）。

1. **给 `_SessionCache` 添加 `invalidate_all()` 方法** — 清空内存 dict + DELETE 全表 token_cache
2. **给 `GuacamoleService` 暴露 `invalidate_all_sessions()` 方法** — 调用 `_cache.invalidate_all()`
3. **`admin_router.py` 在 4 个写操作后调用** — `create_app` / `update_app` / `delete_app` / `update_acl`

```python
# guacamole_service.py - _SessionCache
def invalidate_all(self):
    """清空全部缓存（admin 修改应用/权限后调用）"""
    with self._lock:
        self._memory.clear()
    try:
        self._db.execute_update("DELETE FROM token_cache")
    except Exception:
        logger.warning("token_cache 全量清除失败")

# guacamole_service.py - GuacamoleService
def invalidate_all_sessions(self):
    """清空所有用户的 Guacamole session 缓存"""
    self._cache.invalidate_all()
    logger.info("已清空全部 Guacamole session 缓存")

# admin_router.py - 在每个写操作后
from backend.router import guac_service
# ... update_app / delete_app / create_app / update_acl 中:
guac_service.invalidate_all_sessions()
```

**为什么用全量清除而非按用户精确清除**:
- Admin 操作频率极低（一天几次），全清的代价只是下次 launch 多一次 token 创建
- 修改一个 app 可能影响多个用户（通过 ACL 关联），精确清除需要额外查询
- 代码简洁，不容易出 bug

#### 架构教训

| 教训 | 说明 |
|------|------|
| **缓存 = 数据的影子** | 有缓存的地方就必须有失效策略。设计缓存时第一个问题不是"怎么存"而是"什么时候清" |
| **写入端必须知道缓存** | 如果模块 A 写 DB、模块 B 缓存 DB 数据，A 和 B 之间必须有失效通道 |
| **加密 token 是不可变快照** | JSON Auth token 内含的参数一旦加密就不可修改，修改源数据后必须重新创建 token |
| **"两层不同步"比"没缓存"更危险** | 没缓存只是慢，缓存和 DB 不同步会导致业务错误 |

#### 关联

- 与 [BUG-008](#bug-008-容器重建后旧-token-缓存导致登录页) 同源：都是 `_SessionCache` 与实际状态不同步
- 与 [BUG-014](#bug-014-后端重启导致旧标签被踢回登录页) 互补：014 是缓存丢失（后端重启清内存），017 是缓存该清未清

---

## 三、参考资料汇总

### 官方文档

| 文档 | 链接 |
|------|------|
| Guacamole 用户指南（主页） | https://guacamole.apache.org/doc/gug/ |
| 系统架构 | https://guacamole.apache.org/doc/gug/guacamole-architecture.html |
| Guacamole 协议 | https://guacamole.apache.org/doc/gug/guacamole-protocol.html |
| 协议指令参考 | https://guacamole.apache.org/doc/gug/protocol-reference.html |
| JSON 认证 | https://guacamole.apache.org/doc/gug/json-auth.html |
| 配置参数 | https://guacamole.apache.org/doc/gug/configuring-guacamole.html |
| Docker 部署 | https://guacamole.apache.org/doc/gug/guacamole-docker.html |
| 反向代理 | https://guacamole.apache.org/doc/gug/reverse-proxy.html |
| 扩展开发 | https://guacamole.apache.org/doc/gug/guacamole-ext.html |
| 故障排查 | https://guacamole.apache.org/doc/gug/troubleshooting.html |

### GitHub 仓库

| 仓库 | 链接 |
|------|------|
| guacamole-client（Java 前端+API） | https://github.com/apache/guacamole-client |
| guacamole-server（C 守护进程 guacd） | https://github.com/apache/guacamole-server |
| Branding 示例 | https://github.com/apache/guacamole-client/tree/main/doc/guacamole-branding-example |
| Docker entrypoint 脚本 | https://github.com/apache/guacamole-client/tree/main/guacamole-docker/entrypoint.d |
| FreeRDP 项目 | https://github.com/FreeRDP/FreeRDP |

### JIRA Issues

| Issue | 标题 | 状态 |
|-------|------|------|
| [GUACAMOLE-2123](https://issues.apache.org/jira/browse/GUACAMOLE-2123) | Remote App Windows not updated with GFX Pipeline | 相关 |
| [GUACAMOLE-1015](https://issues.apache.org/jira/browse/GUACAMOLE-1015) | Tunnel and WebSocket states out of sync | Open |
| [GUACAMOLE-67](https://issues.apache.org/jira/browse/GUACAMOLE-67) | I/O error in WebSocket can cause connection tracking to fail | 相关 |
| [GUACAMOLE-2081](https://issues.apache.org/jira/browse/GUACAMOLE-2081) | NOP ping inexplicably stops sending | Closed (Cannot Reproduce) |
| [GUACAMOLE-2138](https://issues.apache.org/jira/browse/GUACAMOLE-2138) | Add optional maximum connection timeout | Open (Feature Request) |
| [GUACAMOLE-1475](https://issues.apache.org/jira/browse/GUACAMOLE-1475) | Make api-session-timeout adaptable in Docker | Resolved |

### 其他参考

| 资源 | 链接 |
|------|------|
| Tomcat Context Path 文档 | https://tomcat.apache.org/tomcat-9.0-doc/config/context.html |
| Tomcat WAR 部署指南 | https://tomcat.apache.org/tomcat-9.0-doc/deployer-howto.html |
| FreeRDP RemoteApp Wiki | https://github.com/FreeRDP/FreeRDP/wiki/RemoteApp |
| MS-RDPERP 协议规范 | https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdperp/3aa1de2c-6353-4cc8-b33a-8907ca386c67 |
| MDN: localStorage | https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage |
| MDN: Window.open() | https://developer.mozilla.org/en-US/docs/Web/API/Window/open |
| MDN: Same-origin policy | https://developer.mozilla.org/en-US/docs/Web/Security/Same-origin_policy |
| Guacamole Mailing List: RDP idle timeout | https://www.mail-archive.com/user@guacamole.apache.org/msg07792.html |
| Guacamole Mailing List: Session Timeout | https://www.mail-archive.com/user@guacamole.apache.org/msg14605.html |
| SourceForge: Guacamole reconnect discussion | https://sourceforge.net/p/guacamole/discussion/1110834/thread/6341b248/ |
| Microsoft: RDP Session Timeout | https://learn.microsoft.com/en-us/windows-server/remote/remote-desktop-services/clients/rdp-files |
| Microsoft: RemoteApp sessions disconnected | https://learn.microsoft.com/en-us/troubleshoot/windows-server/remote/remoteapp-sessions-disconnected |
| Microsoft: Session Time Limits GPO (admx.help) | https://admx.help/?Category=Windows_10_2016&Policy=Microsoft.Policies.TerminalServer::TS_SESSIONS_Idle_Limit_1 |

---

> **更新日志**
>
> | 日期 | 更新内容 |
> |------|---------|
> | 2026-03-01 | 初始版本，记录 BUG-001 ~ BUG-010 |
> | 2026-03-01 | 追加 BUG-011 ~ BUG-013：Token 有效期分析、页面刷新会话恢复、URL 隐藏 |
> | 2026-03-02 | 追加 BUG-014：后端重启导致旧标签被踢，修正 BUG-011 结论 |
> | 2026-03-02 | 追加 BUG-015：about:blank iframe 键盘输入失效，焦点管理修复 |
> | 2026-03-02 | 追加 BUG-016：RemoteApp 空闲 ~20 分钟卡死，多层超时优化 + Windows GPO 配置指南 |
> | 2026-03-08 | 追加 BUG-017：Admin 修改应用后缓存未失效，Session 缓存失效策略修复 |
