CREATE TABLE IF NOT EXISTS portal_comment (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    target_type  VARCHAR(20)   NOT NULL COMMENT 'app/case',
    target_id    BIGINT        NOT NULL,
    user_id      BIGINT        NOT NULL,
    content      VARCHAR(2000) NOT NULL,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_portal_comment_target (target_type, target_id, created_at, id),
    INDEX idx_portal_comment_user (user_id, created_at),
    FOREIGN KEY (user_id) REFERENCES portal_user(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
