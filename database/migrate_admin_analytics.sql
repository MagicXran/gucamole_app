ALTER TABLE portal_user
    ADD COLUMN department VARCHAR(100) NOT NULL DEFAULT '' COMMENT '所属部门' AFTER display_name;
