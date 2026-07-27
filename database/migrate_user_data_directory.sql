-- 统一 Guacamole 映射盘名称，并为 RemoteApp 补齐默认工作目录。
SET NAMES utf8mb4;
USE guacamole_portal_db;

UPDATE vscode_control_profile
SET default_workspace_template = '\\\\tsclient\\用户数据目录',
    revision = revision + 1,
    updated_at = CURRENT_TIMESTAMP
WHERE default_workspace_template <> '\\\\tsclient\\用户数据目录';

UPDATE remote_app
SET remote_app_dir = '\\\\tsclient\\用户数据目录'
WHERE COALESCE(TRIM(remote_app), '') <> ''
  AND COALESCE(TRIM(remote_app_dir), '') = '';

-- JSON Auth token 内含 drive-name/remote-app-dir；旧 token 必须失效。
DELETE FROM token_cache;
