"""选择自动化用的浏览器：不在自测过程中下载浏览器。

选择顺序：
  1. Playwright 自带的 Chromium 已安装 → 用它（版本与 Playwright 严格匹配，最稳定）
  2. 本机已装的 Chrome → channel="chrome"
  3. 本机已装的 Edge   → channel="msedge"
  4. 都没有 → 报「环境未配置」，由人安装（python -m playwright install chromium），AI 不执行下载

无论用哪一个，Playwright 都是另起一个独立进程、使用临时的空白用户目录，
不会动你正在使用的浏览器窗口、标签页和登录状态。默认无界面运行，屏幕上不会弹出窗口。
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

from common.config import BASE_DIR, EnvNotConfigured

RUNTIME_DIR = BASE_DIR / ".runtime"
CHOICE_FILE = RUNTIME_DIR / "browser.json"


def _system_browser(names_win, names_mac, names_linux):
    if sys.platform.startswith("win"):
        roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        for root in filter(None, roots):
            for rel in names_win:
                p = Path(root) / rel
                if p.exists():
                    return str(p)
    elif sys.platform == "darwin":
        for p in names_mac:
            if Path(p).exists():
                return p
    else:
        for name in names_linux:
            found = shutil.which(name)
            if found:
                return found
    return None


def find_chrome():
    return _system_browser(["Google/Chrome/Application/chrome.exe"],
                           ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
                           ["google-chrome", "google-chrome-stable"])


def find_edge():
    return _system_browser(["Microsoft/Edge/Application/msedge.exe"],
                           ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
                           ["microsoft-edge", "microsoft-edge-stable"])


def choose(bundled_path=None):
    """返回 {"channel": None|"chrome"|"msedge", "detail": 说明}；都不可用时抛 EnvNotConfigured。
    bundled_path：Playwright 自带 Chromium 的可执行文件路径（playwright.chromium.executable_path）。"""
    if bundled_path and Path(bundled_path).exists():
        return {"channel": None, "detail": f"Playwright 自带 Chromium：{bundled_path}"}
    chrome = find_chrome()
    if chrome:
        return {"channel": "chrome", "detail": f"本机 Chrome：{chrome}"}
    edge = find_edge()
    if edge:
        return {"channel": "msedge", "detail": f"本机 Edge：{edge}"}
    raise EnvNotConfigured("浏览器（未找到 Playwright 自带 Chromium，也未找到本机 Chrome / Edge；"
                           "请人工执行 python -m playwright install chromium，或安装 Chrome）")


def save_choice(choice):
    RUNTIME_DIR.mkdir(exist_ok=True)
    CHOICE_FILE.write_text(json.dumps({**choice, "time": int(time.time())}, ensure_ascii=False, indent=1), encoding="utf-8")


def load_choice():
    """读取准备度检查时选定的浏览器；没有或文件损坏时返回 None。"""
    try:
        return json.loads(CHOICE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
