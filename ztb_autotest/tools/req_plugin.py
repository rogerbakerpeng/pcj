"""pytest 插件：把每条用例的结果写成 JSON，供 tools/run_req.py 汇总。由 run_req.py 通过 -p 加载，不要单独使用。"""
import json
import os

_RESULTS = {}


def _short(report):
    """失败原因的简短描述：断言信息 + 位置。完整堆栈在日志文件里。"""
    rep = report.longrepr
    crash = getattr(rep, "reprcrash", None)
    if crash is not None:
        lines = [ln.strip() for ln in str(crash.message).splitlines() if ln.strip()]
        msg = " | ".join(lines[:3])[:400]          # 断言信息和第一层比较；完整堆栈在日志文件里
        return f"{msg}  @ {os.path.basename(str(crash.path))}:{crash.lineno}"
    if isinstance(rep, tuple) and len(rep) == 3:      # 跳过：(文件, 行号, 原因)
        return str(rep[2])[:300]
    return str(rep).strip().splitlines()[-1][:400] if rep else ""


def pytest_runtest_logreport(report):
    item = _RESULTS.setdefault(report.nodeid, {"outcome": "passed", "duration": 0.0, "detail": ""})
    item["duration"] += getattr(report, "duration", 0.0) or 0.0
    if report.skipped:
        if hasattr(report, "wasxfail"):
            item["outcome"] = "xfailed"
            item["detail"] = str(report.wasxfail)[:300]
        elif item["outcome"] == "passed":
            item["outcome"] = "skipped"
            item["detail"] = _short(report)
    elif report.failed:
        item["outcome"] = "failed" if report.when == "call" else "error"
        item["detail"] = _short(report)
    elif report.passed and report.when == "call" and hasattr(report, "wasxfail"):
        item["outcome"] = "xpassed"


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("ZTB_RESULT_FILE")
    if not path:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"exitstatus": int(exitstatus), "stop": str(getattr(session, "shouldstop", "") or ""),
                   "results": _RESULTS}, f, ensure_ascii=False, indent=1)
