"""按前缀清理自动化数据。注意顺序：先子表后主表。TODO 表名"""
from common.logger import get_logger

log = get_logger("cleanup")

TABLES = [
    ("TODO_eval_result", "section_id IN (SELECT id FROM TODO_section WHERE section_name LIKE :p)"),
    ("TODO_bid", "section_id IN (SELECT id FROM TODO_section WHERE section_name LIKE :p)"),
    ("TODO_section", "section_name LIKE :p"),
    ("TODO_plan", "plan_no LIKE :p"),
]


def cleanup_by_prefix(db, prefix="AUTO_"):
    for table, where in TABLES:
        try:
            n = db.execute(f"DELETE FROM {table} WHERE {where}", p=f"{prefix}%")
            log.info("清理 %s：%s 行", table, n)
        except Exception as e:  # 表名未配置时不中断
            log.warning("清理 %s 失败：%s", table, e)
