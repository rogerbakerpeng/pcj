"""① 评标系统调用交易系统取数（交易系统为服务端，产品基线）
脚本扮演评标系统，不依赖评标系统在线。"""
import pytest

from common.xml_utils import parse, get_text, get_list
from contracts.contract_checker import assert_contract
from ws.eval_fetch_client import EvalFetchClient

# 评标调我们取数：脚本扮演评标系统，本地即可运行；环境 deps.eval 为 none 时跳过
pytestmark = [pytest.mark.needs("eval"), pytest.mark.needs_config("trade.fetch_ws_url")]


@pytest.fixture(scope="module")
def client(env):
    return EvalFetchClient(env)


@pytest.mark.integration
@pytest.mark.p0
def test_fetch_project_after_open(client, opened_section):
    status, xml = client.get_project_info(opened_section.section_code)
    assert status == 200
    assert get_text(parse(xml), "//Code") == "0"


@pytest.mark.integration
@pytest.mark.contract
@pytest.mark.p1
def test_fetch_project_contract(client, opened_section):
    _, xml = client.get_project_info(opened_section.section_code)
    assert_contract(xml, "fetch_project_resp.xsd", "fetch_project_resp")


@pytest.mark.integration
@pytest.mark.p1
def test_fetch_bidders_match_db(client, opened_section, db):
    _, xml = client.get_bidders(opened_section.section_code)
    ws_bidders = {b.findtext("BidderName"): b.findtext("Price") for b in get_list(parse(xml), "//Bidder")}  # TODO 节点名
    db_bidders = {r["bidder_name"]: str(r["price"]) for r in db.query(
        "SELECT bidder_name, price FROM TODO_bid WHERE section_id=:sid", sid=opened_section.section_id)}
    assert ws_bidders == db_bidders


@pytest.mark.integration
@pytest.mark.p1
def test_fetch_before_open_rejected(client, noticed_section):
    _, xml = client.get_project_info(noticed_section.section_code)
    assert get_text(parse(xml), "//Code") != "0", "未开标时不应返回评标数据"


@pytest.mark.integration
@pytest.mark.p1
@pytest.mark.parametrize("code", ["", "AUTO_NOT_EXIST", "' OR 1=1 --"])
def test_fetch_invalid_section(client, code):
    _, xml = client.get_project_info(code)
    assert get_text(parse(xml), "//Code") != "0"


@pytest.mark.integration
@pytest.mark.p1
def test_fetch_without_auth(env, opened_section):
    env_no_auth = {**env, "ws_auth": {"app_id": "WRONG"}}
    _, xml = EvalFetchClient(env_no_auth).get_project_info(opened_section.section_code)
    assert get_text(parse(xml), "//Code") != "0"
