"""全局 fixture 与用例筛选（单项目结构，配置见根目录 project.yaml）。

筛选规则：
  1. testcases/baseline/<系统>/ 只运行 project.yaml 中 systems 列出的系统
  2. testcases/features/ 只在有可选功能开启时加载；@pytest.mark.feature("x") 未开启时跳过
  3. 指定 --module 时，只运行 @pytest.mark.module("<模块>") 匹配的用例（按模块回归）
  4. 指定 --req 时，只运行 @pytest.mark.req("<需求目录名>") 匹配的用例（需求自测）；两者可同时使用
  5. @pytest.mark.needs("<外部依赖>") 的用例，按当前环境 deps 中该依赖的提供方式决定：
       mock / real → 运行；none / 未声明 → 跳过并标「转其他环境执行」；manual → 跳过并标「人工验收」
     @pytest.mark.needs("<依赖>", mode="mock") 只在该依赖为 mock 的环境运行（如需要切换 mock 场景的异常用例）

环境预检（用到什么才检查什么）：
  - 只检查「本次要运行的用例」需要的配置，用不到的 TODO 不拦截
  - 缺配置时一次列出全部缺项并停止，不让用例逐条超时；缺的是环境，不要改用例、不要重跑
"""
import os
from pathlib import Path

import pytest

from common.config import (BASE_DIR, EnvNotConfigured, dep_mode, find_missing, get_env, is_missing,
                           load_project, lookup, require)

pytest_plugins = ["fixtures.trade_fixtures", "fixtures.ui_fixtures"]

_DEFERRED = []   # (nodeid, 依赖, 原因)：因当前环境不提供依赖而跳过的用例，结束时汇总


def pytest_addoption(parser):
    parser.addoption("--env", default=os.getenv("ZTB_ENV", "test"), help="环境名，对应 project.yaml 中 envs 的键")
    parser.addoption("--module", default=None, help="只运行指定模块，对应 @pytest.mark.module(\"<模块>\")")
    parser.addoption("--req", default=None, help="只运行指定需求，对应 @pytest.mark.req(\"<需求目录名>\")")
    parser.addoption("--check-only", action="store_true", default=False,
                     help="只做环境预检（本次用例需要的配置是否齐全），不运行用例")


def _stop(kind, message, returncode=4):
    pytest.exit(f"[{kind}] {message}", returncode=returncode)


def pytest_sessionstart(session):
    """开跑前只确认环境存在；具体配置在收集完用例后按需检查。"""
    config = session.config
    if config.getoption("collectonly", False):
        return
    env_name = config.getoption("--env")
    envs = load_project().get("envs") or {}
    if env_name not in envs:
        _stop("环境未配置", f"project.yaml 的 envs 中没有「{env_name}」（已有：{list(envs)}）。"
                       f"请先按 project.yaml 中的注释配置后再运行。")


def _parts(path):
    try:
        return Path(path).resolve().relative_to(BASE_DIR).parts
    except ValueError:
        return ()


def pytest_ignore_collect(collection_path, config):
    """不导入本项目未包含的系统和未开启的可选功能，避免加载无关依赖。"""
    parts = _parts(collection_path)
    project = load_project()
    if len(parts) > 2 and parts[:2] == ("testcases", "baseline") and parts[2] not in (project.get("systems") or []):
        return True
    if len(parts) > 1 and parts[:2] == ("testcases", "features") and not any((project.get("features") or {}).values()):
        return True
    return None


def _apply_needs(item, env, env_name, bad):
    """按环境的 deps 处理 needs 标记。返回 True 表示该用例会运行。"""
    will_run = True
    for mark in item.iter_markers("needs"):
        if not mark.args:
            continue
        dep, want = mark.args[0], mark.kwargs.get("mode")
        try:
            mode = dep_mode(env, dep)
        except EnvNotConfigured as e:
            bad.add(str(e))
            continue
        if mode in (None, "none"):
            why = f"环境 {env_name} 不提供「{dep}」" + ("（deps 中未声明）" if mode is None else "") + "，转其他环境执行"
        elif mode == "manual":
            why = f"「{dep}」在环境 {env_name} 为人工验收"
        elif want and mode != want:
            why = f"本用例需要「{dep}」为 {want}，环境 {env_name} 为 {mode}，转其他环境执行"
        else:
            section = lookup(env, f"{dep}_{mode}")      # 约定：依赖的地址配置在 <依赖>_<方式> 下，如 eval_mock、eval_real
            if section is None:
                bad.add(f"{dep}_{mode}（deps.{dep} 为 {mode}，但缺少这一节配置）")
            else:
                bad.update(find_missing(section, f"{dep}_{mode}"))
            continue
        item.add_marker(pytest.mark.skip(reason=why))
        _DEFERRED.append((item.nodeid, dep, why))
        will_run = False
    return will_run


