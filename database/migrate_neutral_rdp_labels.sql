-- 将用户可见的 RDPDR 共享名统一为中文“用户空间”。
SET NAMES utf8mb4;
USE guacamole_portal_db;

-- 自动工作目录由启动链按当前 drive-name 统一展开；显式业务目录保持不变。
UPDATE remote_app
SET remote_app_dir = NULL
WHERE remote_app_dir IN (
    '\\\\tsclient\\GuacDrive',
    '\\\\tsclient\\用户数据目录',
    '\\\\tsclient\\UserFiles',
    '\\\\tsclient\\用户空间'
);

-- JSON Auth token 内包含 client-name、drive-name 和 remote-app-dir。
DELETE FROM token_cache;
