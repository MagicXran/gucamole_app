/*!40101 SET NAMES utf8mb4 */;

USE guacamole_portal_db;

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
