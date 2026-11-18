"""招标公告：新增、发布（引用招标计划）。"""


class NoticeApi:
    def __init__(self, session):
        self.s = session

    def create_from_plan(self, plan_id, data):
        return self.s.post("TODO/notice/add", json={"planId": plan_id, **data})

    def publish(self, notice_id):
        return self.s.post("TODO/notice/publish", json={"id": notice_id})
