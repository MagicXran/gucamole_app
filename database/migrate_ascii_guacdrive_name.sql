-- 回退到 ASCII RDPDR 共享名，避免 Guacamole 1.6.0 截断多字节 UTF-8 名称。
SET NAMES utf8mb4;
USE guacamole_portal_db;

UPDATE remote_app
SET remote_app_dir = NULL
WHERE remote_app_dir = '\\\\tsclient\\用户数据目录';

DELETE FROM token_cache;
