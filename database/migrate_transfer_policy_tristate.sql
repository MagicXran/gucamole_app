-- 迁移目标：RemoteApp 文件传输策略改为 tri-state
-- NULL = 继承全局，1 = 强制禁用，0 = 强制允许

SET @disable_download_default_before = (
    SELECT COLUMN_DEFAULT
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'remote_app'
      AND COLUMN_NAME = 'disable_download'
    LIMIT 1
);

SET @disable_upload_default_before = (
    SELECT COLUMN_DEFAULT
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'remote_app'
      AND COLUMN_NAME = 'disable_upload'
    LIMIT 1
);

SET @add_disable_download_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'remote_app'
              AND COLUMN_NAME = 'disable_download'
        ),
        'SELECT 1',
        'ALTER TABLE remote_app ADD COLUMN disable_download TINYINT(1) NULL DEFAULT NULL COMMENT ''禁用下载到本地'' AFTER enable_printing'
    )
);
PREPARE add_disable_download_stmt FROM @add_disable_download_sql;
EXECUTE add_disable_download_stmt;
DEALLOCATE PREPARE add_disable_download_stmt;

SET @add_disable_upload_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'remote_app'
              AND COLUMN_NAME = 'disable_upload'
        ),
        'SELECT 1',
        'ALTER TABLE remote_app ADD COLUMN disable_upload TINYINT(1) NULL DEFAULT NULL COMMENT ''禁用本地上传到远程'' AFTER disable_download'
    )
);
PREPARE add_disable_upload_stmt FROM @add_disable_upload_sql;
EXECUTE add_disable_upload_stmt;
DEALLOCATE PREPARE add_disable_upload_stmt;

ALTER TABLE remote_app
    MODIFY COLUMN disable_download TINYINT(1) DEFAULT NULL COMMENT '禁用下载到本地',
    MODIFY COLUMN disable_upload TINYINT(1) DEFAULT NULL COMMENT '禁用本地上传到远程';

-- 历史默认值 0 实际表示“继承全局”，只在旧列默认值确实是 0 时做一次性清洗
SET @normalize_disable_download_sql = IF(
    @disable_download_default_before = '0',
    'UPDATE remote_app SET disable_download = NULL WHERE disable_download = 0',
    'SELECT 1'
);
PREPARE normalize_disable_download_stmt FROM @normalize_disable_download_sql;
EXECUTE normalize_disable_download_stmt;
DEALLOCATE PREPARE normalize_disable_download_stmt;

SET @normalize_disable_upload_sql = IF(
    @disable_upload_default_before = '0',
    'UPDATE remote_app SET disable_upload = NULL WHERE disable_upload = 0',
    'SELECT 1'
);
PREPARE normalize_disable_upload_stmt FROM @normalize_disable_upload_sql;
EXECUTE normalize_disable_upload_stmt;
DEALLOCATE PREPARE normalize_disable_upload_stmt;
