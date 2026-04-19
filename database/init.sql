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
    disable_download      TINYINT(1)    DEFAULT NULL         COMMENT '禁用下载到本地',
    disable_upload        TINYINT(1)    DEFAULT NULL         COMMENT '禁用本地上传到远程',
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
    request_mode     VARCHAR(20)  NOT NULL DEFAULT 'gui' COMMENT 'gui/task',
    platform_task_id BIGINT       DEFAULT NULL,
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
    INDEX idx_user_status (user_id, status),
    INDEX idx_platform_task (platform_task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 应用目录（统一映射 GUI/脚本运行形态）
CREATE TABLE IF NOT EXISTS catalog_app (
    id             BIGINT PRIMARY KEY AUTO_INCREMENT,
    app_key        VARCHAR(100) NOT NULL,
    name           VARCHAR(200) NOT NULL,
    app_kind       VARCHAR(50)  NOT NULL COMMENT 'simulation_runtime/remoteapp_exe/web_app',
    icon           VARCHAR(100) DEFAULT 'desktop',
    description    TEXT         DEFAULT NULL,
    owner_user_id  BIGINT       DEFAULT NULL,
    review_status  VARCHAR(30)  NOT NULL DEFAULT 'internal' COMMENT 'internal/draft/pending_review/rejected/approved/published/unpublished',
    is_active      TINYINT(1)   NOT NULL DEFAULT 1,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_catalog_app_key (app_key),
    INDEX idx_catalog_app_kind_active (app_kind, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Worker 节点组
CREATE TABLE IF NOT EXISTS worker_group (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    group_key       VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     VARCHAR(500) DEFAULT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    max_claim_batch INT          NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_worker_group_key (group_key),
    INDEX idx_worker_group_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 应用绑定（GUI RemoteApp / Worker 脚本 等）
CREATE TABLE IF NOT EXISTS app_binding (
    id                     BIGINT PRIMARY KEY AUTO_INCREMENT,
    app_id                 BIGINT       NOT NULL,
    binding_kind           VARCHAR(50)  NOT NULL COMMENT 'gui_remoteapp/worker_script/external_web',
    name                   VARCHAR(200) NOT NULL,
    remote_app_id          BIGINT       DEFAULT NULL,
    resource_pool_id       BIGINT       DEFAULT NULL,
    worker_group_id        BIGINT       DEFAULT NULL,
    requires_resource_pool TINYINT(1)   NOT NULL DEFAULT 0,
    is_enabled             TINYINT(1)   NOT NULL DEFAULT 1,
    launch_config_json     JSON         DEFAULT NULL,
    runtime_config_json    JSON         DEFAULT NULL,
    open_api_profile_json  JSON         DEFAULT NULL,
    created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_app_binding_app_kind (app_id, binding_kind),
    INDEX idx_app_binding_group_enabled (worker_group_id, is_enabled),
    FOREIGN KEY (app_id) REFERENCES catalog_app(id) ON DELETE CASCADE,
    FOREIGN KEY (remote_app_id) REFERENCES remote_app(id) ON DELETE SET NULL,
    FOREIGN KEY (resource_pool_id) REFERENCES resource_pool(id) ON DELETE SET NULL,
    FOREIGN KEY (worker_group_id) REFERENCES worker_group(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 应用脚本预设
CREATE TABLE IF NOT EXISTS remote_app_script_profile (
    id                   BIGINT PRIMARY KEY AUTO_INCREMENT,
    remote_app_id        BIGINT       NOT NULL,
    is_enabled           TINYINT(1)   NOT NULL DEFAULT 0,
    executor_key         VARCHAR(100) NOT NULL COMMENT 'python_api/command_statusfile',
    scratch_root         VARCHAR(500) DEFAULT NULL,
    artifact_policy_json JSON         DEFAULT NULL,
    log_policy_json      JSON         DEFAULT NULL,
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_remote_app_script_profile (remote_app_id),
    INDEX idx_script_profile_enabled (is_enabled),
    FOREIGN KEY (remote_app_id) REFERENCES remote_app(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Worker 节点
CREATE TABLE IF NOT EXISTS worker_node (
    id                           BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id                     VARCHAR(64)  NOT NULL,
    group_id                     BIGINT       NOT NULL,
    display_name                 VARCHAR(200) DEFAULT NULL,
    expected_hostname            VARCHAR(255) NOT NULL,
    hostname                     VARCHAR(255) DEFAULT NULL,
    machine_fingerprint          VARCHAR(128) DEFAULT NULL,
    agent_version                VARCHAR(50)  DEFAULT NULL,
    os_type                      VARCHAR(50)  NOT NULL DEFAULT 'windows',
    os_version                   VARCHAR(100) DEFAULT NULL,
    scratch_root                 VARCHAR(500) DEFAULT NULL,
    workspace_share              VARCHAR(500) DEFAULT NULL,
    max_concurrent_tasks         INT          NOT NULL DEFAULT 1,
    status                       VARCHAR(30)  NOT NULL DEFAULT 'pending_enrollment' COMMENT 'pending_enrollment/active/offline/disabled/revoked',
    last_seen_at                 DATETIME     DEFAULT NULL,
    last_heartbeat_at            DATETIME     DEFAULT NULL,
    last_ip                      VARCHAR(45)  DEFAULT NULL,
    last_error                   VARCHAR(500) DEFAULT NULL,
    runtime_state_json           JSON         DEFAULT NULL,
    supported_executor_keys_json JSON         DEFAULT NULL,
    capabilities_json            JSON         DEFAULT NULL,
    created_at                   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_worker_agent_id (agent_id),
    UNIQUE KEY uk_worker_group_expected_hostname (group_id, expected_hostname),
    INDEX idx_worker_group_status (group_id, status),
    FOREIGN KEY (group_id) REFERENCES worker_group(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Worker 注册码
CREATE TABLE IF NOT EXISTS worker_enrollment (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    worker_node_id   BIGINT       NOT NULL,
    token_hash       CHAR(64)     NOT NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'issued' COMMENT 'issued/consumed/expired/revoked',
    issued_by        BIGINT       DEFAULT NULL,
    issued_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at       DATETIME     NOT NULL,
    consumed_at      DATETIME     DEFAULT NULL,
    consumed_from_ip VARCHAR(45)  DEFAULT NULL,
    revoked_at       DATETIME     DEFAULT NULL,
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_worker_enrollment_hash (token_hash),
    INDEX idx_worker_enrollment_status (worker_node_id, status),
    FOREIGN KEY (worker_node_id) REFERENCES worker_node(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Worker 访问令牌
CREATE TABLE IF NOT EXISTS worker_auth_token (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    worker_node_id BIGINT      NOT NULL,
    token_hash    CHAR(64)     NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT 'active/rotated/revoked',
    issued_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    DATETIME     DEFAULT NULL,
    revoked_at    DATETIME     DEFAULT NULL,
    last_used_at  DATETIME     DEFAULT NULL,
    last_used_ip  VARCHAR(45)  DEFAULT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_worker_auth_token_hash (token_hash),
    INDEX idx_worker_auth_node_status (worker_node_id, status),
    FOREIGN KEY (worker_node_id) REFERENCES worker_node(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 平台任务
CREATE TABLE IF NOT EXISTS platform_task (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id             VARCHAR(64)   NOT NULL,
    user_id             BIGINT        NOT NULL,
    app_id              BIGINT        DEFAULT NULL,
    binding_id          BIGINT        DEFAULT NULL,
    task_kind           VARCHAR(50)   NOT NULL COMMENT 'script_run/gui_launch_request/external_app_task',
    executor_key        VARCHAR(100)  DEFAULT NULL,
    resource_pool_id    BIGINT        DEFAULT NULL,
    worker_group_id     BIGINT        DEFAULT NULL,
    worker_node_id      BIGINT        DEFAULT NULL,
    requested_runtime_id BIGINT       DEFAULT NULL,
    assigned_runtime_id BIGINT        DEFAULT NULL,
    entry_path          VARCHAR(1000) DEFAULT NULL,
    workspace_path      VARCHAR(1000) DEFAULT NULL,
    input_snapshot_path VARCHAR(1000) DEFAULT NULL,
    scratch_path        VARCHAR(1000) DEFAULT NULL,
    status              VARCHAR(30)   NOT NULL DEFAULT 'submitted' COMMENT 'submitted/queued/assigned/preparing/running/uploading/succeeded/failed/cancelled',
    external_task_id    VARCHAR(200)  DEFAULT NULL,
    cancel_requested    TINYINT(1)    NOT NULL DEFAULT 0,
    params_json         JSON          DEFAULT NULL,
    result_summary_json JSON          DEFAULT NULL,
    created_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_at         DATETIME      DEFAULT NULL,
    started_at          DATETIME      DEFAULT NULL,
    ended_at            DATETIME      DEFAULT NULL,
    UNIQUE KEY uk_platform_task_task_id (task_id),
    INDEX idx_platform_task_status (status, created_at),
    INDEX idx_platform_task_worker (worker_node_id, status),
    INDEX idx_platform_task_pool (resource_pool_id, status),
    FOREIGN KEY (app_id) REFERENCES catalog_app(id) ON DELETE SET NULL,
    FOREIGN KEY (binding_id) REFERENCES app_binding(id) ON DELETE SET NULL,
    FOREIGN KEY (resource_pool_id) REFERENCES resource_pool(id) ON DELETE SET NULL,
    FOREIGN KEY (worker_group_id) REFERENCES worker_group(id) ON DELETE SET NULL,
    FOREIGN KEY (worker_node_id) REFERENCES worker_node(id) ON DELETE SET NULL,
    FOREIGN KEY (requested_runtime_id) REFERENCES remote_app(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_runtime_id) REFERENCES remote_app(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 平台任务日志
CREATE TABLE IF NOT EXISTS platform_task_log (
    id         BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id     BIGINT       NOT NULL,
    seq_no     BIGINT       NOT NULL,
    level      VARCHAR(20)  NOT NULL DEFAULT 'info',
    message    TEXT         NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_platform_task_log_seq (task_id, seq_no),
    INDEX idx_platform_task_log_created (task_id, created_at),
    FOREIGN KEY (task_id) REFERENCES platform_task(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 平台任务产物
CREATE TABLE IF NOT EXISTS platform_task_artifact (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id          BIGINT        NOT NULL,
    artifact_kind    VARCHAR(30)   NOT NULL COMMENT 'workspace_output/minio_archive/external_link',
    display_name     VARCHAR(255)  NOT NULL,
    relative_path    VARCHAR(1000) DEFAULT NULL,
    minio_bucket     VARCHAR(255)  DEFAULT NULL,
    minio_object_key VARCHAR(1000) DEFAULT NULL,
    external_url     VARCHAR(1000) DEFAULT NULL,
    size_bytes       BIGINT        DEFAULT NULL,
    created_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_platform_task_artifact_kind (task_id, artifact_kind),
    FOREIGN KEY (task_id) REFERENCES platform_task(id) ON DELETE CASCADE
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
