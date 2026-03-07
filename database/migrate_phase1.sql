-- ============================================
-- Phase 1 数据库迁移
-- 对已有环境: 新增 is_admin 字段 + audit_log 表
-- 对全新环境: 直接用 init.sql 即可，无需此脚本
--
-- 执行方式:
--   docker exec -i nercar-portal-guac-sql mysql -uroot -p${MYSQL_ROOT_PASSWORD} \
--     --default-character-set=utf8mb4 guacamole_portal_db < database/migrate_phase1.sql
-- ============================================

USE guacamole_portal_db;

-- 1. portal_user 表增加 is_admin 字段（幂等）
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'guacamole_portal_db'
      AND TABLE_NAME = 'portal_user'
      AND COLUMN_NAME = 'is_admin'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE portal_user ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''是否管理员'' AFTER display_name',
    'SELECT ''is_admin column already exists'' AS info'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. 将 admin 用户设为管理员
UPDATE portal_user SET is_admin = 1 WHERE username = 'admin';

-- 3. 创建审计日志表（幂等）
CREATE TABLE IF NOT EXISTS audit_log (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT       NOT NULL                COMMENT '操作者用户ID',
    username     VARCHAR(64)  NOT NULL                COMMENT '操作者用户名（冗余）',
    action       VARCHAR(50)  NOT NULL                COMMENT '动作类型',
    target_type  VARCHAR(50)  DEFAULT NULL            COMMENT '目标类型 (app/user/acl)',
    target_id    BIGINT       DEFAULT NULL            COMMENT '目标ID',
    target_name  VARCHAR(200) DEFAULT NULL            COMMENT '目标名称（冗余）',
    detail       TEXT         DEFAULT NULL            COMMENT 'JSON 额外信息',
    ip_address   VARCHAR(45)  DEFAULT NULL            COMMENT '客户端 IP',
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'Phase 1 migration complete' AS result;
