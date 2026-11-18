"""需求自测运行器：一条命令跑完并给出失败摘要，省掉「为了看报错而重跑」。

    python tools/run_req.py --req <需求目录名> --env local              首次：跑本需求全部用例
    python tools/run_req.py --req <需求目录名> --env local --failed     只重跑上次失败、且尚未定性的用例
    python tools/run_req.py --req <需求目录名> --env local -k "018"     只跑名字含 018 的用例
    python tools/run_req.py --req <需求目录名> --classify "018=c:预期与新设计不符，待交付确认"
    python tools/run_req.py --req <需求目录名> --env local --all        最终全量（含已定性的），出报告前跑一次
    python tools/run_req.py --req <需求目录名> --status                 查看当前进度，不运行

做了什么：
  - 完整输出写入日志文件，屏幕只给摘要：每条失败用例的断言信息和位置。不需要再用 tail / grep 截取，也不需要重跑看详情
  - 记录每条用例连续失败的轮数；达到 3 轮标「停止修复」，应停下来汇报
  - 已定性的用例（c 预期待确认 / d 环境问题）后续默认不再运行，避免反复重跑已知失败
  - 因当前环境不提供外部依赖而跳过的用例单独列出，不算失败

定性类别：c = 预期可能有误或需求未覆盖（待交付确认）；d = 环境问题；ok = 取消定性
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _console_utf8():
    """Windows 命令行默认是 GBK，输出 ✔ ✘ 等字符会报错：改为无法显示的字符用 ? 代替，不中断。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


_console_utf8()


def _symbols():
    """命令行能显示 ✔ ✘ 就用符号，否则（如 Windows GBK 命令行）用文字。"""
    try:
        "✔✘－".encode(sys.stdout.encoding or "utf-8")
        return "✔", "✘", "－"
    except (UnicodeEncodeError, LookupError):
        return "[通过]", "[不通过]", "[提示]"


OK_MARK, BAD_MARK, INFO_MARK = _symbols()

ROOT = Path(__file__).resolve().parent.parent
MAX_ROUNDS = 3


