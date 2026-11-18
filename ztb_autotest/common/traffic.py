"""页面接口录制：走页面造数的同时，把页面发出的接口请求和返回存进样本库，不用另外再抓一次包。

    from common import traffic

    with traffic.record(page, "公告发布"):          # 包住造数流程中的一步
        page.click("text=发布")

- **缺才录**：样本库里还没有这个接口的报文时才录，已有的不覆盖；要重新录，运行前设置环境变量 ZTB_RECORD=1
- 只录页面发出的 XHR / fetch 请求（不录图片、样式、脚本）
- 自动脱敏：去掉 Cookie、Authorization、Token 等请求头；字段名像口令的值替换为 ***
- 存到 samples/messages/<dep>/<接口>/<场景>_<序号>_<地址末段>.req.json / .resp.json，并在 samples/index.yaml 登记
- 带防重放签名的接口（如 /rest 请求里的 reqtime、paramsign）录下来只能用于核对字段，不能脱离页面重放：
  这种接口的造数仍走页面，传 replayable=False，登记时会注明
"""
import contextlib
import datetime
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
INDEX = SAMPLES_DIR / "index.yaml"
DROP_HEADERS = {"cookie", "set-cookie", "authorization", "token", "x-token", "x-auth-token", "proxy-authorization"}
SECRET_KEY = re.compile(r"(pass(word)?|pwd|mima|secret|口令|密码)", re.I)
MAX_BODY = 200_000


def _mask(obj):
    if isinstance(obj, dict):
        return {k: ("***" if SECRET_KEY.search(str(k)) and v not in (None, "") else _mask(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mask(v) for v in obj]
    return obj


def _body(text, content_type=""):
    """尽量解析成 JSON 或表单字段，便于阅读和脱敏；解析不了保留原文（过长截断）。"""
    if text is None:
        return None
    text = text[:MAX_BODY]
    try:
        return _mask(json.loads(text))
    except (ValueError, TypeError):
        pass
    if "form" in (content_type or "") or ("=" in text and "&" in text and "<" not in text[:50]):
        return _mask(dict(parse_qsl(text, keep_blank_values=True)))
    return text


def _headers(h):
    """去掉身份凭证和浏览器自带的无关请求头（sec-*、user-agent 等），只留和接口有关的。"""
    return {k: v for k, v in (h or {}).items()
            if k.lower() not in DROP_HEADERS and not k.lower().startswith("sec-") and k.lower() != "user-agent"}


def _safe(name):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("_")[:60] or "root"


def _exists(dep, interface):
    d = SAMPLES_DIR / "messages" / dep / interface
    return d.exists() and any(d.glob("*.req.*"))


def _register(dep, interface, scenario, replayable, desc):
    """在 index.yaml 的 messages 一节末尾追加一行（已登记的不重复）。保留原文件的注释和格式。"""
    if not INDEX.exists():
        return
    text = INDEX.read_text(encoding="utf-8")
    key = f"dep: {dep}, interface: {interface}, direction: 本系统页面, scenario: {scenario},"
    if key in text:
        return
    note = desc + ("；带防重放签名，仅供核对字段，不能脱离页面重放" if not replayable else "")
    line = (f"  - {{{key} parts: [req, resp], "
            f"source: 造数流程录制 {datetime.date.today():%Y-%m-%d}, desc: {note}}}\n")
    marker = "\n# ---------- 业务文件"
    pos = text.find(marker)
    text = text[:pos].rstrip("\n") + "\n" + line + text[pos:] if pos >= 0 else text.rstrip("\n") + "\n" + line
    INDEX.write_text(text, encoding="utf-8")


@contextlib.contextmanager
def record(page, interface, scenario="normal", dep="trade", replayable=True, desc=""):
    """包住造数流程中的一步，录下这一步页面发出的接口请求。缺才录；ZTB_RECORD=1 时强制重录。"""
    force = os.getenv("ZTB_RECORD") == "1"
    if _exists(dep, interface) and not force:
        yield []
        return
    captured = []

    def on_response(resp):
        req = resp.request
        if req.resource_type not in ("xhr", "fetch"):
            return
        try:
            resp_text = resp.text()
        except Exception:  # noqa: BLE001  重定向、二进制下载等拿不到正文
            resp_text = None
        captured.append({
            "request": {"method": req.method, "url": req.url, "headers": _headers(req.headers),
                        "body": _body(req.post_data, req.headers.get("content-type", ""))},
            "response": {"status": resp.status, "headers": _headers(resp.headers),
                         "body": _body(resp_text, resp.headers.get("content-type", ""))},
        })

    page.on("response", on_response)
    try:
        yield captured
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:  # noqa: BLE001
            pass
    if not captured:
        return
    d = SAMPLES_DIR / "messages" / dep / interface
    d.mkdir(parents=True, exist_ok=True)
    for n, item in enumerate(captured, 1):
        tail = _safe(urlparse(item["request"]["url"]).path.rsplit("/", 1)[-1])
        name = f"{scenario}_{n:02d}_{tail}"
        for part, key in (("req", "request"), ("resp", "response")):
            (d / f"{name}.{part}.json").write_text(json.dumps(item[key], ensure_ascii=False, indent=1), encoding="utf-8")
        _register(dep, interface, name, replayable, desc or f"{interface} 第 {n} 个请求（{tail}）")
