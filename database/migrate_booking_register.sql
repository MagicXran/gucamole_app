CREATE TABLE IF NOT EXISTS booking_register (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id       BIGINT       NOT NULL COMMENT '预约用户',
    app_name      VARCHAR(200) NOT NULL COMMENT '预约应用名称',
    scheduled_for DATETIME     NOT NULL COMMENT '预约时间',
    purpose       VARCHAR(255) NOT NULL COMMENT '预约目的',
    note          VARCHAR(1000) DEFAULT '' COMMENT '补充说明',
    status        VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT 'active/cancelled',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at  DATETIME     DEFAULT NULL,
    INDEX idx_booking_user_status_created (user_id, status, created_at),
    INDEX idx_booking_schedule (status, scheduled_for)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