@pytest.hookimpl(trylast=True)   # 排在 pytest 自带的 -k / -m 筛选之后，预检只看真正要运行的用例
def pytest_collection_modifyitems(config, items):
    project = load_project()
    features = project.get("features") or {}
    module = config.getoption("--module")
    req = config.getoption("--req")
    selected, deselected = [], []
    for item in items:
        if module:
            m = item.get_closest_marker("module")
            if not m or m.args[0] != module:
                deselected.append(item)
                continue
        if req:
            r = item.get_closest_marker("req")
            if not r or req not in r.args:
                deselected.append(item)
                continue
        f = item.get_closest_marker("feature")
        if f and not features.get(f.args[0], False):
            item.add_marker(pytest.mark.skip(reason=f"项目未启用功能：{f.args[0]}"))
        selected.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
    # testcases/modules/ 下的用例必须同时带 module 和 req 标签（见 prompts/02_用例与脚本生成.md 第四部分第 3 条）
    missing = [i.nodeid for i in items
               if _parts(i.path)[:2] == ("testcases", "modules")
               and not (i.get_closest_marker("module") and i.get_closest_marker("req"))]
    if missing:
        _stop("缺少标签", "以下用例没有同时标注 @pytest.mark.module 和 @pytest.mark.req：\n  "
              + "\n  ".join(missing[:20]) + ("\n  ……" if len(missing) > 20 else ""))
    if (module or req) and not selected:
        mods = sorted({m.args[0] for i in deselected for m in [i.get_closest_marker("module")] if m})
        reqs = sorted({a for i in deselected for r in [i.get_closest_marker("req")] if r for a in r.args})
        _stop("没有用例", f"没有匹配 module={module!r} req={req!r} 的用例。"
              f"已有模块：{mods or '无'}；已有需求：{reqs or '无'}。"
              f"参数要与用例中的 @pytest.mark.module / @pytest.mark.req 名称一致。", returncode=5)

    if config.getoption("collectonly", False):
        return
    # ---------- 按需预检：只检查本次要运行的用例用到的配置 ----------
    env_name = config.getoption("--env")
    env = get_env(project, env_name)
    bad = set()
    for item in items:
        if any(m.name == "skip" for m in item.iter_markers()):
            continue
        if not _apply_needs(item, env, env_name, bad):
            continue
        names = set(getattr(item, "fixturenames", ()))
        if "login_as" in names and is_missing(lookup(env, "trade.base_url")):
            bad.add("trade.base_url")
        if "db" in names and env.get("db") is not None and is_missing(lookup(env, "db.url")):
            bad.add("db.url")
        for mark in item.iter_markers("needs_config"):      # 用例显式声明的必需配置项
            bad.update(a for a in mark.args if is_missing(lookup(env, a)))
    if bad:
        _stop("环境未配置", f"环境 {env_name} 中，本次要运行的用例需要以下配置，但仍是 TODO、为空或含未设置的环境变量"
              f"（如 ${{ZTB_DB_PWD}}）：{'、'.join(sorted(bad))}。\n"
              f"这是环境问题：请在 project.yaml 中填写或设置对应环境变量后再运行；不要修改用例，不要反复重跑。")
    if config.getoption("--check-only"):
        will_run = sum(1 for i in items if not any(m.name == "skip" for m in i.iter_markers()))
        pytest.exit(f"[预检通过] 环境 {env_name}：将运行 {will_run} 条，"
                    f"因外部依赖转其他环境 {len(_DEFERRED)} 条。", returncode=0)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """运行中才发现缺配置（如某个角色的账号没填）：立即停止整次运行，并说明缺什么。"""
    outcome = yield
    if call.excinfo is not None and call.excinfo.errisinstance(EnvNotConfigured):
        outcome.get_result()
        item.session.shouldstop = (f"[环境未配置] {item.nodeid} 需要配置：{call.excinfo.value}。"
                                   f"请在 project.yaml 中填写或设置对应环境变量后再运行；不要修改用例，不要反复重跑。")


def pytest_terminal_summary(terminalreporter):
    """汇总因环境不提供外部依赖而未执行的用例，写自测报告时直接引用。"""
    if not _DEFERRED:
        return
    tr = terminalreporter
    tr.section("未在本环境执行的用例（外部依赖）")
    for nodeid, dep, why in _DEFERRED:
        tr.write_line(f"{nodeid}  ←  {why}")
    tr.write_line("以上用例不算失败：请换到提供该依赖的环境执行（--env <环境>），人工验收的按 02_测试用例.md 的清单验证。")


@pytest.fixture(scope="session")
def project():
    return load_project()


@pytest.fixture(scope="session")
def env(request, project):
    return get_env(project, request.config.getoption("--env"))


_DB_STATE = {"instance": None}


@pytest.fixture(scope="session")
def db(env):
    """数据库访问。只读环境（readonly: true）下只能查询；任何环境都不能改表结构、不能整表修改。"""
    from common.db import DB
    if not env.get("db"):
        pytest.skip("当前环境未配置数据库")
    database = DB(require(env, "db.url"), readonly=bool(env.get("readonly", False)))
    _DB_STATE["instance"] = database
    yield database
    database.close()


@pytest.fixture(scope="session")
def login_as(env):
    """交易系统按角色登录：login_as("agent") / login_as("bidder_1")"""
    from api.session import TradeSession
    cache = {}

    def _login(role):
        if role not in cache:
            base_url = require(env, "trade.base_url")
            account = require(env, f"accounts.{role}")
            s = TradeSession(base_url)
            s.login(account["username"], account["password"])
            cache[role] = s
        return cache[role]

    return _login


@pytest.fixture(scope="session", autouse=True)
def cleanup_auto_data(env):
    """会话结束后按 AUTO_ 前缀清理自动化数据：仅当本次运行用到了数据库、开启清理、且环境不是只读时。"""
    yield
    database = _DB_STATE["instance"]
    if database is not None and env.get("cleanup", True) and not env.get("readonly", False):
        from db.cleanup import cleanup_by_prefix
        cleanup_by_prefix(database, env.get("data_prefix", "AUTO_"))
