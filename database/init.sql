-- ============================================
-- Guacamole RemoteApp 门户 - 数据库初始化
-- 数据库: guacamole_portal_db
-- 编码: UTF-8, 引擎: InnoDB
-- ============================================

CREATE DATABASE IF NOT EXISTS guacamole_portal_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE guacamole_portal_db;

-- RemoteApp 应用配置表
CREATE TABLE IF NOT EXISTS remote_app (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(200)  NOT NULL             COMMENT '显示名称',
    icon            VARCHAR(100)  DEFAULT 'desktop'    COMMENT '图标标识',
    protocol        VARCHAR(20)   NOT NULL DEFAULT 'rdp',
    hostname        VARCHAR(255)  NOT NULL,
    port            INT           NOT NULL DEFAULT 3389,
    rdp_username    VARCHAR(100)                       COMMENT 'RDP 登录用户名',
    rdp_password    VARCHAR(200)                       COMMENT 'RDP 登录密码',
    domain          VARCHAR(100)  DEFAULT '',
    security        VARCHAR(20)   DEFAULT 'nla'        COMMENT 'nla/tls/rdp/any',
    ignore_cert     TINYINT(1)    DEFAULT 1,
    remote_app      VARCHAR(200)                       COMMENT 'RemoteApp，如 ||notepad',
    remote_app_dir  VARCHAR(500)                       COMMENT 'RemoteApp 工作目录',
    remote_app_args VARCHAR(500)                       COMMENT 'RemoteApp 命令行参数',
    is_active       TINYINT(1)    DEFAULT 1,
    created_at      DATETIME      DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户-应用 访问控制表
CREATE TABLE IF NOT EXISTS remote_app_acl (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id     BIGINT NOT NULL                        COMMENT '用户ID（PoC阶段固定为1）',
    app_id      BIGINT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_app (user_id, app_id),
    FOREIGN KEY (app_id) REFERENCES remote_app(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 示例数据（请根据实际环境修改 hostname/密码）
-- ============================================

INSERT INTO remote_app (name, icon, hostname, port, rdp_username, rdp_password, remote_app)
VALUES
    ('记事本',   'edit',      '192.168.1.8', 3389, 'admin', 'password', '||notepad'),
    ('计算器',   'calculate', '192.168.1.8', 3389, 'admin', 'password', '||calc'),
    ('远程桌面', 'desktop',   '192.168.1.8', 3389, 'admin', 'password', NULL);

-- 给 PoC 用户 (user_id=1) 分配所有应用
INSERT INTO remote_app_acl (user_id, app_id)
SELECT 1, id FROM remote_app;
