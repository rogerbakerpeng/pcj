"""投标文件上传：样本库数据驱动（产品基线）。样本登记在 samples/index.yaml 的 files 中，类别 bid。"""
import pytest

from api.bid_api import BidApi
from common import samples
from flows.project_flow import ProjectFlow

BID_SAMPLES = samples.entries("files", category="bid")


@pytest.fixture(scope="module")
def section(login_as, db, env):
    return ProjectFlow(login_as, db, env).publish_notice()


@pytest.mark.api
@pytest.mark.p1
@pytest.mark.parametrize("s", BID_SAMPLES, ids=lambda s: s["id"])
def test_upload_samples(login_as, section, s):
    if not samples.available(s) or s.get("expect") in (None, "TODO"):
        pytest.skip(f"样本未提供或预期未确认：{s['id']}（{s.get('desc', '')}），见 samples/index.yaml")
    path = samples.file(s["id"])
    res = BidApi(login_as("bidder_1")).upload_bid_file(section.section_id, path)
    if s["expect"] == "success":
        assert res.get("success") is True
    else:
        assert res.get("success") is False
        assert s["msg"] in res.get("message", "")
