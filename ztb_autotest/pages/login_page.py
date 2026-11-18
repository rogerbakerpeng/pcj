"""登录。不同环境的登录方式可能不同，在 project.yaml 对应环境的 ui.login 中声明：

    form  本系统自己的登录页（默认，开发环境通常是这种）
    sso   跳转到统一登录（测试环境常见）

新发现一种登录方式时：在这里加一个 _login_<方式> 方法，在 project.yaml 声明，并登记到 pages/环境差异.md。
"""
from pages.base_page import BasePage


class LoginPage(BasePage):
    def login(self, base_url, username, password):
        mode = self.ui_option("login", "form")
        handler = getattr(self, f"_login_{mode}", None)
        if handler is None:
            raise NotImplementedError(
                f"project.yaml 中 ui.login 为「{mode}」，但 pages/login_page.py 里还没有 _login_{mode} 方法。"
                f"这是环境差异：先在该环境学习登录页，补上这个方法并登记到 pages/环境差异.md。")
        handler(base_url, username, password)

    def _login_form(self, base_url, username, password):
        # TODO: 按实际登录页补全；若有验证码，写明处理方式（关闭、万能码、环境变量 ZTB_LOGIN_CODE）
        self.page.goto(f"{base_url}/TODO/login")
        self.page.fill("#username", username)
        self.page.fill("#password", password)
        self.page.click("text=登录")

    # def _login_sso(self, base_url, username, password):
    #     """统一登录：访问系统地址后会跳到统一登录页，登录成功再跳回。在测试环境学习后补全。"""
    #     self.page.goto(base_url)
    #     ...
