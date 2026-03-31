/*!40101 SET NAMES utf8mb4 */;

DELIMITER $$
DROP PROCEDURE IF EXISTS _migrate_resource_pool_queue$$
CREATE PROCEDURE _migrate_resource_pool_queue()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'remote_app'
          AND COLUMN_NAME = 'pool_id'
    ) THEN
        ALTER TABLE remote_app
            ADD COLUMN pool_id BIGINT DEFAULT NULL COMMENT '所属资源池' AFTER keyboard_layout;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'remote_app'
          AND COLUMN_NAME = 'member_max_concurrent'
    ) THEN
        ALTER TABLE remote_app
            ADD COLUMN member_max_concurrent INT NOT NULL DEFAULT 1 COMMENT '成员并发上限' AFTER pool_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'remote_app'
          AND INDEX_NAME = 'idx_pool_active'
    ) THEN
        ALTER TABLE remote_app
            ADD INDEX idx_pool_active (pool_id, is_active);
    END IF;

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

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'active_session'
          AND COLUMN_NAME = 'pool_id'
    ) THEN
        ALTER TABLE active_session
            ADD COLUMN pool_id BIGINT DEFAULT NULL AFTER app_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'active_session'
          AND COLUMN_NAME = 'queue_id'
    ) THEN
        ALTER TABLE active_session
            ADD COLUMN queue_id BIGINT DEFAULT NULL AFTER pool_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'active_session'
          AND COLUMN_NAME = 'last_activity_at'
    ) THEN
        ALTER TABLE active_session
            ADD COLUMN last_activity_at DATETIME DEFAULT NULL AFTER last_heartbeat;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'active_session'
          AND COLUMN_NAME = 'reclaim_reason'
    ) THEN
        ALTER TABLE active_session
            ADD COLUMN reclaim_reason VARCHAR(20) DEFAULT NULL COMMENT 'stale/idle/admin/manual' AFTER status;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'active_session'
          AND INDEX_NAME = 'idx_pool_status'
    ) THEN
        ALTER TABLE active_session
            ADD INDEX idx_pool_status (pool_id, status);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'active_session'
          AND INDEX_NAME = 'idx_queue'
    ) THEN
        ALTER TABLE active_session
            ADD INDEX idx_queue (queue_id);
    END IF;

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
END$$
DELIMITER ;

CALL _migrate_resource_pool_queue();
DROP PROCEDURE IF EXISTS _migrate_resource_pool_queue;

INSERT INTO resource_pool
    (name, icon, max_concurrent, auto_dispatch_enabled,
     dispatch_grace_seconds, stale_timeout_seconds, idle_timeout_seconds, is_active)
SELECT
    CONCAT('默认池-', a.id, '-', a.name) AS name,
    COALESCE(a.icon, 'desktop')          AS icon,
    1                                    AS max_concurrent,
    1                                    AS auto_dispatch_enabled,
    120                                  AS dispatch_grace_seconds,
    120                                  AS stale_timeout_seconds,
    NULL                                 AS idle_timeout_seconds,
    1                                    AS is_active
FROM remote_app a
LEFT JOIN resource_pool p
    ON p.name = CONCAT('默认池-', a.id, '-', a.name)
WHERE a.pool_id IS NULL
  AND p.id IS NULL;

UPDATE remote_app a
JOIN resource_pool p
    ON p.name = CONCAT('默认池-', a.id, '-', a.name)
SET a.pool_id = p.id
WHERE a.pool_id IS NULL;

UPDATE active_session s
JOIN remote_app a
    ON a.id = s.app_id
SET s.pool_id = a.pool_id
WHERE s.pool_id IS NULL
  AND a.pool_id IS NOT NULL;
