# Portal 个人空间管理系统 — 双向传输详解

## 一句话概括

**浏览器和 RemoteApp 读写的是同一块 Docker 磁盘**——没有"同步"，没有"传输协议"，就是同一个目录的两个入口。

---

## 1. 现有架构回顾：文件是怎么到 RemoteApp 里的

### 1.1 Drive Redirection 原理

当前系统已经实现了 **guacd → RDP Server** 的虚拟磁盘映射。这不是新东西，来回顾一下它的工作机制：

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Docker Host (你的服务器)                         │
│                                                                          │
│  ┌─ guacd 容器 ──────────────────────┐                                   │
│  │                                    │                                   │
│  │  Volume 挂载: guacd_drive → /drive │        RDP 协议 (RDPDR)          │
│  │                                    │ ─────────────────────────────→    │
│  │  /drive/portal_u1/                 │   "我有一块磁盘叫 GuacDrive,     │
│  │  /drive/portal_u2/                 │    内容是 /drive/portal_u1/"      │
│  │  /drive/portal_u3/                 │                                   │
│  └────────────────────────────────────┘                                   │
│                                                                          │
│                                           ┌─ RDP Server (Windows) ──┐    │
│                                           │                          │    │
│                                           │  收到 RDPDR 通道:        │    │
│                                           │  "哦，有个远程磁盘"       │    │
│                                           │                          │    │
│                                           │  映射为:                  │    │
│                                           │  \\tsclient\GuacDrive\    │    │
│                                           │                          │    │
│                                           │  RemoteApp (如 Excel)    │    │
│                                           │  可以像本地磁盘一样       │    │
│                                           │  打开/保存文件            │    │
│                                           └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

**关键理解**：

- `guacd` 是 Guacamole 的协议代理，它跟 RDP Server 建立连接
- FreeRDP（guacd 内置）支持 **Drive Redirection (RDPDR)**，可以把一个本地目录"假装"成一块磁盘
- RDP Server (Windows) 看到这块"远程磁盘"后，自动映射为 `\\tsclient\GuacDrive\`
- 所以 RemoteApp 中 **文件→另存为→`\\tsclient\GuacDrive\report.xlsx`**，实际写入的是 guacd 容器里的 `/drive/portal_u{user_id}/report.xlsx`

### 1.2 当前的参数传递链

```
config.json                          router.py                       guacamole_crypto.py
─────────────                        ─────────                       ────────────────────
"drive": {                           user_drive_path =               build_rdp_connection(
  "enabled": true,        →            f"/drive/portal_u{uid}"  →      drive_path=user_drive_path,
  "name": "GuacDrive",                                                 drive_name="GuacDrive",
  "base_path": "/drive",                                               enable_drive=True
}                                                                    )
                                                                          ↓
                                                                     RDP 参数:
                                                                       enable-drive: true
                                                                       drive-name: GuacDrive
                                                                       drive-path: /drive/portal_u1
                                                                       create-drive-path: true
```

### 1.3 当前的问题

| 问题 | 原因 |
|------|------|
| **无法上传文件到 RemoteApp** | Guacamole 侧边菜单已被 CSS 隐藏（`#guac-menu { display:none }`），上传入口消失 |
| **大文件下载不可用** | Guacamole 内置下载走 base64 blob 协议（~6KB/帧），100MB 文件要传 17000+ 帧 |
| **没有空间管理** | 用户不知道自己用了多少空间，磁盘可能被撑爆 |
| **无断点续传** | Guacamole 的文件传输没有断点恢复能力 |

---

## 2. 个人空间方案：给同一块磁盘加第二个入口

### 2.1 核心思路

现在只有 guacd 容器能访问 `guacd_drive` 这块 Docker volume。**新方案不是造新路，而是给已有的路加几个门**：

