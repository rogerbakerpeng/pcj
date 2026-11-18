import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1600, "height": 900}}


@pytest.fixture
def agent_page(page_as):
    """以代理身份登录的页面。登录状态整次运行只取一次，见 fixtures/ui_fixtures.py。"""
    return page_as("agent")
