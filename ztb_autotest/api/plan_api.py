"""招标计划：新增、查询、导出、审核。"""


class PlanApi:
    def __init__(self, session):
        self.s = session

    def add(self, data):
        # TODO: 抓包补全“新增招标计划-保存”接口
        return self.s.post("TODO/plan/add", json=data)

    def query(self, **conditions):
        # 条件：数据来源、招标计划编号、招标单位、项目类型、受理人员、监管部门
        return self.s.post("TODO/plan/list", json=conditions)

    def export(self, **conditions):
        return self.s.http.post(f"{self.s.base_url}/TODO/plan/export", json=conditions)

    def audit(self, plan_id, passed=True, opinion="自动化审核"):
        return self.s.post("TODO/plan/audit", json={"id": plan_id, "pass": passed, "opinion": opinion})
