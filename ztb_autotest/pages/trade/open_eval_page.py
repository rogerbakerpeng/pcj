from pages.base_page import BasePage


class OpenEvalPage(BasePage):
    """开评标情况（代理）：② 获取评标结果"""

    def open(self):
        self.open_menu("开标评标", "开评标情况")   # TODO 菜单名按实际调整

    def fetch_result(self, section_name):
        self.frame.get_by_text(section_name).first.click()
        self.click_button("获取评标结果")

    def candidate_names(self):
        return self.frame.locator(".candidate-table td.bidder-name").all_inner_texts()  # TODO 选择器
