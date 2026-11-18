"""招标计划接口用例（产品基线）"""
import pytest
import yaml
from common.config import BASE_DIR

from api.plan_api import PlanApi

DATA = yaml.safe_load((BASE_DIR / "data" / "plan_cases.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def plan_api(login_as):
    return PlanApi(login_as("agent"))


@pytest.mark.api
@pytest.mark.p0
@pytest.mark.parametrize("c", DATA["add_valid"], ids=lambda c: c["case"])
def test_add_plan_success(plan_api, c):
    res = plan_api.add({"unit": c["unit"], "planNo": c["plan_no"]})
    assert res.get("success") is True          # TODO 按实际返回结构
    found = plan_api.query(planNo=c["plan_no"])
    assert found["total"] == 1


@pytest.mark.api
@pytest.mark.p1
@pytest.mark.parametrize("c", DATA["field_length"], ids=lambda c: c["case"])
def test_field_length(plan_api, c):
    value = "AUTO_" + "测" * (c["length"] - 5)
    res = plan_api.add({c["field"]: value})
    assert (res.get("success") is True) == (c["expect"] == "success")


@pytest.mark.api
@pytest.mark.p1
def test_audited_plan_cannot_edit(login_as, db, env):
    from flows.project_flow import ProjectFlow
    ctx = ProjectFlow(login_as, db, env).create_audited_plan()
    res = PlanApi(login_as("agent")).s.post("TODO/plan/update", json={"id": ctx.plan_id, "unit": "AUTO_改"})
    assert res.get("success") is False


@pytest.mark.api
@pytest.mark.p1
def test_other_unit_cannot_see_plan(login_as, db, env):
    from flows.project_flow import ProjectFlow
    ctx = ProjectFlow(login_as, db, env).create_audited_plan()
    res = PlanApi(login_as("bidder_1")).query(id=ctx.plan_id)
    assert res["total"] == 0
