from pages.base_page import BasePage


class PlanPage(BasePage):
    """我要招标 > 招标计划"""

    def open(self):
        self.open_menu("我要招标", "招标计划")

    def add_plan(self, data):
        self.click_button("新增招标计划")
        self.select_combo("数据来源", data["source"])
        self.fill_by_label("招标计划编号", data["plan_no"])
        self.fill_by_label("招标单位", data["unit"])
        self.select_combo("招标项目类型", data["project_type"])
        self.click_button("保存")

    def search(self, plan_no):
        self.fill_by_label("招标计划编号", plan_no)
        self.click_button("查询")

    def row_count(self):
        return self.frame.locator("table tbody tr").count()
