/*!40101 SET NAMES utf8mb4 */;

-- RDP 高级参数迁移 (12 列)
-- MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，用存储过程逐列检查
DELIMITER $$
DROP PROCEDURE IF EXISTS _migrate_rdp_params$$
CREATE PROCEDURE _migrate_rdp_params()
BEGIN
    -- 显示与性能
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'color_depth'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN color_depth INT DEFAULT NULL COMMENT '色深: 8/16/24, NULL=自动' AFTER remote_app_args;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'disable_gfx'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN disable_gfx TINYINT(1) DEFAULT 1 COMMENT '禁用 GFX Pipeline' AFTER color_depth;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'resize_method'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN resize_method VARCHAR(20) DEFAULT 'display-update' COMMENT 'display-update/reconnect' AFTER disable_gfx;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'enable_wallpaper'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN enable_wallpaper TINYINT(1) DEFAULT 0 COMMENT '显示桌面壁纸' AFTER resize_method;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'enable_font_smoothing'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN enable_font_smoothing TINYINT(1) DEFAULT 1 COMMENT 'ClearType 字体平滑' AFTER enable_wallpaper;
    END IF;

    -- 安全与剪贴板
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'disable_copy'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN disable_copy TINYINT(1) DEFAULT 0 COMMENT '禁止从远程复制到本地' AFTER enable_font_smoothing;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'disable_paste'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN disable_paste TINYINT(1) DEFAULT 0 COMMENT '禁止从本地粘贴到远程' AFTER disable_copy;
    END IF;

    -- 音频
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'enable_audio'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN enable_audio TINYINT(1) DEFAULT 1 COMMENT '音频输出' AFTER disable_paste;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'enable_audio_input'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN enable_audio_input TINYINT(1) DEFAULT 0 COMMENT '麦克风输入' AFTER enable_audio;
    END IF;

    -- 设备
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'enable_printing'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN enable_printing TINYINT(1) DEFAULT 0 COMMENT '虚拟打印机(PDF)' AFTER enable_audio_input;
    END IF;

    -- 本地化
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'timezone'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN timezone VARCHAR(50) DEFAULT NULL COMMENT '时区, 如 Asia/Shanghai' AFTER enable_printing;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'keyboard_layout'
    ) THEN
        ALTER TABLE remote_app ADD COLUMN keyboard_layout VARCHAR(50) DEFAULT NULL COMMENT '键盘布局' AFTER timezone;
    END IF;
END$$
DELIMITER ;
CALL _migrate_rdp_params();
DROP PROCEDURE IF EXISTS _migrate_rdp_params;