```
                    ┌─────────────────────────────────────────────────────┐
                    │         Docker Volume: guacd_drive                  │
                    │                                                     │
                    │    /drive/portal_u1/                                │
                    │       ├── report.xlsx    ← RemoteApp 保存的         │
                    │       ├── Export/                                    │
                    │       │   └── data.csv   ← RemoteApp 导出的         │
                    │       ├── 上传的文件.zip   ← 浏览器上传的            │
                    │       └── .uploads/       ← 分片上传临时目录(隐藏)   │
                    │                                                     │
                    │    /drive/portal_u2/                                │
                    │       └── ...                                       │
                    │                                                     │
                    └───────┬──────────────┬──────────────┬───────────────┘
                            │              │              │
                   ─────────┼──────────────┼──────────────┼──────────────
                            │              │              │
                    ┌───────┴──────┐ ┌─────┴──────┐ ┌────┴────────┐
                    │   guacd      │ │  portal-   │ │   nginx     │
                    │              │ │  backend   │ │             │
                    │ 挂载: rw     │ │ 挂载: rw   │ │ 挂载: ro    │
                    │ /drive       │ │ /drive     │ │ /drive      │
                    │              │ │            │ │             │
                    │ 用途:        │ │ 用途:      │ │ 用途:       │
                    │ RDP 磁盘映射 │ │ 上传写入   │ │ 下载零拷贝  │
                    │              │ │ 文件列表   │ │ sendfile    │
                    │              │ │ 配额计算   │ │ 断点续传    │
                    │              │ │ 删除操作   │ │             │
                    └──────────────┘ └────────────┘ └─────────────┘
```

**就是这么简单**——三个容器挂载同一个 Docker volume，读写同一组文件。没有同步、没有消息队列、没有 webhook 通知。一个容器写入，其他容器**立即**可见，因为底层是同一块磁盘。

### 2.2 docker-compose.yml 只改 4 行

```yaml
# 现在 (只有 guacd 挂载):
guacd:
    volumes:
      - guacd_drive:/drive          # ← 已有

# 改后 (三个容器共享):
portal-backend:
    volumes:
      - guacd_drive:/drive          # ← 新增: 读写

nginx:
    volumes:
      - guacd_drive:/drive:ro       # ← 新增: 只读
```

---

## 3. 上传：浏览器 → 个人空间 → RemoteApp 可见

### 3.1 数据流

```
用户拖拽文件到 Portal 页面
        │
        ▼
┌── 浏览器 (JavaScript) ──────────────────────────────────────────────────┐
│  1. 文件切片: file.slice(0, 10MB), file.slice(10MB, 20MB), ...         │
│  2. POST /api/files/upload/init  {path: "data.zip", size: 52428800}    │
│     → 收到 {upload_id: "abc-123", offset: 0}                           │
│  3. 循环发送分片:                                                       │
│     POST /api/files/upload/chunk                                        │
│       FormData: upload_id + offset + chunk(10MB Blob)                   │
│     → 收到 {offset: 10485760, complete: false}                          │
│     → 更新进度条: 20% → 40% → 60% → 80% → 100%                        │
│  4. 最后一片返回 {complete: true}                                       │
│     → 刷新文件列表 + 刷新配额显示                                       │
└─────────────────────────────────────────────────────────────────────────┘
        │
        │ HTTP (经过 Nginx 流式转发, proxy_request_buffering off)
        ▼
┌── portal-backend 容器 (FastAPI) ────────────────────────────────────────┐
│  /api/files/upload/init:                                                │
│    ① JWT 验证 → 提取 user_id                                           │
│    ② 配额检查: 已用 + 文件大小 > 配额? → 拒绝 422                      │
│    ③ 创建 /drive/portal_u{id}/.uploads/abc-123.meta  (JSON 元信息)     │
│    ④ 创建 /drive/portal_u{id}/.uploads/abc-123.tmp   (空文件)          │
│    ⑤ 返回 {upload_id, offset: 0}                                       │
│                                                                         │
│  /api/files/upload/chunk:                                               │
│    ① 加载 .meta, 验证 user_id 匹配                                     │
│    ② 验证 offset == .tmp 当前大小 (防乱序)                              │
│    ③ 配额二次检查 (防并发上传绕过)                                      │
│    ④ chunk_data = await chunk.read()                                    │
│    ⑤ await run_in_executor(线程池):  ← 不阻塞事件循环!                  │
│         with open(.tmp, "ab") as f:                                     │
│             f.write(chunk_data)                                         │
│    ⑥ 如果写完全部:                                                      │
│         shutil.move(.tmp → /drive/portal_u{id}/data.zip)  ← 原子操作   │
│         删除 .meta                                                      │
│         清除使用量缓存                                                   │
└─────────────────────────────────────────────────────────────────────────┘
        │
        │ 写入的目标路径: /drive/portal_u{id}/data.zip
        │ 这个路径在 guacd 容器内也是 /drive/portal_u{id}/data.zip
        ▼
┌── guacd 容器 ───────────────────────────────────────────────────────────┐
│  FreeRDP Drive Redirection:                                             │
│  /drive/portal_u{id}/data.zip  →  \\tsclient\GuacDrive\data.zip        │
│                                                                         │
│  RemoteApp 打开资源管理器或 "文件→打开"                                 │
│  导航到 \\tsclient\GuacDrive\ → 看到 data.zip → 可以直接使用            │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 断点续传

```
场景: 上传 500MB 文件, 传到 200MB 时网络断了

