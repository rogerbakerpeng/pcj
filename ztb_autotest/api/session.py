"""交易系统 HTTP 会话。接口地址与参数需按 F12 抓包结果补全（TODO）。"""
import requests

from common.logger import get_logger

log = get_logger("trade")


DEFAULT_TIMEOUT = 15  # 秒；地址不通时尽快失败，不要无限等待


class _TimeoutSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        return super().request(*args, **kwargs)


class TradeSession:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.http = _TimeoutSession()

    def login(self, username, password):
        # TODO: 按实际登录接口补全（若需 CA，测试环境开免 CA 登录开关）
        r = self.http.post(f"{self.base_url}/TODO/login", data={"username": username, "password": password})
        r.raise_for_status()
        log.info("登录成功：%s", username)

    def post(self, path, **kwargs):
        r = self.http.post(f"{self.base_url}/{path.lstrip('/')}", **kwargs)
        log.info("POST %s -> %s", path, r.status_code)
        r.raise_for_status()
        return r.json()

    def get(self, path, **kwargs):
        r = self.http.get(f"{self.base_url}/{path.lstrip('/')}", **kwargs)
        r.raise_for_status()
        return r.json()
