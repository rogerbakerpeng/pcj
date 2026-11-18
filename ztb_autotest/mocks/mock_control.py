"""测试脚本中控制 Mock 评标服务。"""
import requests


class EvalMock:
    def __init__(self, control_url):
        self.url = control_url.rstrip("/")

    def set_scenario(self, name):
        requests.post(f"{self.url}/scenario", json={"scenario": name}, timeout=5).raise_for_status()

    def received(self):
        return requests.get(f"{self.url}/requests", timeout=5).json()

    def reset(self):
        requests.post(f"{self.url}/reset", timeout=5)
