"""② 代理“获取评标结果”：交易系统调用评标系统（Mock），产品基线
前提：交易系统测试环境的评标接口地址已配置为 Mock 地址。"""
import pytest

from api.open_eval_api import OpenEvalApi
from common.config import require
from mocks.mock_control import EvalMock

# 我们调评标取结果：需要切换 mock 场景，只在 deps.eval 为 mock 的环境运行（通常是本地）
pytestmark = pytest.mark.needs("eval", mode="mock")


@pytest.fixture(scope="module")
def mock(env):
    m = EvalMock(require(env, "eval_mock.control_url"))
    m.reset()
    yield m
    m.reset()


@pytest.fixture
def agent_api(login_as):
    return OpenEvalApi(login_as("agent"))


@pytest.mark.integration
@pytest.mark.p0
def test_get_result_normal(mock, agent_api, opened_section, db):
    mock.set_scenario("normal")
    res = agent_api.fetch_eval_result(opened_section.section_id)
    assert res.get("success") is True
    rows = db.query("SELECT bidder_name, ranking FROM TODO_eval_result WHERE section_id=:sid ORDER BY ranking",
                    sid=opened_section.section_id)
    assert [r["bidder_name"] for r in rows] == ["AUTO_投标人1", "AUTO_投标人2", "AUTO_投标人3"]
    assert mock.received(), "Mock 未收到交易系统请求，检查评标接口地址配置"


@pytest.mark.integration
@pytest.mark.p1
def test_get_result_repeat_no_duplicate(mock, agent_api, opened_section, db):
    mock.set_scenario("normal")
    agent_api.fetch_eval_result(opened_section.section_id)
    agent_api.fetch_eval_result(opened_section.section_id)
    n = db.query_one("SELECT COUNT(*) AS n FROM TODO_eval_result WHERE section_id=:sid", sid=opened_section.section_id)
    assert n["n"] == 3


@pytest.mark.integration
@pytest.mark.p1
@pytest.mark.parametrize("scenario,keyword", [
    ("not_finished", "尚未结束"),
    ("error", "异常"),
])
def test_get_result_abnormal(mock, agent_api, opened_section, scenario, keyword):
    mock.set_scenario(scenario)
    res = agent_api.fetch_eval_result(opened_section.section_id)
    assert res.get("success") is False
    assert keyword in res.get("message", "")


@pytest.mark.integration
@pytest.mark.p1
@pytest.mark.parametrize("scenario,expect_status", [
    ("failed_bid", "TODO_流标状态"),
    ("rejected", "TODO_重新评标状态"),
])
def test_get_result_special_status(mock, agent_api, opened_section, db, scenario, expect_status):
    mock.set_scenario(scenario)
    agent_api.fetch_eval_result(opened_section.section_id)
    row = db.query_one("SELECT status FROM TODO_section WHERE id=:sid", sid=opened_section.section_id)
    assert row["status"] == expect_status


@pytest.mark.integration
@pytest.mark.p2
def test_get_result_timeout(mock, agent_api, opened_section):
    mock.set_scenario("timeout")
    res = agent_api.fetch_eval_result(opened_section.section_id)
    assert res.get("success") is False