第一次:
  POST /upload/init  {path: "big.zip", size: 500MB}  → {upload_id: "xyz", offset: 0}
  POST /upload/chunk {offset: 0,   chunk: 10MB}      → {offset: 10MB}
  POST /upload/chunk {offset: 10MB, chunk: 10MB}     → {offset: 20MB}
  ... 传到 200MB ...
  ✗ 网络断开

  磁盘上:
    .uploads/xyz.meta  → {"path":"big.zip", "size":500MB, "user_id":1, "created":...}
    .uploads/xyz.tmp   → 200MB 的不完整文件

页面刷新后, 用户再次上传同一个文件:
  POST /upload/init  {path: "big.zip", size: 500MB}
    → 后端扫描 .uploads/*.meta
    → 找到匹配: path="big.zip" 且 size=500MB
    → 读取 xyz.tmp 大小 = 200MB
    → 返回 {upload_id: "xyz", offset: 200MB}  ← 从断点继续!

  POST /upload/chunk {offset: 200MB, chunk: 10MB}   → {offset: 210MB}
  ... 继续传完 ...
  POST /upload/chunk {offset: 490MB, chunk: 10MB}   → {complete: true}
```

---

## 4. 下载：RemoteApp 保存 → 浏览器取回

### 4.1 数据流

```
RemoteApp 中:
  用户点 "文件→另存为→ \\tsclient\GuacDrive\result.xlsx"
        │
        │ RDP RDPDR 协议
        ▼
┌── guacd 容器 ───────────────────────────────────────────────────────────┐
│  FreeRDP 将 RDPDR 写操作翻译为本地文件系统写入:                          │
│  \\tsclient\GuacDrive\result.xlsx  →  /drive/portal_u{id}/result.xlsx   │
│  (对 RDP Server 来说, 这就像写了一块网络磁盘)                            │
│  (对 guacd 来说, 这就是写了本地 /drive/ 目录下的一个文件)                │
└─────────────────────────────────────────────────────────────────────────┘
        │
        │ 同一个 Docker volume, 零延迟
        ▼
┌── 用户在 Portal 页面点击 "下载" ────────────────────────────────────────┐
│                                                                         │
│  浏览器:                                                                │
│    window.open("/api/files/download?path=result.xlsx&_token=jwt-xxx")   │
│                                                                         │
│    为什么用 _token query 而不是 Authorization header?                    │
│    因为 window.open / <a> 标签触发的下载无法设置 HTTP header             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
        │
        │ HTTP GET (经过 Nginx)
        ▼
┌── portal-backend 容器 (FastAPI) ────────────────────────────────────────┐
│  /api/files/download:                                                   │
│    ① JWT 验证 (从 _token query 或 Authorization header)                 │
│    ② _safe_resolve: 防路径穿越 (../../etc/passwd → 拒绝 400)           │
│    ③ 确认文件存在且是普通文件                                           │
│    ④ 构造响应:                                                          │
│       Response(                                                         │
│         status_code=200,                                                │
│         headers={                                                       │
│           "X-Accel-Redirect": "/internal-drive/portal_u1/result.xlsx",  │
│           "Content-Disposition": "attachment; filename*=UTF-8''...",     │
│           "Content-Type": "application/octet-stream",                   │
│         }                                                               │
│       )                                                                 │
│                                                                         │
│    FastAPI 不读文件内容! 只返回一个带特殊 header 的空响应                │
│    实际的文件传输由 Nginx 接管                                           │
└─────────────────────────────────────────────────────────────────────────┘
        │
        │ X-Accel-Redirect 触发 Nginx 内部重定向
        ▼
┌── nginx 容器 ───────────────────────────────────────────────────────────┐
│  location /internal-drive/ {                                            │
│      internal;            ← 外部直接访问返回 403                        │
│      alias /drive/;       ← 映射到 Docker volume                       │
│  }                                                                      │
│                                                                         │
│  Nginx 收到 X-Accel-Redirect: /internal-drive/portal_u1/result.xlsx    │
│    → 解析为本地路径: /drive/portal_u1/result.xlsx                       │
│    → 调用 sendfile() 系统调用: 内核直接从磁盘→网卡, 不经过用户态         │
│    → 自动支持 Range 请求: 浏览器暂停/恢复下载 = 断点续传                │
│                                                                         │
│  传输 1GB 文件, Nginx 内存占用: ~0  (零拷贝)                            │
│  传输 1GB 文件, FastAPI 内存占用: ~0  (它压根没碰文件字节)               │
└─────────────────────────────────────────────────────────────────────────┘
        │
        │ HTTP 响应 (文件字节流)
        ▼
  浏览器弹出下载对话框, 开始接收文件
```

### 4.2 为什么不让 FastAPI 直接读文件返回？

| 方案 | 1GB 文件内存占用 | 断点续传 | 传输速度 |
|------|-----------------|---------|---------|
| `FileResponse` (FastAPI 直读) | ~1GB (全读入内存) | 需手动实现 Range | 受 Python GIL 限制 |
| `StreamingResponse` (FastAPI 流式) | ~10MB (分块) | 需手动实现 Range | 受 Python GIL 限制 |
| **X-Accel-Redirect (Nginx sendfile)** | **~0** | **自动支持** | **内核级，接近磁盘 IO 上限** |

没有悬念，用 X-Accel-Redirect。

---

## 5. 完整架构图：五个容器的角色

```
┌─ 用户浏览器 ─────────────────────────────────────────────────────────────┐
│                                                                          │
│  Portal 页面                                                             │
│  ├── 应用 Tab: 点击 → 打开 RemoteApp 窗口                               │
│  └── 我的空间 Tab: 文件列表 / 上传 / 下载 / 删除 / 配额展示             │
│                                                                          │
│  RemoteApp 窗口 (about:blank + iframe)                                   │
│  └── Guacamole 客户端 → WebSocket → guacd → RDP → 远程应用              │
│       远程应用内: "另存为" → \\tsclient\GuacDrive\                       │
│                                                                          │
└──────────────┬────────────────────────────────────────────────────────────┘
               │ HTTP/WebSocket (端口 80/8880)
               ▼
┌─ nginx ──────────────────────────────────────────────────────────────────┐
│  路由规则:                                                               │
│  /api/files/upload/*  → portal-backend (proxy_request_buffering off)    │
│  /api/*               → portal-backend                                  │
│  /guacamole/*         → guac-web (WebSocket 升级)                       │
│  /internal-drive/*    → 本地 /drive/ (internal, sendfile 零拷贝下载)    │
│  /*                   → portal-backend (静态文件)                       │
│                                                                          │
│  Volume: guacd_drive:/drive:ro  ← 只读, 仅用于下载                      │
└──────────────┬───────────────────────────┬───────────────────────────────┘
               │                           │
       ┌───────┴───────┐           ┌───────┴───────┐
       ▼               ▼           ▼               │
┌─ portal-backend ─┐  ┌─ guac-web ───┐             │
│  FastAPI          │  │  Tomcat      │             │
│                   │  │  Guacamole   │             │
│  Volume:          │  │  Web App     │             │
│  guacd_drive:     │  │              │             │
│  /drive (rw)      │  │  JSON Auth   │             │
│                   │  │  处理加密    │             │
│  功能:            │  │  token       │             │
│  ・JWT 认证       │  │              │             │
│  ・文件列表       │  └───────┬──────┘             │
│  ・上传(写入)     │          │                     │
│  ・下载(X-Accel)  │          │ guacd 协议          │
│  ・删除           │          ▼                     │
│  ・配额管理       │  ┌─ guacd ────────────┐       │
│                   │  │  FreeRDP           │       │
└───────┬───────────┘  │                    │       │
        │              │  Volume:           │       │
        │              │  guacd_drive:      │       │
        │              │  /drive (rw)       │       │
        ▼              │                    │       │
┌─ guac-sql ────┐      │  Drive Redirect:  │       │
│  MySQL 8.0    │      │  /drive/portal_u1  │       │
│               │      │  → \\tsclient\     │       │
│  portal_user  │      │    GuacDrive\     │       │
│  (quota_bytes)│      │                    │       │
│               │      │  RDP → Windows    │       │
│  remote_app   │      └────────────────────┘       │
│  audit_log    │                                    │
└───────────────┘                                    │
                                                     │
        ┌────────────────────────────────────────────┘
        │
        │  所有路径最终指向同一个物理存储:
        ▼
   ┌─────────────────────────────────────┐
   │   Docker Volume: guacd_drive        │
   │                                     │
   │   /drive/                           │
   │   ├── portal_u1/    (用户 1)        │
   │   │   ├── report.xlsx               │
   │   │   ├── Export/                   │
   │   │   │   └── data.csv             │
   │   │   └── .uploads/  (临时, 隐藏)  │
   │   ├── portal_u2/    (用户 2)        │
   │   │   └── ...                       │
   │   └── portal_u3/    (用户 3)        │
   │       └── ...                       │
   └─────────────────────────────────────┘
```

---

## 6. 为什么"零同步延迟"？

### Docker Volume 的本质

Docker volume 不是什么高科技。在 Linux 上，`guacd_drive` 本质上就是宿主机 `/var/lib/docker/volumes/guacamole_guacd_drive/_data/` 这个目录。

当三个容器都声明 `guacd_drive:/drive` 时，Docker 做的事情等价于：

```bash
# Docker 启动 guacd 容器时:
mount --bind /var/lib/docker/volumes/guacamole_guacd_drive/_data  /容器rootfs/drive

# Docker 启动 portal-backend 容器时:
mount --bind /var/lib/docker/volumes/guacamole_guacd_drive/_data  /容器rootfs/drive

# Docker 启动 nginx 容器时:
mount --bind /var/lib/docker/volumes/guacamole_guacd_drive/_data  /容器rootfs/drive
```

三个 bind mount 指向同一个宿主机目录。所以：

- guacd 写入 `/drive/portal_u1/file.txt`
- portal-backend 读取 `/drive/portal_u1/file.txt` → **立即**看到
- 没有缓存失效问题，没有最终一致性，没有传播延迟
- 这跟你在同一台电脑上用两个程序打开同一个文件夹是**完全一样的**

### Windows Docker Desktop 的情况

在 Windows (Docker Desktop + WSL2) 上，volume 存储在 WSL2 虚拟机的 ext4 文件系统中，但同样是三个容器共享同一块存储，零延迟。

---

## 7. 配额系统：为什么不用数据库记录使用量

### 问题

RemoteApp 内用户可以直接操作 `\\tsclient\GuacDrive\`——创建文件、删除文件、复制粘贴——这些操作**完全绕过 Portal API**。如果我们在数据库里维护 `used_bytes` 字段，RemoteApp 端的任何文件操作都不会更新这个字段，数据必然失准。

### 方案

**实时扫描目录 + 内存缓存**：

```python
# 每次查询: 遍历用户目录, 加总所有文件大小
total = sum(f.stat().st_size for f in user_dir.rglob("*") if f.is_file())

# 缓存 60 秒, 避免频繁 IO
_usage_cache[user_id] = (time.time(), total)
```

| 问题 | 回答 |
|------|------|
| 遍历慢不慢？ | 10 万个文件 ~200ms, 且有 60s 缓存, 实际平均响应 <1ms |
| 缓存会失准？ | 最多差 60 秒, 配额控制不需要毫秒级精确 |
| 并发上传绕过？ | init 检查一次 + 每个 chunk 再检查一次, 双重校验 |

### 配额来源

```
portal_user.quota_bytes
    │
    ├── NULL → 使用 config.json 的 default_quota_gb (默认 10GB)
    └── 非 NULL → 管理员为该用户单独设置的配额 (如 50GB)
```

---

## 8. 安全设计

### 8.1 路径防穿越

这是文件系统 API 最关键的安全问题。如果用户构造 `path=../../etc/passwd`，不做防护就是灾难。

```python
def _safe_resolve(user_id: int, relative_path: str) -> Path:
    base = (DRIVE_BASE / f"portal_u{user_id}").resolve()  # 绝对路径
    target = (base / relative_path).resolve()              # 解析掉所有 ../
    # 关键: target 必须在 base 目录内
    if not str(target).startswith(str(base) + os.sep) and target != base:
        raise HTTPException(400, "非法路径")
    return target
```

**攻击尝试与防御结果**：

| 输入 path | resolve 后 | 校验结果 |
|-----------|-----------|---------|
| `report.xlsx` | `/drive/portal_u1/report.xlsx` | ✅ 通过 |
| `sub/dir/file.txt` | `/drive/portal_u1/sub/dir/file.txt` | ✅ 通过 |
| `../../etc/passwd` | `/etc/passwd` | ❌ 拒绝: 不在 `/drive/portal_u1/` 前缀内 |
| `../portal_u2/secret` | `/drive/portal_u2/secret` | ❌ 拒绝: 不在 `/drive/portal_u1/` 前缀内 |
| 符号链接 → /etc | resolve 后变成 `/etc/...` | ❌ 拒绝: resolve() 会追踪符号链接 |

### 8.2 用户隔离

每个用户只能访问 `/drive/portal_u{自己的user_id}/`。`user_id` 从 JWT token 中提取，无法伪造。

```
用户 A (user_id=1): 只能操作 /drive/portal_u1/
用户 B (user_id=2): 只能操作 /drive/portal_u2/
```

---

## 9. Nginx 配置要点

### 9.1 上传：流式转发

```nginx
location /api/files/upload/ {
    client_max_body_size 0;           # 不限大小 (后端自己校验配额)
    proxy_request_buffering off;      # ★ 关键: 不缓冲到 Nginx 临时文件
    proxy_pass http://portal_backend;
    proxy_read_timeout 300s;          # 大文件上传可能慢
}
```

**`proxy_request_buffering off` 的作用**：

默认情况下，Nginx 会先把整个请求体写到临时文件，再转发给后端。对于 10MB 的 chunk，这意味着：
1. 客户端 → Nginx 临时文件 (写一次)
2. Nginx 临时文件 → FastAPI (读一次，写一次到最终文件)

关闭缓冲后：
1. 客户端 → FastAPI (直接流式转发，写一次到最终文件)

少了一次磁盘 IO，且不需要 Nginx 临时目录的磁盘空间。

### 9.2 下载：internal + sendfile

```nginx
location /internal-drive/ {
    internal;                         # ★ 外部请求直接 403
    alias /drive/;                    # 映射到 volume
}
```

- `internal` 意味着只有后端返回 `X-Accel-Redirect` header 时才会触发
- 用户不能直接访问 `http://server/internal-drive/portal_u1/file.txt`
- Nginx 的 `sendfile` 默认开启，文件传输走内核零拷贝

---

## 10. 前端交互设计

### 10.1 页面布局

Portal 首页新增 Tab 切换：**应用** | **我的空间**

```
┌─ Header ──────────────────────────────────────────────────┐
│  RemoteApp 门户                          admin  用户  退出  │
├─ Tab Bar ─────────────────────────────────────────────────┤
│  [应用]  [我的空间]                                        │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─ 配额进度条 ─────────────────────────────────────┐     │
│  │ ████████████░░░░░░░░░░  3.2 GB / 10 GB  (32%)   │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
│  ┌─ 工具栏 ─────────────────────────────────────────┐     │
│  │ 📂 根目录 / Export /       [新建文件夹]  [上传文件] │     │
│  ├──────────────────────────────────────────────────┤     │
│  │ 名称              大小      修改时间     操作      │     │
│  │ 📁 Export/         —        03-09 14:30           │     │
│  │ 📄 report.xlsx    2.1 MB   03-09 10:15  [↓] [🗑]  │     │
│  │ 📄 backup.zip     1.1 GB   03-08 22:30  [↓] [🗑]  │     │
│  ├──────────────────────────────────────────────────┤     │
│  │                                                    │     │
│  │          ┌──────────────────────────┐              │     │
│  │          │  拖放文件到此处上传        │              │     │
│  │          └──────────────────────────┘              │     │
│  │                                                    │     │
│  ├─ 上传任务 ───────────────────────────────────────┤     │
│  │ data.csv   ████████░░ 80%   48 MB/s               │     │
│  │ model.bin  ██░░░░░░░░ 15%   32 MB/s          [✕]  │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### 10.2 用户操作流程

**上传文件**：
1. 点击 "上传文件" 按钮 或 拖拽文件到拖拽区域
2. 出现进度条，显示百分比 + 速度
3. 完成后文件出现在列表中
4. 配额进度条实时更新
5. 切换到 RemoteApp → `\\tsclient\GuacDrive\` 里已经有了

**下载文件**：
1. 在 RemoteApp 中 "另存为" 到 `\\tsclient\GuacDrive\`
2. 回到 Portal "我的空间" Tab
3. 刷新看到文件（或等 60 秒自动出现）
4. 点击下载按钮 → 浏览器标准下载，支持暂停/恢复

**管理文件**：
- 新建文件夹: 输入名称 → 创建
- 删除: 确认弹窗 → 删除 → 配额立即释放
- 目录导航: 点击文件夹进入, 面包屑导航回退

---

## 11. 管理后台扩展

### 用户管理 — 配额控制

管理员在用户编辑页面可以设置每个用户的配额：

| 操作 | 说明 |
|------|------|
| 查看用户列表 | 每行显示 "已用 / 配额" (如 "3.2 GB / 10 GB") |
| 编辑用户配额 | 下拉选择: 5GB / 10GB / 20GB / 50GB / 100GB / 不限制 / 自定义 |
| 默认配额 | config.json 中 `default_quota_gb: 10`，新用户自动继承 |

### 审计日志

所有文件操作记录到 `audit_log` 表：

```
操作类型        target_name 示例
file_upload     data/backup.zip (52.4 MB)
file_download   report.xlsx
file_delete     old_data/ (目录)
```

---

## 12. 待确认的问题

请审阅后反馈以下几点：

1. **默认配额 10GB 是否合理？** 你们的仿真结果文件通常多大？
2. **单文件 50GB 上限够不够？** 有没有更大的单体文件场景？
3. **分片大小 10MB 是否合适？** 网络条件好可以调大（减少请求数），差可以调小（减少重传浪费）
4. **是否需要文件夹上传？** 当前设计只支持单文件上传（含拖拽多文件），不支持保持目录结构的文件夹上传
5. **是否需要文件重命名功能？** 当前只有 列表/上传/下载/删除/新建文件夹
6. **RemoteApp 锁定文件时的行为？** 如果 Excel 正在编辑某文件，Portal 端删除会失败（文件被锁定）——当前方案是返回友好错误提示，这个行为可以接受吗？
