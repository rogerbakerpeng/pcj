-- 常用查询（TODO 按实际表结构）
-- 标段状态
SELECT id, section_code, status FROM TODO_section WHERE section_code = :code;
-- 投标人与报价
SELECT bidder_name, price FROM TODO_bid WHERE section_id = :sid;
-- 评标结果
SELECT bidder_name, ranking, score, price FROM TODO_eval_result WHERE section_id = :sid;
-- 接口日志（取 ①② 报文样例的地方）
SELECT * FROM TODO_interface_log WHERE biz_key = :code ORDER BY create_time DESC;
