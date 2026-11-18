"""招标计划 UI 冒烟（产品基线）"""
import time

import pytest

from pages.trade.plan_page import PlanPage


@pytest.mark.ui
@pytest.mark.p0
def test_add_and_search_plan(agent_page):
    p = PlanPage(agent_page)
    p.open()
    plan_no = f"AUTO_UI_{int(time.time())}"
    p.add_plan({"source": "TODO", "plan_no": plan_no, "unit": "AUTO_UI单位", "project_type": "TODO"})
    p.search(plan_no)
    assert p.row_count() == 1
