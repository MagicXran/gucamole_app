/*!40101 SET NAMES utf8mb4 */;

USE guacamole_portal_db;

DROP PROCEDURE IF EXISTS _migrate_remote_app_app_kind;
DELIMITER $$
CREATE PROCEDURE _migrate_remote_app_app_kind()
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'remote_app'
          AND COLUMN_NAME = 'app_kind'
    ) THEN
        ALTER TABLE remote_app
            ADD COLUMN app_kind VARCHAR(50) NOT NULL DEFAULT 'commercial_software'
            COMMENT 'commercial_software/simulation_app/compute_tool'
            AFTER icon;
    END IF;
END $$
DELIMITER ;

CALL _migrate_remote_app_app_kind();
DROP PROCEDURE IF EXISTS _migrate_remote_app_app_kind;

UPDATE remote_app
SET app_kind = 'commercial_software'
WHERE app_kind IS NULL OR app_kind = '';
