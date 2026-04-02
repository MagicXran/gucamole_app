# Guacamole RemoteApp Portal — Docker 部署指南

## 包内容

```
deploy/
├── .env                         # 密码/密钥/时区（按目标环境修改）
├── docker-compose.yml           # 容器编排，一键启动
├── guac-web.Dockerfile          # Guacamole Web 自定义镜像（含品牌扩展）
├── branding/
│   └── portal-branding.jar      # 品牌覆盖扩展（去除 Guacamole 标识）
└── initdb/
    └── 00-full-dump.sql         # 两个数据库完整快照（schema + 种子数据）
                                 #   - guacamole_db:       Guacamole 核心库
                                 #   - guacamole_portal_db: Portal 应用配置库
```

## 项目名与服务

Compose 项目名默认是 `nercar-portal`，但实际由 `.env` 里的 `PORTAL_INSTANCE_ID` 决定。
同机并行跑多套实例时，先改这个值，再按需改 `MYSQL_HOST_PORT`，否则你自己会把自己端口撞死。

| Service 名 | 镜像 | 用途 | 端口 |
|--------|------|------|------|
| **guacd** | guacamole/guacd | RDP/VNC/SSH 协议代理（C 语言守护进程） | 4822（内部） |
| **guac-sql** | mysql:8 | 数据库（Guacamole 核心 + Portal 应用配置） | 默认 `33060→3306`，可用 `MYSQL_HOST_PORT` 覆盖 |
| **guac-web** | 自定义构建 | Guacamole Web 前端 + REST API（Tomcat） | 8080（容器内） |
| **portal-backend** | 自定义构建 | FastAPI 门户后端 | 8000（容器内） |
| **nginx** | nginx:alpine | 外部入口代理 | `${PORTAL_PORT:-80}→80` |

---

## 部署步骤

### 前提条件

- Docker Engine 20.10+
- Docker Compose v2（`docker compose` 命令可用）
- 目标机器可访问互联网（首次需拉取镜像）

### 第一步：拷贝部署包

将整个 `deploy/` 目录拷贝到目标机器，进入目录：

```bash
cd deploy/
```

### 第二步：修改配置

编辑 `.env` 文件，按目标环境调整：

```ini
# Compose 实例标识（同机多套实例时必须改）
PORTAL_INSTANCE_ID=nercar-portal

# MySQL 密码（生产环境请改为强密码）
MYSQL_ROOT_PASSWORD=xran
MYSQL_USER=guacamole_user
MYSQL_PASSWORD=xran
MYSQL_DATABASE=guacamole_db

# 开发态默认暴露到宿主机 33060；并行实例时显式改掉它
# MYSQL_HOST_PORT=33060

# 生产环境如需直接挂宿主机目录，配置这两个
# MYSQL_DATA_SOURCE=/srv/nercar-portal/mysql
# GUAC_DRIVE_SOURCE=/srv/nercar-portal/drive

# Guacamole JSON Auth 密钥（128-bit hex）
# ⚠ 必须与 FastAPI 后端 config/config.json 中的 json_secret_key 一致
JSON_SECRET_KEY=4c0b569e4c96df157eee1b65dd0e4d41

# 时区
TZ=Asia/Shanghai
```

历史环境如果还在用旧字段名 `GUAC_DB_ROOT_PASSWORD`、`GUAC_DB_PASSWORD`、`GUACAMOLE_JSON_SECRET_KEY`，当前 compose 仍兼容；但别再继续沿用，规范名才是正道。

### 第三步：修改 RDP 连接信息（如目标服务器地址变了）

dump 文件中包含了 RDP 连接的凭据。如果目标 Windows 服务器的 IP/账号/密码变了，
编辑 `initdb/00-full-dump.sql`，找到 `INSERT INTO remote_app` 这一行，
修改其中的 hostname、rdp_username、rdp_password：

```sql
-- 找到类似这样的行（约第 736 行）：
INSERT INTO `remote_app` VALUES
  (1,'记事本','edit','rdp','192.168.1.8',3389,'xran','Nercar501', ...),
                              ^^^^^^^^^^^^      ^^^^   ^^^^^^^^
                              目标IP            用户名  密码
```

也可以先部署，后面通过 FastAPI 后端 API 修改。

### 第四步：启动容器

```bash
docker compose up -d
```

首次启动时：
0. 如目标机器上已存在同项目名 volume：先确认 `PORTAL_INSTANCE_ID`，再按实际 volume 名删除，例如 `docker volume rm nercar-portal_mysql_data`
1. Docker 拉取 `guacamole/guacd:latest` 和 `mysql:8` 基础镜像
2. 构建 `guac-web` 与 `portal-backend` 自定义镜像
3. MySQL 容器初始化时自动执行 `initdb/00-full-dump.sql`，创建两个数据库
4. `guac-web` 和 `portal-backend` 等待 MySQL 健康检查通过后启动

### 第五步：验证部署

