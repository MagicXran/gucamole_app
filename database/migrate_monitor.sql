/*!40101 SET NAMES utf8mb4 */;

USE guacamole_portal_db;

-- 活跃会话追踪表 (实时监控)
CREATE TABLE IF NOT EXISTS active_session (
    id             BIGINT       PRIMARY KEY AUTO_INCREMENT,
    session_id     VARCHAR(36)  NOT NULL UNIQUE  COMMENT 'UUID v4, 心跳凭证',
    user_id        BIGINT       NOT NULL,
    app_id         BIGINT       NOT NULL,
    started_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at       DATETIME     NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT 'active/disconnected',
    INDEX idx_status (status),
    INDEX idx_app_status (app_id, status),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
