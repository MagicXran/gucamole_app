-- 用户数据目录 一般限制：安全模式与受限 VSCode 控制策略
/*!40101 SET NAMES utf8mb4 */;
USE guacamole_portal_db;

CREATE TABLE IF NOT EXISTS vscode_control_profile (
    id                           BIGINT PRIMARY KEY AUTO_INCREMENT,
    profile_key                  VARCHAR(100) NOT NULL,
    display_name                 VARCHAR(200) NOT NULL,
    description                  VARCHAR(1000) NOT NULL DEFAULT '',
    policy_version               INT NOT NULL DEFAULT 1,
    is_active                    TINYINT(1) NOT NULL DEFAULT 0,
    revision                     INT NOT NULL DEFAULT 1,
    permissions_json             JSON NOT NULL,
    allowed_shells_json          JSON NOT NULL,
    allowed_tools_json           JSON NOT NULL,
    allowed_debuggers_json       JSON NOT NULL,
    allowed_extensions_json      JSON NOT NULL,
    allowed_network_targets_json JSON NOT NULL,
    user_data_root               VARCHAR(500) NOT NULL,
    extensions_root              VARCHAR(500) NOT NULL,
    default_workspace_template   VARCHAR(500) NOT NULL,
    created_at                   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_vscode_control_profile_key (profile_key),
    INDEX idx_vscode_control_profile_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS migrate_access_security_modes;
DELIMITER $$
CREATE PROCEDURE migrate_access_security_modes()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'security_mode'
    ) THEN
        ALTER TABLE remote_app
            ADD COLUMN security_mode VARCHAR(40) NULL AFTER remote_app_args;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND COLUMN_NAME = 'vscode_control_profile_id'
    ) THEN
        ALTER TABLE remote_app
            ADD COLUMN vscode_control_profile_id BIGINT NULL AFTER security_mode;
    END IF;

    UPDATE remote_app
    SET security_mode = CASE
        WHEN remote_app IS NULL OR TRIM(remote_app) = '' THEN 'admin_desktop'
        WHEN LOWER(name) LIKE '%vscode%'
          OR LOWER(name) LIKE '%visual studio code%'
          OR LOWER(COALESCE(remote_app, '')) LIKE '%visual studio code%'
            THEN 'restricted_vscode'
        ELSE 'restricted_remoteapp'
    END
    WHERE security_mode IS NULL
       OR security_mode NOT IN ('restricted_remoteapp', 'restricted_vscode', 'admin_desktop');

    ALTER TABLE remote_app
        MODIFY COLUMN security_mode VARCHAR(40) NOT NULL DEFAULT 'restricted_remoteapp';

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app' AND INDEX_NAME = 'idx_security_mode_active'
    ) THEN
        ALTER TABLE remote_app ADD INDEX idx_security_mode_active (security_mode, is_active);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.REFERENTIAL_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'remote_app'
          AND CONSTRAINT_NAME = 'fk_remote_app_vscode_control_profile'
    ) THEN
        ALTER TABLE remote_app
            ADD CONSTRAINT fk_remote_app_vscode_control_profile
            FOREIGN KEY (vscode_control_profile_id) REFERENCES vscode_control_profile(id)
            ON DELETE RESTRICT;
    END IF;
END$$
DELIMITER ;

CALL migrate_access_security_modes();
DROP PROCEDURE migrate_access_security_modes;

INSERT IGNORE INTO vscode_control_profile (
    profile_key, display_name, description, policy_version, is_active, revision,
    permissions_json, allowed_shells_json, allowed_tools_json, allowed_debuggers_json,
    allowed_extensions_json, allowed_network_targets_json,
    user_data_root, extensions_root, default_workspace_template
) VALUES (
    'default-controlled',
    '默认受控开发模式',
    '全部可授予权限默认勾选；补齐程序、扩展和网络白名单后才能启用。',
    1,
    0,
    1,
    JSON_OBJECT(
        'workspace_file_ops', TRUE, 'multi_root_workspace', TRUE,
        'user_settings', TRUE, 'workspace_settings', TRUE, 'keybindings', TRUE, 'snippets', TRUE,
        'terminal', TRUE, 'tasks', TRUE, 'run', TRUE, 'build', TRUE, 'debug', TRUE,
        'git_local', TRUE, 'git_remote', TRUE, 'package_install', TRUE,
        'extension_use', TRUE, 'extension_install_update', TRUE,
        'ai_chat', TRUE, 'agent_mode', TRUE, 'mcp_tools', TRUE,
        'integrated_browser', TRUE, 'port_forwarding', TRUE, 'remote_development', TRUE,
        'copy_remote_to_local', TRUE, 'paste_local_to_remote', TRUE,
        'browser_upload', TRUE, 'browser_download', TRUE,
        'printing', TRUE, 'audio_output', TRUE, 'audio_input', TRUE,
        'network_git', TRUE, 'network_packages', TRUE, 'network_business', TRUE, 'network_https', TRUE
    ),
    JSON_ARRAY(), JSON_ARRAY(), JSON_ARRAY(), JSON_ARRAY(), JSON_ARRAY(),
    'C:\\PortalProfiles', 'C:\\PortalExtensions', '\\\\tsclient\\{user_drive}'
);

-- 普通用户不保留管理员桌面的旧 ACL；管理员 ACL 保持不变。
DELETE acl
FROM remote_app_acl acl
JOIN portal_user u ON u.id = acl.user_id
JOIN remote_app a ON a.id = acl.app_id
WHERE u.is_admin = 0
  AND a.security_mode = 'admin_desktop';
