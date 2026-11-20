"""准备度检查：自测开始前一条命令确认「能不能开跑」，约一分钟。

    python tools/preflight.py --env local --req <需求目录名>

逐项检查并给出 ✔ / ✘：
  1. 环境配置：本需求用例用到的地址、账号、数据库、外部依赖声明是否齐全
  2. 被测服务：地址能否访问
  3. 数据库：能否连接（配置了才检查）
  4. 浏览器：选定自动化用的浏览器（自带 Chromium → 本机 Chrome → 本机 Edge），并实际启动一次。不下载
  5. 页面通用方法：项目接入时是否已学习（登录、菜单、控件、提示框）。没学且本需求有界面用例 → ✘，先回去做接入
  6. 用例脚本：能否收集到本需求的用例，标签是否齐全
  7. 样本库：还有多少样本待提供（仅提示）
  8. 造数能力：账号池和前置流程造数是否已登记（仅提示）

另：python tools/preflight.py --common    只看页面通用方法是否已学习（需求开始前用）
    python tools/preflight.py --pick-env  判断「学习页面通用方法」该用哪个环境（优先本地，没有再用测试环境），并列出缺什么。

全部 ✔ 才开始自测。有 ✘ 时把清单交给人处理——
这些是准备工作，不要在自测会话里临时摸索（装浏览器、找测试数据、摸登录页都很耗时）。
"""
import argparse
import os
import subprocess
import sys
import urllib.error
import urllib.request
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
sys.path.insert(0, str(ROOT))

RESULTS = []


def record(ok, item, detail="", fix=""):
    RESULTS.append((ok, item, detail, fix))
    mark = {True: OK_MARK, False: BAD_MARK, None: INFO_MARK}[ok]
    print(f"  {mark} {item}" + (f"：{detail}" if detail else ""))
    if ok is False and fix:
        print(f"      处理：{fix}")


def run_pytest(args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip()]
    return p.returncode, lines


def check_config(env_name, req):
    print("1. 环境配置")
    args = ["--env", env_name, "--check-only"] + (["--req", req] if req else [])
    code, lines = run_pytest(args)
    verdict = next((ln for ln in reversed(lines) if "[预检通过]" in ln or "[环境未配置]" in ln
                    or "[缺少标签]" in ln or "[没有用例]" in ln), lines[-1] if lines else "")
    verdict = verdict.strip(" !").replace("_pytest.outcomes.Exit: ", "")
    if "[预检通过]" in verdict:
        record(True, "配置齐全", verdict.split("]", 1)[-1].strip())
        deferred = [ln.strip() for ln in lines if "←" in ln]
        for ln in deferred[:10]:
            print(f"      转其他环境：{ln}")
        return True
    record(False, "配置不齐", verdict,
           "在 project.yaml 中补全列出的配置项，或设置对应的环境变量；用不到的 TODO 不用管")
    return False


def check_service(env):
    print("2. 被测服务")
    from common.config import is_missing, lookup
    found = False
    for key in ("trade.base_url", "portal.base_url"):
        url = lookup(env, key)
        if url is None:
            continue
        found = True
        if is_missing(url):
            record(None, key, "未填写（本需求用不到则忽略）")
            continue
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=8) as r:
                record(True, key, f"可访问（HTTP {r.status}）")
        except urllib.error.HTTPError as e:
            record(True, key, f"可访问（HTTP {e.code}）")       # 有响应就说明服务在
        except Exception as e:  # noqa: BLE001
            record(False, key, f"无法访问：{type(e).__name__}", "确认本地工程已启动、地址和端口正确")
    if not found:
        record(None, "未配置服务地址")


def check_db(env):
    print("3. 数据库")
    from common.config import is_missing, lookup
    url = lookup(env, "db.url")
    if url is None:
        record(None, "未配置数据库", "测试环境一般不连库，属正常；查库的用例会跳过，改为在本地验证")
        return
    if is_missing(url):
        record(False, "db.url", "仍是 TODO 或环境变量未设置", "填写连接串；密码写成 ${ZTB_DB_PWD} 并设置该环境变量")
        return
    try:
        from common.db import DB
        db = DB(url, readonly=True)
        db.query("SELECT 1")
        db.close()
        record(True, "可连接", "只读" if env.get("readonly") else "可写（只动 AUTO_ 数据）")
    except ImportError as e:
        record(False, "缺少数据库驱动", str(e), "pip install -r requirements.txt")
    except Exception as e:  # noqa: BLE001
        record(False, "无法连接", type(e).__name__, "确认地址、端口、账号；检查 ZTB_DB_PWD 是否已设置")


