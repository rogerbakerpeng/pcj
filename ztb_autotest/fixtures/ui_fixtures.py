"""界面用例共用 fixture：浏览器选择、登录状态复用。

登录状态复用：每个角色整次运行只登录一次，登录后的状态存到 .runtime/auth/，
同一次运行以及有效期内的后续运行直接复用，不再每条用例重新登录（界面用例最主要的固定开销）。

    def test_x(page_as):
        page = page_as("agent")          # 已登录的页面
        page = page_as("agent", fresh=True)   # 强制重新登录（如测试登录本身、会话已失效）

登录动作由 pages/login_page.py 的 LoginPage.login(base_url, username, password) 完成，项目接入时补全。
登录方式随环境不同时（如测试环境走统一登录），在 project.yaml 对应环境的 ui.login 中声明，登录状态按环境分别保存。
页面对象需要区分环境做法时，构造时把 env 传进去：SomePage(page, env)。
"""
import os
import time

import pytest

from common import browser as browser_choice
from common.config import require

AUTH_TTL_SECONDS = int(os.getenv("ZTB_AUTH_TTL_MINUTES", "30")) * 60   # 登录状态有效期，默认 30 分钟


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, playwright):
    """未用 --browser-channel 指定时，自动选择浏览器（见 common/browser.py），不下载。"""
    args = dict(browser_type_launch_args)
    if not args.get("channel"):
        choice = browser_choice.load_choice() or browser_choice.choose(playwright.chromium.executable_path)
        if choice.get("channel"):
            args["channel"] = choice["channel"]
    return args


@pytest.fixture(scope="session")
def auth_state(browser, env, request):
    """返回函数 auth_state(role, fresh=False) -> 登录状态文件路径。"""
    env_name = request.config.getoption("--env")
    auth_dir = browser_choice.RUNTIME_DIR / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    done = set()

    def _get(role, fresh=False):
        path = auth_dir / f"{env_name}_{role}.json"
        stale = (not path.exists()) or (time.time() - path.stat().st_mtime > AUTH_TTL_SECONDS)
        if fresh or (stale and role not in done):
            from pages.login_page import LoginPage
            base_url = require(env, "trade.base_url" if env.get("trade") else "portal.base_url")
            account = require(env, f"accounts.{role}")
            ctx = browser.new_context()
            try:
                LoginPage(ctx.new_page(), env).login(base_url, account["username"], account["password"])
                ctx.storage_state(path=str(path))
            finally:
                ctx.close()
            done.add(role)
        return str(path)

    return _get


@pytest.fixture
def page_as(browser, browser_context_args, auth_state):
    """返回函数 page_as(role, fresh=False, **context_kwargs) -> 已登录的页面；用例结束自动关闭。"""
    contexts = []

    def _open(role, fresh=False, **context_kwargs):
        ctx = browser.new_context(**{**browser_context_args, **context_kwargs,
                                     "storage_state": auth_state(role, fresh=fresh)})
        contexts.append(ctx)
        return ctx.new_page()

    yield _open
    for ctx in contexts:
        ctx.close()
