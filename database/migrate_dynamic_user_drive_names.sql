-- 将固定 UNC 名称升级为按 Portal 用户动态展开的资料空间名称。
SET NAMES utf8mb4;
USE guacamole_portal_db;

UPDATE vscode_control_profile
SET default_workspace_template = '\\\\tsclient\\{user_drive}',
    revision = revision + 1,
    updated_at = CURRENT_TIMESTAMP
WHERE default_workspace_template <> '\\\\tsclient\\{user_drive}';

UPDATE remote_app
SET remote_app_dir = NULL
WHERE remote_app_dir IN (
    '\\\\tsclient\\GuacDrive',
    '\\\\tsclient\\用户数据目录'
);

-- 旧 JSON Auth token 包含旧 drive-name；必须全部失效。
DELETE FROM token_cache;
