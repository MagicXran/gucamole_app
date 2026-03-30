/*!40101 SET NAMES utf8mb4 */;

-- RemoteApp 启动预设与固定文件参数迁移
-- MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，用存储过程逐列检查
DELIMITER $$
DROP PROCEDURE IF EXISTS _migrate_remote_app_launch_presets$$
CREATE PROCEDURE _migrate_remote_app_launch_presets()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'launch_preset'
    ) THEN
        ALTER TABLE remote_app
            ADD COLUMN launch_preset VARCHAR(50) NOT NULL DEFAULT 'custom' COMMENT '启动预设'
            AFTER remote_app_args;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'server_file_path'
    ) THEN
        ALTER TABLE remote_app
            ADD COLUMN server_file_path VARCHAR(500) DEFAULT NULL COMMENT '服务器端固定文件路径'
            AFTER launch_preset;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'launch_arg_template'
    ) THEN
        ALTER TABLE remote_app
            ADD COLUMN launch_arg_template VARCHAR(500) DEFAULT NULL COMMENT '启动参数模板'
            AFTER server_file_path;
    END IF;
END$$
DELIMITER ;
CALL _migrate_remote_app_launch_presets();
DROP PROCEDURE IF EXISTS _migrate_remote_app_launch_presets;