```bash
# 1. 查看容器状态（guac-sql 应为 healthy）
docker compose ps

# 2. 测试入口是否响应
curl -s http://localhost:${PORTAL_PORT:-80}/health
# 应返回 {"status":"ok"}

# 3. 检查数据库是否正确初始化
docker compose exec -T guac-sql mysql -uroot -p你的密码 --default-character-set=utf8mb4 \
    -e "SHOW DATABASES"
# 应看到 guacamole_db 和 guacamole_portal_db

# 4. 检查 Portal 应用数据
docker compose exec -T guac-sql mysql -uroot -p你的密码 --default-character-set=utf8mb4 \
    guacamole_portal_db -e "SELECT id, name, hostname FROM remote_app"
# 应看到记事本、计算器、远程桌面三条记录
```

---

## 后续维护操作

### 重置数据库（清空所有数据重新初始化）

```bash
docker compose down -v     # -v 删除当前项目名下的 mysql_data / guacd_drive volume
docker compose up -d       # 重新初始化
```

### 手动执行 SQL（带正确编码）

⚠ **关键**：在 Windows 或 WSL 环境中通过管道执行 SQL 文件时，
**必须**加 `--default-character-set=utf8mb4`，否则中文字段（COMMENT 等）会乱码。

```bash
# ✅ 正确写法
docker compose exec -T guac-sql mysql -uroot -p密码 --default-character-set=utf8mb4 < your-file.sql

# ❌ 错误写法（中文会变成乱码）
docker compose exec -T guac-sql mysql -uroot -p密码 < your-file.sql
```

`mysqldump` 导出时也一样：

```bash
# ✅ 正确写法
docker compose exec -T guac-sql mysqldump -uroot -p密码 --default-character-set=utf8mb4 \
    --databases guacamole_db guacamole_portal_db > backup.sql

# ❌ 错误写法
docker compose exec -T guac-sql mysqldump -uroot -p密码 --databases ... > backup.sql
```

**乱码原因**：Windows/WSL 的 shell 管道默认使用 latin1/Windows-1252 编码，
UTF-8 中文字节经过 latin1 解读后被双重编码存入数据库，形成不可逆的 mojibake。
`--default-character-set=utf8mb4` 强制 MySQL 客户端以 UTF-8 解释输入字节。

### 查看容器日志

```bash
docker compose logs -f guac-web    # Guacamole/Tomcat 日志（service name）
docker compose logs -f guacd       # 协议代理日志（RDP 连接调试）
docker compose logs -f guac-sql    # MySQL 日志
docker compose logs -f portal-backend  # FastAPI 门户日志
docker compose logs -f nginx       # 反向代理日志
```

### 重建 guac-web / portal-backend 镜像

```bash
docker compose build guac-web portal-backend
docker compose up -d guac-web portal-backend
```

### 备份与恢复

```bash
# 查看当前项目实例的 MySQL / drive 挂载状态
./backup.sh status

# 导出数据库 + drive
./backup.sh export

# 从备份目录恢复
./backup.sh import ./backups/20260321_215500
```

---

## 配合 FastAPI 后端

完整 compose 现在已经包含 `portal-backend` + `nginx`，默认推荐直接用整套容器跑。

如果你坚持在宿主机单独跑 FastAPI 后端（`backend/app.py`），也可以，但要保证下面几项和 compose 对齐：

```bash
cd /path/to/gucamole_app
python backend/app.py
```

后端的 `config/config.json` 中以下字段需要与 Docker 配置对应：

| config.json 字段 | 对应 .env / compose 配置 |
|------------------|--------------------------|
| `database.host` | `127.0.0.1`（宿主机访问容器端口） |
| `database.port` | compose 中 guac-sql 的映射端口（默认 `33060`，或你设置的 `MYSQL_HOST_PORT`） |
| `database.user` | `root`（后端用 root 连接 portal_db） |
| `database.password` | `.env` 中的 `MYSQL_ROOT_PASSWORD` |
| `guacamole.json_secret_key` | `.env` 中的 `JSON_SECRET_KEY`（必须一致） |
| `guacamole.internal_url` | `http://localhost:8080/guacamole` |
| `guacamole.external_url` | `http://localhost:${PORTAL_PORT}/guacamole` |

如果你改了 `MYSQL_HOST_PORT`，宿主机后端也得同步改 `config/config.json` 或设置 `PORTAL_DB_PORT`，别自己把端口配散了。

---

## 常见问题

**Q: guac-web 启动报数据库连接错误？**
A: guac-web 依赖 guac-sql 的 healthcheck。如果 MySQL 初始化较慢（首次导入大量数据），
等待 30-60 秒后 guac-web 会自动重连。用 `docker compose ps` 确认 guac-sql 状态为 healthy。

**Q: 浏览器访问 8080 跳转到 Guacamole 登录页？**
A: 正常。用户应访问 `nginx` 暴露的门户入口（默认 80 端口），不是直接怼 8080。
后端通过 JSON Auth 加密机制获取 token，自动跳转到 Guacamole 连接页面。

**Q: 同机起第二套实例为什么还冲突？**
A: 你大概率只改了 `PORTAL_INSTANCE_ID`，没改 `MYSQL_HOST_PORT`。项目名隔离了容器/volume，不会帮你自动避开宿主机端口。

**Q: 迁移后 RDP 连不上？**
A: 检查 `initdb/00-full-dump.sql` 中 `remote_app` 表的 hostname 是否改为新环境的 Windows 服务器 IP，
以及目标服务器的 RDP 服务和 RemoteApp 是否已配置。
