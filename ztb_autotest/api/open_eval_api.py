"""开评标情况：代理点击“获取评标结果”（② 交易系统调用评标接口）。"""


class OpenEvalApi:
    def __init__(self, session):
        self.s = session

    def fetch_eval_result(self, section_id):
        """对应页面按钮“获取评标结果”，交易系统后台会去调用评标系统接口。"""
        return self.s.post("TODO/openeval/getEvalResult", json={"sectionId": section_id})

    def get_result_detail(self, section_id):
        return self.s.post("TODO/openeval/resultDetail", json={"sectionId": section_id})
