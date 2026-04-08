-- MySQL / MariaDB：删除与软删除冲突的单列/联合唯一索引（执行前请备份库）
-- 说明：ORM 已去掉 unique=True / UniqueConstraint，查重由路由层 + is_delete 控制
-- 若索引名与库中实际不一致，可先执行：SHOW INDEX FROM 表名;

DELIMITER //

DROP PROCEDURE IF EXISTS geeker_drop_unique_on_column//

CREATE PROCEDURE geeker_drop_unique_on_column(IN p_table VARCHAR(64), IN p_column VARCHAR(64))
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE v_idx VARCHAR(128);
    DECLARE cur CURSOR FOR
        SELECT DISTINCT INDEX_NAME
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = p_table
          AND COLUMN_NAME = p_column
          AND NON_UNIQUE = 0
          AND INDEX_NAME <> 'PRIMARY'
          AND SEQ_IN_INDEX = 1;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN cur;
    idx_loop: LOOP
        FETCH cur INTO v_idx;
        IF done THEN
            LEAVE idx_loop;
        END IF;
        SET @ddl = CONCAT('ALTER TABLE `', p_table, '` DROP INDEX `', v_idx, '`');
        PREPARE stmt FROM @ddl;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END LOOP;
    CLOSE cur;
END//

DELIMITER ;

-- sys_user.username
CALL geeker_drop_unique_on_column('sys_user', 'username');

-- sys_role.name / sys_role.code
CALL geeker_drop_unique_on_column('sys_role', 'name');
CALL geeker_drop_unique_on_column('sys_role', 'code');

-- sys_dict_type.dict_code（模型字段为 dict_code，非 dict_type）
CALL geeker_drop_unique_on_column('sys_dict_type', 'dict_code');

-- sys_dict_data：联合唯一 (dict_code, dict_value)，首列为 dict_code 时即可定位该索引
CALL geeker_drop_unique_on_column('sys_dict_data', 'dict_code');

-- biz_news_category.category_name
CALL geeker_drop_unique_on_column('biz_news_category', 'category_name');

-- biz_fragment_category.code
CALL geeker_drop_unique_on_column('biz_fragment_category', 'code');

DROP PROCEDURE IF EXISTS geeker_drop_unique_on_column;

-- 建议：删除唯一索引后，为常用查询列补非唯一索引（若 DROP 后已无索引且执行报错则说明已存在，可忽略）
CREATE INDEX ix_sys_user_username ON sys_user (username);
CREATE INDEX ix_sys_role_name ON sys_role (name);
CREATE INDEX ix_sys_role_code ON sys_role (code);
CREATE INDEX ix_sys_dict_type_dict_code ON sys_dict_type (dict_code);
CREATE INDEX ix_biz_news_category_category_name ON biz_news_category (category_name);
CREATE INDEX ix_biz_fragment_category_code ON biz_fragment_category (code);
