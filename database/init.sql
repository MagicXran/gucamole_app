-- ============================================
-- Guacamole RemoteApp 门户 - 数据库初始化
-- 数据库: guacamole_portal_db
-- 编码: UTF-8, 引擎: InnoDB
--
-- MySQL Docker entrypoint 不带 --default-character-set，
-- 必须在 SQL 文件内显式声明 charset，否则中文会双重编码。
-- ============================================

/*!40101 SET NAMES utf8mb4 */;
/*!40101 SET CHARACTER_SET_CLIENT=utf8mb4 */;
/*!40101 SET CHARACTER_SET_RESULTS=utf8mb4 */;

CREATE DATABASE IF NOT EXISTS guacamole_portal_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE guacamole_portal_db;

-- RemoteApp 应用配置表
CREATE TABLE IF NOT EXISTS remote_app (
    id                    BIGINT PRIMARY KEY AUTO_INCREMENT,
    name                  VARCHAR(200)  NOT NULL             COMMENT '显示名称',
    icon                  VARCHAR(100)  DEFAULT 'desktop'    COMMENT '图标标识',
    protocol              VARCHAR(20)   NOT NULL DEFAULT 'rdp',
    hostname              VARCHAR(255)  NOT NULL,
    port                  INT           NOT NULL DEFAULT 3389,
    rdp_username          VARCHAR(100)                       COMMENT 'RDP 登录用户名',
    rdp_password          VARCHAR(200)                       COMMENT 'RDP 登录密码',
    domain                VARCHAR(100)  DEFAULT '',
    security              VARCHAR(20)   DEFAULT 'nla'        COMMENT 'nla/tls/rdp/any',
    ignore_cert           TINYINT(1)    DEFAULT 1,
    remote_app            VARCHAR(200)                       COMMENT 'RemoteApp，如 ||notepad',
    remote_app_dir        VARCHAR(500)                       COMMENT 'RemoteApp 工作目录',
    remote_app_args       VARCHAR(500)                       COMMENT 'RemoteApp 命令行参数',
    color_depth           INT           DEFAULT NULL         COMMENT '色深: 8/16/24, NULL=自动',
    disable_gfx           TINYINT(1)    DEFAULT 1            COMMENT '禁用 GFX Pipeline',
    resize_method         VARCHAR(20)   DEFAULT 'display-update' COMMENT 'display-update/reconnect',
    enable_wallpaper      TINYINT(1)    DEFAULT 0            COMMENT '显示桌面壁纸',
    enable_font_smoothing TINYINT(1)    DEFAULT 1            COMMENT 'ClearType 字体平滑',
    disable_copy          TINYINT(1)    DEFAULT 0            COMMENT '禁止从远程复制到本地',
    disable_paste         TINYINT(1)    DEFAULT 0            COMMENT '禁止从本地粘贴到远程',
    enable_audio          TINYINT(1)    DEFAULT 1            COMMENT '音频输出',
    enable_audio_input    TINYINT(1)    DEFAULT 0            COMMENT '麦克风输入',
    enable_printing       TINYINT(1)    DEFAULT 0            COMMENT '虚拟打印机(PDF)',
    timezone              VARCHAR(50)   DEFAULT NULL         COMMENT '时区, 如 Asia/Shanghai',
    keyboard_layout       VARCHAR(50)   DEFAULT NULL         COMMENT '键盘布局',
    pool_id               BIGINT        DEFAULT NULL         COMMENT '所属资源池',
    member_max_concurrent INT           NOT NULL DEFAULT 1   COMMENT '成员并发上限',
    is_active             TINYINT(1)    DEFAULT 1,
    created_at            DATETIME      DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (is_active),
    INDEX idx_pool_active (pool_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户-应用 访问控制表
CREATE TABLE IF NOT EXISTS remote_app_acl (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id     BIGINT NOT NULL                        COMMENT '用户ID',
    app_id      BIGINT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_app (user_id, app_id),
    FOREIGN KEY (app_id) REFERENCES remote_app(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 资源池定义表
CREATE TABLE IF NOT EXISTS resource_pool (
    id                     BIGINT PRIMARY KEY AUTO_INCREMENT,
    name                   VARCHAR(200) NOT NULL             COMMENT '资源池名称',
    icon                   VARCHAR(100) DEFAULT 'desktop'    COMMENT '图标',
    max_concurrent         INT         NOT NULL DEFAULT 1    COMMENT '池级并发上限',
    auto_dispatch_enabled  TINYINT(1)  NOT NULL DEFAULT 1    COMMENT '自动放行',
    dispatch_grace_seconds INT         NOT NULL DEFAULT 120  COMMENT 'ready 过期秒数',
    stale_timeout_seconds  INT         NOT NULL DEFAULT 120  COMMENT '心跳超时秒数',
    idle_timeout_seconds   INT         DEFAULT NULL          COMMENT '空闲回收秒数',
    is_active              TINYINT(1)  NOT NULL DEFAULT 1,
    created_at             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_pool_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 示例数据（请根据实际环境修改 hostname/密码）
-- ============================================

INSERT IGNORE INTO resource_pool
    (id, name, icon, max_concurrent, auto_dispatch_enabled,
     dispatch_grace_seconds, stale_timeout_seconds, idle_timeout_seconds, is_active)
VALUES
    (1, '默认池-1-记事本',   'edit',      1, 1, 120, 120, NULL, 1),
    (2, '默认池-2-计算器',   'calculate', 1, 1, 120, 120, NULL, 1),
    (3, '默认池-3-远程桌面', 'desktop',   1, 1, 120, 120, NULL, 1);

INSERT IGNORE INTO remote_app
    (id, name, icon, hostname, port, rdp_username, rdp_password, remote_app, pool_id, member_max_concurrent)
VALUES
    (1, '记事本',   'edit',      '192.168.1.6', 3389, 'admin', 'password', '||notepad', 1, 1),
    (2, '计算器',   'calculate', '192.168.1.6', 3389, 'admin', 'password', '||calc',    2, 1),
    (3, '远程桌面', 'desktop',   '192.168.1.6', 3389, 'admin', 'password', NULL,        3, 1);

-- Token 缓存表（确保后端重启后复用已有 Guacamole session）
CREATE TABLE IF NOT EXISTS token_cache (
    username    VARCHAR(64)  PRIMARY KEY              COMMENT 'Guacamole 用户名 (如 portal_u1)',
    auth_token  VARCHAR(256) NOT NULL                 COMMENT 'Guacamole authToken',
    data_source VARCHAR(64)  NOT NULL DEFAULT 'json'  COMMENT '数据源标识',
    created_at  DOUBLE       NOT NULL                 COMMENT 'Unix timestamp (秒)'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Portal 用户表
CREATE TABLE IF NOT EXISTS portal_user (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    username      VARCHAR(64)   NOT NULL UNIQUE       COMMENT '登录用户名',
    password_hash VARCHAR(200)  NOT NULL              COMMENT 'bcrypt 哈希',
    display_name  VARCHAR(100)  DEFAULT ''            COMMENT '显示名称',
    is_admin      TINYINT(1)    NOT NULL DEFAULT 0    COMMENT '是否管理员',
    quota_bytes   BIGINT        DEFAULT NULL          COMMENT '个人空间配额(字节), NULL=使用默认',
    is_active     TINYINT(1)    DEFAULT 1,
    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_log (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT       NOT NULL                COMMENT '操作者用户ID',
    username     VARCHAR(64)  NOT NULL                COMMENT '操作者用户名（冗余）',
    action       VARCHAR(50)  NOT NULL                COMMENT '动作类型',
    target_type  VARCHAR(50)  DEFAULT NULL            COMMENT '目标类型 (app/user/acl/pool/queue/session)',
    target_id    BIGINT       DEFAULT NULL            COMMENT '目标ID',
    target_name  VARCHAR(200) DEFAULT NULL            COMMENT '目标名称（冗余）',
    detail       TEXT         DEFAULT NULL            COMMENT 'JSON 额外信息',
    ip_address   VARCHAR(45)  DEFAULT NULL            COMMENT '客户端 IP',
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 活跃会话追踪表 (实时监控 + 资源池占用)
CREATE TABLE IF NOT EXISTS active_session (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id       VARCHAR(36)  NOT NULL UNIQUE     COMMENT 'UUID v4, 心跳凭证',
    user_id          BIGINT       NOT NULL,
    app_id           BIGINT       NOT NULL,
    pool_id          BIGINT       DEFAULT NULL,
    queue_id         BIGINT       DEFAULT NULL,
    started_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at DATETIME     DEFAULT NULL,
    ended_at         DATETIME     DEFAULT NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT 'active/reclaim_pending/disconnected',
    reclaim_reason   VARCHAR(20)  DEFAULT NULL        COMMENT 'stale/idle/admin/manual',
    INDEX idx_status (status),
    INDEX idx_app_status (app_id, status),
    INDEX idx_user (user_id),
    INDEX idx_pool_status (pool_id, status),
    INDEX idx_queue (queue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 启动排队/预约表
CREATE TABLE IF NOT EXISTS launch_queue (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    pool_id          BIGINT       NOT NULL,
    user_id          BIGINT       NOT NULL,
    requested_app_id BIGINT       NOT NULL,
    assigned_app_id  BIGINT       DEFAULT NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'queued' COMMENT 'queued/ready/launching/fulfilled/cancelled/expired',
    failure_count    INT          NOT NULL DEFAULT 0,
    last_error       VARCHAR(500) DEFAULT NULL,
    cancel_reason    VARCHAR(100) DEFAULT NULL,
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ready_at         DATETIME     DEFAULT NULL,
    ready_expires_at DATETIME     DEFAULT NULL,
    fulfilled_at     DATETIME     DEFAULT NULL,
    cancelled_at     DATETIME     DEFAULT NULL,
    INDEX idx_pool_status (pool_id, status, id),
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 默认管理员 (密码: admin123，生产环境请立即修改)
INSERT IGNORE INTO portal_user (id, username, password_hash, display_name, is_admin)
VALUES (1, 'admin', '$2b$12$.zHt5ZnYYg9BLJ8sXI84U.Doz2rhgbAbghicuxjUNz5vN3lFdlytu', '管理员', 1);

-- 测试用户 (密码: test123)
INSERT IGNORE INTO portal_user (id, username, password_hash, display_name, is_admin)
VALUES (2, 'test', '$2b$12$L91JPIXfv6upob1STuLlJuIZqese8iUsJdf9G/YwYCw3mIzm7TJs6', '测试用户', 0);

-- 给 admin (user_id=1) 分配所有应用
INSERT IGNORE INTO remote_app_acl (user_id, app_id)
SELECT 1, id FROM remote_app;

-- 给 test (user_id=2) 只分配记事本
INSERT IGNORE INTO remote_app_acl (user_id, app_id)
SELECT 2, id FROM remote_app WHERE name = '记事本';
