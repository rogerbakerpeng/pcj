"""交易系统共用前置数据（产品基线和项目用例都可直接使用）。"""
import pytest

from common import samples

# 三家投标人各用一份正常投标文件，样本登记在 samples/index.yaml（id: bid_normal_01～03）
NORMAL_BID_IDS = {"bidder_1": "bid_normal_01", "bidder_2": "bid_normal_02", "bidder_3": "bid_normal_03"}


def normal_bid_files():
    try:
        return {role: str(samples.file(sid)) for role, sid in NORMAL_BID_IDS.items()}
    except samples.SampleMissing as e:
        pytest.skip(f"缺少投标文件样本：{e}")


@pytest.fixture(scope="module")
def opened_section(login_as, db, env):
    """已开标完成的标段（① 评标取数、② 获取评标结果、③ 主动推送的共同前置）"""
    from flows.project_flow import ProjectFlow
    return ProjectFlow(login_as, db, env).finish_open_bid(normal_bid_files())


@pytest.fixture(scope="module")
def noticed_section(login_as, db, env):
    """公告已发布、未开标的标段（验证开标前取数、推送被拒绝）"""
    from flows.project_flow import ProjectFlow
    return ProjectFlow(login_as, db, env).publish_notice()


@pytest.fixture(scope="session")
def section_at(login_as, db, env):
    """返回函数 section_at("<阶段>", shared=True) -> 造到该阶段的标段（阶段见 flows/project_flow.py 的 STAGES）。

    shared=True（默认）：整次运行同一阶段只造一份，**只读**的用例共用，长链路不用每条用例重走
    shared=False：新造一份，给会改变状态的用例用（如测定标、测撤回）
        def test_中标公示(section_at):
            ctx = section_at("已定标")
    """
    from flows.project_flow import ProjectFlow
    cache = {}

    def _get(stage, shared=True):
        if shared and stage in cache:
            return cache[stage]
        ctx = ProjectFlow(login_as, db, env).reach(stage, sample_files=normal_bid_files())
        if shared:
            cache[stage] = ctx
        return ctx

    return _get
