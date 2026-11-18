"""页面通用方法：登录后的菜单、内容 iframe、各类控件的操作和取值、提示框和弹窗。

这里的方法是所有需求共用的，项目接入时学习一次、之后持续沉淀（见 AGENTS.md「页面通用方法与环境差异」）。

环境差异的写法：开发环境和测试环境大体一样，个别细节不同（如测试环境接了统一登录）。
不同的地方**按配置分支，不按环境名分支**——在 project.yaml 对应环境的 ui 一节声明做法，方法里用 self.ui_option 取：

    # project.yaml
    envs:
      local: {ui: {login: form}}
      test:  {ui: {login: sso}}

    # 方法里
    if self.ui_option("login", "form") == "sso": ...

每处差异同时登记到 pages/环境差异.md。
"""


from common.ui_base import UiBase


class BasePage(UiBase):
    """本项目学到的页面通用方法写在这里（项目层，升级不会覆盖）。构造方法和 ui_option 在框架基类 common/ui_base.py。"""
    # 主内容 iframe，TODO 按实际页面 src 关键字调整
    CONTENT_FRAME = "iframe[src*='pages']"

    @property
    def frame(self):
        return self.page.frame_locator(self.CONTENT_FRAME)

    def fill_by_label(self, label, value):
        self.frame.locator(f"xpath=//*[normalize-space(text())='{label}：']/following::input[1]").fill(value)

    def select_combo(self, label, option_text):
        """自定义下拉（带 × 和箭头的那种，不是原生 select）：先点开再按文字选。"""
        self.frame.locator(f"xpath=//*[normalize-space(text())='{label}：']/following::input[1]").click()
        self.frame.get_by_text(option_text, exact=True).last.click()

    def click_button(self, text):
        self.frame.get_by_role("button", name=text).click()

    def toast_text(self):
        # TODO: 按实际提示框选择器调整
        return self.page.locator(".mini-messagebox-content, .fui-toast").first.inner_text()

    def open_menu(self, *path):
        """左侧菜单逐级点击，如 open_menu('我要招标', '招标计划')"""
        for name in path:
            self.page.get_by_text(name, exact=False).first.click()
