"""③【个性化】评标主动推送：仅 features.eval_active_push=true 的项目执行。"""
import pytest

from api.open_eval_api import OpenEvalApi
from common.xml_utils import parse, get_text
from ws.eval_push_client import EvalPushClient

CANDIDATES = [
    {"rank": 1, "name": "AUTO_投标人1", "score": "92.50", "price": "1000000.00"},
    {"rank": 2, "name": "AUTO_投标人2", "score": "88.00", "price": "1020000.00"},
    {"rank": 3, "name": "AUTO_投标人3", "score": "85.30", "price": "990000.00"},
]

pytestmark = [pytest.mark.integration, pytest.mark.feature("eval_active_push"),
              pytest.mark.needs("eval"), pytest.mark.needs_config("trade.push_ws_url")]


@pytest.fixture(scope="module")
def push(env):
    return EvalPushClient(env)


@pytest.mark.p0
def test_push_success(push, opened_section, db):
    _, xml = push.push_result(opened_section.section_code, CANDIDATES)
    assert get_text(parse(xml), "//Code") == "0"
    n = db.query_one("SELECT COUNT(*) AS n FROM TODO_eval_result WHERE section_id=:sid", sid=opened_section.section_id)
    assert n["n"] == 3


@pytest.mark.p1
def test_push_idempotent(push, opened_section, db):
    push.push_result(opened_section.section_code, CANDIDATES)
    push.push_result(opened_section.section_code, CANDIDATES)
    n = db.query_one("SELECT COUNT(*) AS n FROM TODO_eval_result WHERE section_id=:sid", sid=opened_section.section_id)
    assert n["n"] == 3


@pytest.mark.p1
def test_push_before_open_rejected(push, noticed_section):
    _, xml = push.push_result(noticed_section.section_code, CANDIDATES)
    assert get_text(parse(xml), "//Code") != "0"


@pytest.mark.p1
def test_push_then_manual_fetch_consistent(push, opened_section, login_as, db):
    """推送与代理手动获取并存时，结果一致（以需求文档约定为准）"""
    push.push_result(opened_section.section_code, CANDIDATES)
    OpenEvalApi(login_as("agent")).fetch_eval_result(opened_section.section_id)
    rows = db.query("SELECT bidder_name FROM TODO_eval_result WHERE section_id=:sid ORDER BY ranking",
                    sid=opened_section.section_id)
    assert [r["bidder_name"] for r in rows] == [c["name"] for c in CANDIDATES]


@pytest.mark.p1
def test_push_missing_field(push, opened_section):
    bad = [{**CANDIDATES[0], "name": ""}]
    _, xml = push.push_result(opened_section.section_code, bad)
    assert get_text(parse(xml), "//Code") != "0"
