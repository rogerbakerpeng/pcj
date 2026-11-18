"""页面对象的框架基类（框架层，升级时会更新；项目学到的方法写在 pages/base_page.py）。"""


class UiBase:
    def __init__(self, page, env=None):
        self.page = page
        self.env = env or {}

    def ui_option(self, name, default=None):
        """当前环境在 project.yaml 的 ui 一节中声明的做法；没声明用默认值（默认值＝开发环境的做法）。"""
        return (self.env.get("ui") or {}).get(name, default)
