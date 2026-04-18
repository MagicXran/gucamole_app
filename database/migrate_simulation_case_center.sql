/*!40101 SET NAMES utf8mb4 */;
/*!40101 SET CHARACTER_SET_CLIENT=utf8mb4 */;
/*!40101 SET CHARACTER_SET_RESULTS=utf8mb4 */;

USE guacamole_portal_db;

CREATE TABLE IF NOT EXISTS simulation_case (
    id                   BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_uid             VARCHAR(64)   NOT NULL,
    title                VARCHAR(200)  NOT NULL,
    summary              VARCHAR(1000) DEFAULT '',
    app_id               BIGINT        DEFAULT NULL,
    visibility           VARCHAR(20)   NOT NULL DEFAULT 'public' COMMENT 'public/private',
    status               VARCHAR(20)   NOT NULL DEFAULT 'published' COMMENT 'draft/published/archived',
    published_by_user_id BIGINT        NOT NULL,
    published_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_simulation_case_uid (case_uid),
    INDEX idx_simulation_case_app_status (app_id, status, visibility),
    FOREIGN KEY (app_id) REFERENCES catalog_app(id) ON DELETE SET NULL,
    FOREIGN KEY (published_by_user_id) REFERENCES portal_user(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS simulation_case_source (
    id                    BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id               BIGINT       NOT NULL,
    source_type           VARCHAR(30)  NOT NULL COMMENT 'platform_task/manual_upload',
    source_task_id        BIGINT       DEFAULT NULL,
    source_task_public_id VARCHAR(64)  DEFAULT NULL,
    source_user_id        BIGINT       DEFAULT NULL,
    source_status         VARCHAR(30)  DEFAULT NULL,
    source_summary_json   JSON         DEFAULT NULL,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_case_source_case (case_id),
    INDEX idx_case_source_task (source_task_id),
    FOREIGN KEY (case_id) REFERENCES simulation_case(id) ON DELETE CASCADE,
    FOREIGN KEY (source_task_id) REFERENCES platform_task(id) ON DELETE SET NULL,
    FOREIGN KEY (source_user_id) REFERENCES portal_user(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS simulation_case_package (
    id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id            BIGINT        NOT NULL,
    package_root       VARCHAR(1000) NOT NULL,
    archive_path       VARCHAR(1000) NOT NULL,
    archive_size_bytes BIGINT        NOT NULL DEFAULT 0,
    asset_count        INT           NOT NULL DEFAULT 0,
    created_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_simulation_case_package_case (case_id),
    FOREIGN KEY (case_id) REFERENCES simulation_case(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS simulation_case_asset (
    id                    BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id               BIGINT        NOT NULL,
    source_artifact_id    BIGINT        DEFAULT NULL,
    asset_kind            VARCHAR(30)   NOT NULL COMMENT 'workspace_output/minio_archive/external_link',
    display_name          VARCHAR(255)  NOT NULL,
    package_relative_path VARCHAR(1000) NOT NULL,
    size_bytes            BIGINT        DEFAULT NULL,
    sort_order            INT           NOT NULL DEFAULT 0,
    created_at            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_simulation_case_asset_case (case_id, sort_order, id),
    FOREIGN KEY (case_id) REFERENCES simulation_case(id) ON DELETE CASCADE,
    FOREIGN KEY (source_artifact_id) REFERENCES platform_task_artifact(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
