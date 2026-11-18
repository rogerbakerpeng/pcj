"""数据库访问：造数、结果校验、清理。内置写保护，防止自动化误改业务数据。

写保护（execute 时检查，query 不受限）：
  1. 只读环境（project.yaml 中 envs.<环境>.readonly: true）禁止任何写操作
  2. 任何环境都禁止 DROP / TRUNCATE / ALTER 等结构变更——表结构变更由研发手工执行迁移脚本
  3. UPDATE / DELETE 必须带 WHERE，禁止整表修改
"""
import re


class WriteBlocked(Exception):
    """被写保护拦截的 SQL。不要绕过：换成只操作自己造的数据，或请用户确认后手工执行。"""


_FORBIDDEN = re.compile(r"^\s*(drop|truncate|alter|create|rename|grant|revoke)\b", re.I)
_NEEDS_WHERE = re.compile(r"^\s*(update|delete)\b", re.I)
_COMMENT = re.compile(r"(--[^\n]*|/\*.*?\*/)", re.S)


def check_write(sql, readonly=False):
    """检查一条写 SQL 是否允许执行，不允许时抛 WriteBlocked。"""
    clean = _COMMENT.sub(" ", sql)
    statements = [s for s in clean.split(";") if s.strip()]
    for s in statements:
        head = s.strip().split(None, 1)[0].upper() if s.strip() else ""
        if readonly:
            raise WriteBlocked(f"当前环境只读（readonly: true），禁止执行 {head}。测试环境只查不改，用专用测试数据触发业务后核对结果。")
        if _FORBIDDEN.match(s):
            raise WriteBlocked(f"禁止通过自动化执行 {head}。表结构变更由研发确认后手工执行迁移脚本。")
        if _NEEDS_WHERE.match(s) and not re.search(r"\bwhere\b", s, re.I):
            raise WriteBlocked(f"{head} 必须带 WHERE 条件，禁止整表修改。")


class DB:
    def __init__(self, url, readonly=False):
        from sqlalchemy import create_engine
        self.readonly = readonly
        # 连接超时 10 秒，数据库不通时尽快失败
        connect_args = {"connect_timeout": 10} if url.startswith(("mysql", "postgresql")) else {}
        self.engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)

    def query(self, sql, **params):
        from sqlalchemy import text
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params)]

    def query_one(self, sql, **params):
        rows = self.query(sql, **params)
        return rows[0] if rows else None

    def execute(self, sql, **params):
        from sqlalchemy import text
        check_write(sql, self.readonly)
        with self.engine.begin() as conn:
            return conn.execute(text(sql), params).rowcount

    def close(self):
        self.engine.dispose()
