CREATE TABLE IF NOT EXISTS sdk_package (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    package_kind VARCHAR(30)   NOT NULL COMMENT 'cloud_platform/simulation_app',
    name         VARCHAR(200)  NOT NULL,
    summary      VARCHAR(1000) DEFAULT '',
    homepage_url VARCHAR(1000) DEFAULT '',
    is_active    TINYINT(1)    NOT NULL DEFAULT 1,
    sort_order   INT           NOT NULL DEFAULT 0,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sdk_package_kind_active (package_kind, is_active, sort_order, id),
    CONSTRAINT chk_sdk_package_kind CHECK (package_kind IN ('cloud_platform', 'simulation_app'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sdk_version (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    package_id    BIGINT        NOT NULL,
    version       VARCHAR(100)  NOT NULL,
    release_notes TEXT          NULL,
    released_at   DATETIME      DEFAULT NULL,
    is_active     TINYINT(1)    NOT NULL DEFAULT 1,
    sort_order    INT           NOT NULL DEFAULT 0,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sdk_version_package_version (package_id, version),
    INDEX idx_sdk_version_package_active (package_id, is_active, sort_order, id),
    FOREIGN KEY (package_id) REFERENCES sdk_package(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sdk_asset (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    version_id   BIGINT        NOT NULL,
    asset_kind   VARCHAR(50)   NOT NULL COMMENT 'archive/wheel/docs/example/installer',
    display_name VARCHAR(255)  NOT NULL,
    download_url VARCHAR(1000) NOT NULL,
    size_bytes   BIGINT        DEFAULT NULL,
    is_active    TINYINT(1)    NOT NULL DEFAULT 1,
    sort_order   INT           NOT NULL DEFAULT 0,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sdk_asset_version_active (version_id, is_active, sort_order, id),
    FOREIGN KEY (version_id) REFERENCES sdk_version(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
