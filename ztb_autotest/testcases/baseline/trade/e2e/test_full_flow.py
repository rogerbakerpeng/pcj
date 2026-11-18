"""全链路场景（联调环境：真实评标系统 + 工具生成文件）。少而精。
运行：pytest -m e2e --env uat"""
import pytest

# 全链路：只在接了真实评标系统的环境运行（deps.eval 为 real）
pytestmark = [pytest.mark.e2e, pytest.mark.needs("eval", mode="real")]


@pytest.mark.p0
def test_normal_flow():
    """计划 → 公告 → 投标(工具文件) → 开标 → ①评标取数 → 专家评标 → ②代理获取结果 → 公示"""
    pytest.skip("TODO：联调环境就绪后实现；评标环节需评标系统提供测试专家账号或自动打分接口")


@pytest.mark.p1
def test_failed_bid_flow():
    """有效投标人不足 3 家 → 流标 → 重新招标"""
    pytest.skip("TODO")


@pytest.mark.p1
def test_re_evaluation_flow():
    """评标结果退回 → 重新评标 → 代理再次获取结果"""
    pytest.skip("TODO")