def _state_dir(req):
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in req)[:80]
    d = ROOT / ".runtime" / "runs" / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(d):
    try:
        return json.loads((d / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"runs": 0, "tests": {}}


def _save(d, state):
    (d / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _name(nodeid):
    return nodeid.split("::", 1)[-1]


def _classify(state, spec):
    if "=" not in spec:
        sys.exit('定性格式：--classify "<用例名关键字>=c:原因"（类别 c / d / ok）')
    key, rest = spec.split("=", 1)
    kind, _, note = rest.partition(":")
    kind = kind.strip().lower()
    if kind not in ("c", "d", "ok"):
        sys.exit("类别只能是 c（预期待确认）、d（环境问题）、ok（取消定性）")
    hit = [n for n in state["tests"] if key.strip() in n]
    if not hit:
        sys.exit(f"没有名字包含「{key}」的用例。先运行一次，或用 --status 查看用例名。")
    for n in hit:
        if kind == "ok":
            state["tests"][n].pop("class", None)
            state["tests"][n].pop("note", None)
        else:
            state["tests"][n]["class"] = kind
            state["tests"][n]["note"] = note.strip()
        print(f"已定性：{_name(n)} → {kind} {note.strip()}")


def _summary(state, last=None, log=None, stop=""):
    tests = state["tests"]
    by = {}
    for n, t in tests.items():
        by.setdefault(t.get("outcome", "?"), []).append(n)
    open_fail = [n for n in tests if tests[n].get("outcome") in ("failed", "error") and not tests[n].get("class")]
    classified = [n for n in tests if tests[n].get("class")]
    deferred = [n for n in by.get("skipped", []) if "环境" in tests[n].get("detail", "") or "人工" in tests[n].get("detail", "")]
    print("\n" + "=" * 20 + f" 自测摘要（第 {state['runs']} 次运行）" + "=" * 20)
    print("累计：" + "、".join(f"{k} {len(v)}" for k, v in sorted(by.items())) +
          (f"｜本次运行 {len(last)} 条" if last is not None else ""))
    if stop:
        print(f"\n【运行被中止】{stop}")
    if open_fail:
        print(f"\n未解决的失败 {len(open_fail)} 条：")
        for n in open_fail:
            t = tests[n]
            flag = "  ← 已连续失败 %d 轮：停止修复，停下来汇报" % t["rounds"] if t.get("rounds", 0) >= MAX_ROUNDS else ""
            print(f"  {BAD_MARK} {_name(n)}（第 {t.get('rounds', 1)} 轮）{flag}\n      {t.get('detail', '')}")
    if classified:
        print(f"\n已定性 {len(classified)} 条（默认不再重跑，写进自测报告）：")
        for n in classified:
            print(f"  [{tests[n]['class']}] {_name(n)}：{tests[n].get('note', '')}")
    if deferred:
        print(f"\n待其他环境执行 {len(deferred)} 条（不算失败）：")
        for n in deferred:
            print(f"  → {_name(n)}：{tests[n].get('detail', '')}")
    if last:
        slow = [(dur, n) for dur, n in sorted(((last[n]["duration"], n) for n in last), reverse=True)[:3] if dur >= 5]
        if slow:
            print("\n最慢：" + "；".join(f"{_name(n)} {dur:.0f}s" for dur, n in slow))
    if log:
        print(f"完整输出：{log}（需要堆栈时直接读这个文件，不要重跑）")
    if not open_fail and not stop:
        print("\n没有未解决的失败。" + ("" if last is None else "出报告前用 --all 做一次最终全量。"))
    return open_fail


def main():
    ap = argparse.ArgumentParser(description="需求自测运行器", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--req", required=True, help="需求目录名（requirements/ 下的目录名）")
    ap.add_argument("--env", default=os.getenv("ZTB_ENV", "local"))
    ap.add_argument("--failed", action="store_true", help="只重跑上次失败且未定性的用例")
    ap.add_argument("--all", action="store_true", help="全量，包含已定性的用例（出报告前跑一次）")
    ap.add_argument("-k", dest="keyword", default=None, help="只跑名字匹配的用例（pytest -k）")
    ap.add_argument("--module", default=None, help="改为按模块回归（pytest --module），不记入本需求进度")
    ap.add_argument("--classify", action="append", default=[], help='定性："<关键字>=c:原因"')
    ap.add_argument("--status", action="store_true", help="只显示进度")
    ap.add_argument("pytest_args", nargs="*", help="透传给 pytest 的其他参数，写在 -- 之后")
    a = ap.parse_args()

    d = _state_dir(a.req if not a.module else f"module_{a.module}")
    state = _load(d)
    for spec in a.classify:
        _classify(state, spec)
    if a.classify:
        _save(d, state)
    if a.status or (a.classify and not (a.failed or a.all or a.keyword)):
        _summary(state)
        return 0

    cmd = [sys.executable, "-m", "pytest", "-p", "tools.req_plugin", "--env", a.env, "-q", "--tb=short", "-rs"]
    cmd += ["--module", a.module] if a.module else ["--req", a.req]
    tests = state["tests"]
    if a.failed:
        targets = [n for n, t in tests.items() if t.get("outcome") in ("failed", "error") and not t.get("class")]
        if not targets:
            print("没有需要重跑的失败用例。")
            _summary(state)
            return 0
        cmd += targets
    if not a.all:
        for n, t in tests.items():
            if t.get("class"):
                cmd += ["--deselect", n]
    if a.keyword:
        cmd += ["-k", a.keyword]
    cmd += a.pytest_args

    state["runs"] += 1
    log = d / f"run_{state['runs']:02d}.log"
    result_file = d / "last_result.json"
    result_file.unlink(missing_ok=True)
    env = {**os.environ, "ZTB_RESULT_FILE": str(result_file), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    started = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as f:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
    took = time.time() - started

    if not result_file.exists():
        # 没有产生结果：通常是预检不通过（环境未配置、缺少标签、没有用例），把 pytest 的结论原样给出
        tail = [ln for ln in log.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()][-8:]
        print(f"pytest 没有运行用例（退出码 {proc.returncode}）。原因：")
        print("\n".join("  " + ln for ln in tail))
        print("这通常是环境或脚本规范问题：按提示处理，不要反复重跑。")
        state["runs"] -= 1
        _save(d, state)
        return proc.returncode or 4

    data = json.loads(result_file.read_text(encoding="utf-8"))
    last = data["results"]
    for n, r in last.items():
        t = tests.setdefault(n, {})
        failed = r["outcome"] in ("failed", "error")
        t["rounds"] = (t.get("rounds", 0) + 1) if failed else 0
        t.update(outcome=r["outcome"], detail=r["detail"], duration=round(r["duration"], 1))
    _save(d, state)
    print(f"用时 {took:.0f} 秒。")
    open_fail = _summary(state, last=last, log=log, stop=data.get("stop", ""))
    return 1 if open_fail or data.get("stop") else 0


if __name__ == "__main__":
    sys.exit(main())
