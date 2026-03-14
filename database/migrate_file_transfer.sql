/*!40101 SET NAMES utf8mb4 */;

-- 个人空间配额字段 (NULL = 使用默认配额)
-- MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，用存储过程包装
DELIMITER $$
DROP PROCEDURE IF EXISTS _migrate_add_quota$$
CREATE PROCEDURE _migrate_add_quota()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'portal_user'
          AND COLUMN_NAME = 'quota_bytes'
    ) THEN
        ALTER TABLE portal_user ADD COLUMN quota_bytes BIGINT DEFAULT NULL;
    END IF;
END$$
DELIMITER ;
CALL _migrate_add_quota();
DROP PROCEDURE IF EXISTS _migrate_add_quota;
