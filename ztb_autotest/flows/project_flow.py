"""业务流程层：造出某个阶段的标段，供后续用例做前置（规则见 AGENTS.md「长流程的前置数据」）。

    ctx = ProjectFlow(login_as, db, env).reach("已定标", sample_files=...)

每一步也可以单独调用：测「澄清」就停在公告发布，测 ①② 就造到开标完成，测标后就造到定标。
每一步按情况选做法：本系统无外部依赖的走业务接口；外部系统的结果由脚本扮演对方回写；
走不通的（CA 解密、等时间）只对这一步写库快进，并在 flows/造数能力.md 登记绕过了什么。
被测环节本身不在这里造，必须走真实业务。新阶段接在 STAGES 末尾补。"""
import time
from dataclasses import dataclass, field

from api.plan_api import PlanApi
from api.notice_api import NoticeApi
from api.bid_api import BidApi
from api.open_bid_api import OpenBidApi


@dataclass
class SectionContext:
    plan_id: str = ""
    notice_id: str = ""
    section_id: str = ""
    section_code: str = ""
    bidders: list = field(default_factory=list)


# 流程阶段，按顺序；reach() 依次执行到目标阶段。新阶段加在末尾，并在 flows/造数能力.md 登记
STAGES = [
    ("已审核的招标计划", "create_audited_plan"),
    ("已发布公告", "publish_notice"),
    ("已提交投标文件", "submit_bids"),
    ("已开标", "finish_open_bid"),
    ("已出评标结果", "receive_eval_result"),
    ("已定标", "confirm_winner"),
]


class ProjectFlow:
    def __init__(self, login_as, db, env):
        self.login_as = login_as
        self.db = db
        self.prefix = env.get("data_prefix", "AUTO_")

    def _name(self, label):
        return f"{self.prefix}{label}_{int(time.time() * 1000)}"

    def create_audited_plan(self, ctx=None):
        ctx = ctx or SectionContext()
        agent = PlanApi(self.login_as("agent"))
        res = agent.add({"planNo": self._name("PLAN"), "unit": self._name("单位")})  # TODO 字段
        ctx.plan_id = res["data"]["id"]
        PlanApi(self.login_as("supervisor")).audit(ctx.plan_id)
        return ctx

    def publish_notice(self, ctx=None):
        ctx = self.create_audited_plan(ctx)
        res = NoticeApi(self.login_as("agent")).create_from_plan(ctx.plan_id, {"title": self._name("公告")})
        ctx.notice_id = res["data"]["id"]
        ctx.section_id = res["data"]["sectionId"]
        ctx.section_code = res["data"]["sectionCode"]
        NoticeApi(self.login_as("agent")).publish(ctx.notice_id)
        return ctx

    def submit_bids(self, sample_files, ctx=None):
        """sample_files: {"bidder_1": 文件路径, ...}，路径用 samples.file("bid_normal_01") 取得"""
        ctx = self.publish_notice(ctx)
        for role, path in sample_files.items():
            BidApi(self.login_as(role)).upload_bid_file(ctx.section_id, path)
            ctx.bidders.append(role)
        return ctx

    def finish_open_bid(self, sample_files, ctx=None):
        """造到“开标完成”，这是 ① 评标取数的前置状态。"""
        ctx = self.submit_bids(sample_files, ctx)
        self.move_to_open_time(ctx.section_id)
        api = OpenBidApi(self.login_as("agent"))
        api.start_open(ctx.section_id)
        for role in ctx.bidders:
            api.decrypt(ctx.section_id, role)   # TODO 投标人ID；本地没有 CA 时改为写库快进解密，依据源码里解密方法写的表，并登记绕过了什么
        api.finish_open(ctx.section_id)
        return ctx

    def move_to_open_time(self, section_id):
        """不真等开标时间：改库把投标截止/开标时间提前。TODO 表名字段名"""
        self.db.execute(
            "UPDATE TODO_section SET open_time = NOW(), bid_end_time = NOW() WHERE id = :id",
            id=section_id,
        )

    # ---------------- 直达某个阶段 ----------------

    def reach(self, stage, sample_files=None):
        """从头造到 stage（STAGES 中的名称）。各步骤自己会先造好它的前一步。"""
        names = [n for n, _ in STAGES]
        if stage not in names:
            raise ValueError(f"未知阶段「{stage}」，已有：{names}。新阶段请加到 STAGES 末尾")
        method = getattr(self, dict(STAGES)[stage])
        needs_files = names.index(stage) >= names.index("已提交投标文件")
        return method(sample_files) if needs_files else method()

    # ---------------- 标后需求常用的阶段（项目接入或第一个标后需求时补全） ----------------

    def receive_eval_result(self, sample_files, ctx=None):
        """已出评标结果。评标是外部系统：本地由脚本扮演评标系统调用我们的回写接口（报文取自样本库）；
        产品默认由代理在「开评标情况」获取评标结果的，改为启动评标 mock 后调用我们的获取接口。"""
        ctx = self.finish_open_bid(sample_files, ctx)
        raise NotImplementedError("TODO：按本项目的评标结果回写或获取方式补全，并在 flows/造数能力.md 登记")

    def confirm_winner(self, sample_files, ctx=None):
        """已定标。本系统的步骤，走业务接口（定标、中标候选人公示等按本项目流程）。"""
        ctx = self.receive_eval_result(sample_files, ctx)
        raise NotImplementedError("TODO：按本项目的定标流程补全，并在 flows/造数能力.md 登记")
