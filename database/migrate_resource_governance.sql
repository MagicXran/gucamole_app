-- ============================================
-- Resource Governance 数据库迁移
-- 对已有环境: 新增 remote_app 治理列 + launch_queue 表
-- 对全新环境: 直接使用 init.sql 即可
-- ============================================

USE guacamole_portal_db;

-- 1. remote_app.max_concurrent_sessions
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'guacamole_portal_db'
      AND TABLE_NAME = 'remote_app'
      AND COLUMN_NAME = 'max_concurrent_sessions'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE remote_app ADD COLUMN max_concurrent_sessions INT DEFAULT NULL COMMENT ''应用级最大并发会话数, NULL/<=0=不限制'' AFTER keyboard_layout',
    'SELECT ''max_concurrent_sessions column already exists'' AS info'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. remote_app.max_concurrent_per_user
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'guacamole_portal_db'
      AND TABLE_NAME = 'remote_app'
      AND COLUMN_NAME = 'max_concurrent_per_user'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE remote_app ADD COLUMN max_concurrent_per_user INT DEFAULT NULL COMMENT ''单用户最大并发会话数, NULL/<=0=不限制'' AFTER max_concurrent_sessions',
    'SELECT ''max_concurrent_per_user column already exists'' AS info'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. remote_app.queue_enabled
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'guacamole_portal_db'
      AND TABLE_NAME = 'remote_app'
      AND COLUMN_NAME = 'queue_enabled'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE remote_app ADD COLUMN queue_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''达到上限后是否进入排队'' AFTER max_concurrent_per_user',
    'SELECT ''queue_enabled column already exists'' AS info'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4. remote_app.queue_timeout_seconds（如果已有旧列 queue_ttl_seconds，则重命名）
SET @timeout_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'guacamole_portal_db'
      AND TABLE_NAME = 'remote_app'
      AND COLUMN_NAME = 'queue_timeout_seconds'
);
SET @legacy_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'guacamole_portal_db'
      AND TABLE_NAME = 'remote_app'
      AND COLUMN_NAME = 'queue_ttl_seconds'
);
SET @sql = IF(
    @timeout_exists = 0 AND @legacy_exists > 0,
    'ALTER TABLE remote_app CHANGE COLUMN queue_ttl_seconds queue_timeout_seconds INT NOT NULL DEFAULT 300 COMMENT ''排队条目过期秒数''',
    IF(
        @timeout_exists = 0,
        'ALTER TABLE remote_app ADD COLUMN queue_timeout_seconds INT NOT NULL DEFAULT 300 COMMENT ''排队条目过期秒数'' AFTER queue_enabled',
        'SELECT ''queue_timeout_seconds column already exists'' AS info'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5. 创建 launch_queue 表（幂等）
CREATE TABLE IF NOT EXISTS launch_queue (
    id             BIGINT PRIMARY KEY AUTO_INCREMENT,
    app_id         BIGINT      NOT NULL,
    user_id        BIGINT      NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'waiting' COMMENT 'waiting/expired/cancelled',
    created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_app_status_created (app_id, status, created_at, id),
    INDEX idx_user_status (user_id, status),
    FOREIGN KEY (app_id) REFERENCES remote_app(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'Resource governance migration complete' AS result;