def check_browser():
    print("4. 浏览器")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        record(False, "未安装 playwright", "", "pip install -r requirements.txt")
        return
    from common import browser as bc
    from common.config import EnvNotConfigured
    try:
        with sync_playwright() as p:
            choice = bc.choose(p.chromium.executable_path)
            kwargs = {"headless": True}
            if choice["channel"]:
                kwargs["channel"] = choice["channel"]
            b = p.chromium.launch(**kwargs)
            version = b.version
            b.close()
        bc.save_choice(choice)
        record(True, "可用", f"{choice['detail']}（版本 {version}，无界面运行，不影响你正在用的浏览器）")
    except EnvNotConfigured as e:
        record(False, "没有可用的浏览器", str(e), "由人安装一次：python -m playwright install chromium，或安装 Chrome")
    except Exception as e:  # noqa: BLE001
        record(False, "浏览器启动失败", f"{type(e).__name__}: {str(e)[:120]}",
               "本机 Chrome 版本过新时升级 playwright；或由人执行 python -m playwright install chromium")


def common_methods_status():
    """页面通用方法是否已在项目接入时学习。返回 (是否完成, 未完成的原因列表)。"""
    lacks = []
    f = ROOT / "pages" / "login_page.py"
    if not f.exists() or "TODO" in f.read_text(encoding="utf-8"):
        lacks.append("pages/login_page.py 的登录方法还没按本项目补全")
    b = ROOT / "pages" / "base_page.py"
    if not b.exists() or "TODO" in b.read_text(encoding="utf-8"):
        lacks.append("pages/base_page.py 的控件方法还有 TODO")
    reg = ROOT / "pages" / "环境差异.md"
    learned = False
    if reg.exists():
        text = reg.read_text(encoding="utf-8")
        part = text.split("## 一、学习记录", 1)[-1].split("## 二、", 1)[0]
        rows = [ln for ln in part.splitlines() if ln.startswith("|") and "---" not in ln and "学习环境" not in ln]
        learned = any("示例" not in ln for ln in rows)
    if not learned:
        lacks.append("pages/环境差异.md 里没有学习记录")
    return (not lacks), lacks


def has_ui_cases(req):
    """本需求是否有界面用例：True / False；没指定需求时返回 None。"""
    if not req:
        return None
    _, lines = run_pytest(["--req", req, "--collect-only", "-m", "ui"])
    return any("::" in ln or "<Function" in ln for ln in lines)


FIX_COMMON = ("这是项目接入的步骤，每个项目只做一次，不在需求里做：按 docs/各阶段提示词.md 的 0-2 单独开一个会话完成"
              "（python tools/preflight.py --pick-env 选环境）")


def check_common_methods(req):
    print("5. 页面通用方法（项目接入时学习，一次性）")
    done, lacks = common_methods_status()
    if done:
        record(True, "已学习")
        return
    ui = has_ui_cases(req)
    if ui is False:
        record(None, "尚未学习", "本需求没有界面用例，不影响；有界面用例的需求开始前必须先完成")
        return
    record(False, "尚未学习", "；".join(lacks), FIX_COMMON)


def main_common():
    done, lacks = common_methods_status()
    if done:
        print("页面通用方法：已学习。需求中直接复用，缺个别控件时按规则少量补充。")
        return 0
    print("页面通用方法：尚未学习——" + "；".join(lacks))
    print("处理：" + FIX_COMMON)
    print("在完成之前，不要在需求任务里开始摸索登录页和通用控件。")
    return 1


def check_collect(req):
    print("6. 用例脚本")
    if not req:
        record(None, "未指定 --req，跳过")
        return
    code, lines = run_pytest(["--req", req, "--collect-only"])
    last = lines[-1].strip(" =!") if lines else ""
    if code == 0 and "collected" in last:
        record(True, "可收集", last)
    else:
        record(False, "无法收集", last[:200], "脚本不符合规范（缺标签、导入错误）：交回第二步修订，不要在自测中自行改")


def check_samples():
    print("7. 样本库")
    try:
        from common import samples
        idx = samples.load_index()
        todo = [e.get("id") for sec in ("files", "third_party") for e in (idx.get(sec) or []) if not samples.available(e)]
        hand = sum(1 for m in idx.get("messages") or [] if "手写" in str(m.get("source", "")))
        record(None, "仅提示", f"待提供的文件 {len(todo)} 个，手写待录制的报文 {hand} 条；本需求用到的才需要补（见 samples/index.yaml）")
    except Exception as e:  # noqa: BLE001
        record(False, "samples/index.yaml 读取失败", str(e)[:120], "检查 index.yaml 的格式")


def data_status():
    """flows/造数能力.md 里登记了多少（仅提示）。"""
    f = ROOT / "flows" / "造数能力.md"
    if not f.exists():
        return 0
    rows = [ln for ln in f.read_text(encoding="utf-8").splitlines()
            if ln.startswith("|") and "---" not in ln and "示例" not in ln and "✔" in ln]
    return len(rows)


