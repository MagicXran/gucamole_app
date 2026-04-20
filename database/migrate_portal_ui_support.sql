-- 增量迁移：补齐 Vue3 门户依赖的业务表/字段

SET @db_name = DATABASE();

SET @has_department = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = 'portal_user'
      AND COLUMN_NAME = 'department'
);
SET @sql = IF(
    @has_department = 0,
    "ALTER TABLE portal_user ADD COLUMN department VARCHAR(100) DEFAULT '' COMMENT '所属部门' AFTER display_name",
    "SELECT 'portal_user.department already exists' AS info"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_app_kind = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = 'remote_app'
      AND COLUMN_NAME = 'app_kind'
);
SET @sql = IF(
    @has_app_kind = 0,
    "ALTER TABLE remote_app ADD COLUMN app_kind VARCHAR(50) NOT NULL DEFAULT 'commercial_software' COMMENT 'commercial_software/simulation_app/compute_tool' AFTER protocol",
    "SELECT 'remote_app.app_kind already exists' AS info"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS booking_register (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id       BIGINT       NOT NULL,
    app_name      VARCHAR(200) NOT NULL,
    scheduled_for DATETIME     NOT NULL,
    purpose       VARCHAR(255) NOT NULL,
    note          VARCHAR(1000) DEFAULT '',
    status        VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at  DATETIME     DEFAULT NULL,
    INDEX idx_booking_user_status (user_id, status, scheduled_for),
    FOREIGN KEY (user_id) REFERENCES portal_user(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS portal_comment (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    target_type VARCHAR(20)  NOT NULL COMMENT 'app/case',
    target_id   BIGINT       NOT NULL,
    user_id     BIGINT       NOT NULL,
    content     TEXT         NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_comment_target (target_type, target_id, created_at),
    INDEX idx_comment_user (user_id, created_at),
    FOREIGN KEY (user_id) REFERENCES portal_user(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_attachment (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    pool_id         BIGINT       NOT NULL,
    attachment_kind VARCHAR(30)  NOT NULL COMMENT 'tutorial_doc/video_resource/plugin_download',
    title           VARCHAR(200) NOT NULL,
    summary         VARCHAR(500) DEFAULT '',
    url             VARCHAR(1000) NOT NULL,
    sort_order      INT          NOT NULL DEFAULT 0,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_app_attachment_pool_kind (pool_id, attachment_kind, is_active, sort_order),
    FOREIGN KEY (pool_id) REFERENCES resource_pool(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS simulation_case (
    id                   BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_uid             VARCHAR(64)  NOT NULL,
    title                VARCHAR(200) NOT NULL,
    summary              VARCHAR(1000) DEFAULT '',
    app_id               BIGINT       DEFAULT NULL,
    visibility           VARCHAR(20)  NOT NULL DEFAULT 'public',
    status               VARCHAR(20)  NOT NULL DEFAULT 'published',
    published_by_user_id BIGINT       NOT NULL,
    published_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_simulation_case_uid (case_uid),
    INDEX idx_simulation_case_visibility (visibility, status, published_at),
    FOREIGN KEY (published_by_user_id) REFERENCES portal_user(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS simulation_case_source (
    id                    BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id               BIGINT       NOT NULL,
    source_type           VARCHAR(30)  NOT NULL,
    source_task_id        BIGINT       DEFAULT NULL,
    source_task_public_id VARCHAR(64)  DEFAULT NULL,
    source_user_id        BIGINT       DEFAULT NULL,
    source_status         VARCHAR(30)  DEFAULT NULL,
    source_summary_json   JSON         DEFAULT NULL,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_case_source_case (case_id),
    FOREIGN KEY (case_id) REFERENCES simulation_case(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS simulation_case_package (
    id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id            BIGINT       NOT NULL,
    package_root       VARCHAR(1000) NOT NULL,
    archive_path       VARCHAR(1000) NOT NULL,
    archive_size_bytes BIGINT       DEFAULT NULL,
    asset_count        INT          NOT NULL DEFAULT 0,
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_case_package_case (case_id),
    FOREIGN KEY (case_id) REFERENCES simulation_case(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS simulation_case_asset (
    id                    BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id               BIGINT       NOT NULL,
    source_artifact_id    BIGINT       DEFAULT NULL,
    asset_kind            VARCHAR(30)  NOT NULL,
    display_name          VARCHAR(255) NOT NULL,
    package_relative_path VARCHAR(1000) NOT NULL,
    size_bytes            BIGINT       DEFAULT NULL,
    sort_order            INT          NOT NULL DEFAULT 0,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_case_asset_case (case_id, sort_order, id),
    FOREIGN KEY (case_id) REFERENCES simulation_case(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sdk_package (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    package_kind VARCHAR(30)  NOT NULL COMMENT 'cloud_platform/simulation_app',
    name         VARCHAR(200) NOT NULL,
    summary      VARCHAR(1000) DEFAULT '',
    homepage_url VARCHAR(1000) DEFAULT '',
    is_active    TINYINT(1)   NOT NULL DEFAULT 1,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sdk_package_kind (package_kind, is_active, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sdk_version (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    package_id     BIGINT       NOT NULL,
    version        VARCHAR(100) NOT NULL,
    release_notes  TEXT         DEFAULT NULL,
    released_at    DATETIME     DEFAULT NULL,
    is_active      TINYINT(1)   NOT NULL DEFAULT 1,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sdk_version_package (package_id, version),
    INDEX idx_sdk_version_package_active (package_id, is_active, released_at),
    FOREIGN KEY (package_id) REFERENCES sdk_package(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sdk_asset (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    version_id    BIGINT       NOT NULL,
    asset_kind    VARCHAR(30)  NOT NULL DEFAULT 'download',
    display_name  VARCHAR(255) NOT NULL,
    download_url  VARCHAR(1000) NOT NULL,
    size_bytes    BIGINT       DEFAULT NULL,
    sort_order    INT          NOT NULL DEFAULT 0,
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sdk_asset_version (version_id, is_active, sort_order),
    FOREIGN KEY (version_id) REFERENCES sdk_version(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
