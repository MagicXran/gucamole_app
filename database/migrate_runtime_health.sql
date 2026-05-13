CREATE TABLE IF NOT EXISTS remote_app_health (
    remote_app_id          BIGINT PRIMARY KEY,
    health_status          VARCHAR(30)  NOT NULL DEFAULT 'unknown' COMMENT 'unknown/healthy/cooldown/unreachable',
    consecutive_failures   INT          NOT NULL DEFAULT 0,
    cooldown_until         DATETIME     DEFAULT NULL,
    last_failure_at        DATETIME     DEFAULT NULL,
    last_failure_reason    VARCHAR(500) DEFAULT NULL,
    last_success_at        DATETIME     DEFAULT NULL,
    last_probe_at          DATETIME     DEFAULT NULL,
    last_probe_ok          TINYINT(1)   DEFAULT NULL,
    created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (remote_app_id) REFERENCES remote_app(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