def check_data():
    print("8. 造数能力")
    n = data_status()
    if n:
        record(None, "仅提示", f"flows/造数能力.md 已登记 {n} 项可用的账号或造数方法")
    else:
        record(None, "仅提示", "flows/造数能力.md 还没有登记：前置数据和账号会反复向人要，建议先做项目接入的「账号池和造数主流程」")


def _reachable(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=8):
            return True
    except urllib.error.HTTPError:
        return True          # 有响应就说明服务在
    except Exception:  # noqa: BLE001
        return False


def pick_env(project):
    """选择「学习页面通用方法」用的环境：优先本地开发环境，没有再用测试环境。
    返回 (环境名或 None, 每个环境的缺项说明)。"""
    from common.config import get_env, is_missing, lookup
    envs = project.get("envs") or {}
    report = {}
    chosen = None
    for name in ("local", "test"):
        lacks = []
        if name not in envs:
            report[name] = ["project.yaml 中没有这个环境"]
            continue
        env = get_env(project, name)
        url = next((lookup(env, k) for k in ("trade.base_url", "portal.base_url") if lookup(env, k) is not None), None)
        if is_missing(url):
            lacks.append("系统地址（trade.base_url 或 portal.base_url）")
        accounts = [r for r, a in (env.get("accounts") or {}).items()
                    if isinstance(a, dict) and not is_missing(a.get("username")) and not is_missing(a.get("password"))]
        if not accounts:
            lacks.append("至少一个可登录的账号（accounts 中填用户名，密码用环境变量 ZTB_PWD_<环境大写>_<角色大写> 提供）")
        if not lacks and not _reachable(url):
            lacks.append("地址已填但访问不到（本地工程未启动，或当前网络到不了该环境）")
        report[name] = lacks
        if not lacks and chosen is None:
            chosen = name
    return chosen, report


def main_pick_env():
    from common.config import load_project
    chosen, report = pick_env(load_project())
    label = {"local": "本地开发环境 local", "test": "测试环境 test"}
    print("选择学习页面通用方法的环境（优先本地开发环境，没有再用测试环境）\n")
    for name in ("local", "test"):
        lacks = report.get(name, [])
        print(f"  {OK_MARK if not lacks else BAD_MARK} {label[name]}" + ("" if not lacks else "：缺 " + "；".join(lacks)))
    print()
    if chosen == "local":
        print("结论：用 local 学习。之后在测试环境验证时，发现与这里不同的地方再补充并登记到 pages/环境差异.md。")
    elif chosen == "test":
        print("结论：本地环境不可用，用 test 学习。测试环境是共用的：只浏览和操作控件，不保存、不提交、不改数据。")
        print("      以后有了本地环境，再在本地验证一遍，把不同的地方登记到 pages/环境差异.md。")
    else:
        print("结论：两个环境都不可用。请先提供其中一个：")
        print("      优先本地开发环境——启动本地工程，在 project.yaml 取消 local 一节的注释并填写地址和账号；")
        print("      没有本地环境时——在 project.yaml 的 test 一节填写测试环境地址和一个账号（密码用环境变量）。")
    return 0 if chosen else 1


def main():
    ap = argparse.ArgumentParser(description="准备度检查")
    ap.add_argument("--env", default=os.getenv("ZTB_ENV", "local"))
    ap.add_argument("--req", default=None, help="需求目录名；不填则只检查环境")
    ap.add_argument("--pick-env", action="store_true",
                    help="只判断学习页面通用方法该用哪个环境（优先 local，没有再用 test），并列出缺什么")
    ap.add_argument("--common", action="store_true", help="只检查页面通用方法是否已在项目接入时学习")
    a = ap.parse_args()
    if a.common:
        return main_common()
    if a.pick_env:
        return main_pick_env()

    from common.config import get_env, load_project
    project = load_project()
    envs = project.get("envs") or {}
    fw = ROOT / "framework.yaml"
    version = ""
    if fw.exists():
        import yaml
        version = (yaml.safe_load(fw.read_text(encoding="utf-8")) or {}).get("version") or ""
    print(f"准备度检查：环境 {a.env}" + (f"，需求 {a.req}" if a.req else "") + (f"（框架版本 {version}）" if version else "") + "\n")
    if a.env not in envs:
        record(False, f"project.yaml 中没有环境「{a.env}」", f"已有：{list(envs)}",
               "按 project.yaml 中的注释取消 local 一节的注释并填写")
    else:
        env = get_env(project, a.env)
        check_config(a.env, a.req)
        check_service(env)
        check_db(env)
        check_browser()
        check_common_methods(a.req)
        check_collect(a.req)
        check_samples()
        check_data()

    bad = [r for r in RESULTS if r[0] is False]
    print()
    if bad:
        print(f"结论：未就绪，{len(bad)} 项需要处理。请把上面不通过的项交给人处理后重新检查；不要在自测会话里临时摸索。")
        return 1
    print("结论：已就绪，可以开始自测。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
