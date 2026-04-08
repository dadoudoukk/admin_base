-- 软删除字段：在 MySQL / MariaDB 中直接执行（执行前请备份数据库）
-- 若某列已存在，对应语句会报错，可跳过该表或先手动检查 information_schema

-- sys_user
ALTER TABLE sys_user
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- sys_role
ALTER TABLE sys_role
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- sys_menu
ALTER TABLE sys_menu
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- sys_dict_type
ALTER TABLE sys_dict_type
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- sys_dict_data
ALTER TABLE sys_dict_data
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- biz_news_category
ALTER TABLE biz_news_category
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- biz_news_article
ALTER TABLE biz_news_article
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- biz_fragment_category
ALTER TABLE biz_fragment_category
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- biz_fragment_content
ALTER TABLE biz_fragment_content
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';

-- sys_oper_log
ALTER TABLE sys_oper_log
    ADD COLUMN is_delete INT NOT NULL DEFAULT 0 COMMENT '是否删除 0-否 1-是',
    ADD COLUMN delete_time DATETIME NULL COMMENT '删除时间';
