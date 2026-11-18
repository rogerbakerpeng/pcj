"""样本库：测试用的报文、业务文件、第三方资料统一放在 samples/ 下，统一从这里取。

    from common import samples
    samples.message("eval", "获取评标结果", "normal")              # 返回报文文本（默认 resp）；没有返回 None
    samples.message("eval", "评标取数_项目信息", "normal", "req")   # 请求报文
    samples.file("bid_normal_01")                                 # 业务文件路径（Path）；未提供时抛 SampleMissing
    samples.entries("files", category="bid")                      # 索引中的条目，用于数据驱动
    samples.third_party("ntko_save_req")                          # 第三方资料路径

目录约定：
    samples/index.yaml                                   索引，先读它
    samples/messages/<外部系统>/<接口>/<场景>.req.xml      请求报文
    samples/messages/<外部系统>/<接口>/<场景>.resp.xml     返回报文（页面接口抓包可用 .json）
    samples/files/<类别>/...                              业务文件：tender 招标文件 / bid 投标文件 / doc 文档样本
    samples/third_party/<名称>/...                        第三方提供的资料

检查索引与文件是否一致：python -m common.samples
"""
import sys
from pathlib import Path

import yaml

from common.config import BASE_DIR

SAMPLES_DIR = BASE_DIR / "samples"
INDEX_FILE = SAMPLES_DIR / "index.yaml"
MESSAGE_PARTS = ("req", "resp")


class SampleMissing(Exception):
    """样本还没提供。属于测试数据问题：请人把文件放进 samples/ 并在 index.yaml 登记，不要自己伪造。"""


MESSAGE_EXTS = ("xml", "json")


def load_index():
    if not INDEX_FILE.exists():
        return {}
    return yaml.safe_load(INDEX_FILE.read_text(encoding="utf-8")) or {}


def message_path(dep, interface, scenario, part="resp"):
    if part not in MESSAGE_PARTS:
        raise ValueError(f"part 只能是 {MESSAGE_PARTS}")
    d = SAMPLES_DIR / "messages" / dep / interface
    for ext in MESSAGE_EXTS:                      # WebService 报文用 xml，页面接口抓包用 json
        p = d / f"{scenario}.{part}.{ext}"
        if p.exists():
            return p
    return d / f"{scenario}.{part}.{MESSAGE_EXTS[0]}"


def message(dep, interface, scenario, part="resp", required=False):
    """读取一份报文。不存在时返回 None；required=True 时抛 SampleMissing。"""
    p = message_path(dep, interface, scenario, part)
    if p.exists():
        return p.read_text(encoding="utf-8")
    if required:
        raise SampleMissing(f"缺少报文样本：{p.relative_to(BASE_DIR)}")
    return None


def scenarios(dep, interface, part="resp"):
    """某个接口已有的场景名。"""
    d = SAMPLES_DIR / "messages" / dep / interface
    if not d.exists():
        return []
    return sorted({p.name[:-len(f".{part}.{ext}")] for ext in MESSAGE_EXTS for p in d.glob(f"*.{part}.{ext}")})


def entries(section, **filters):
    """索引中某一节（messages / files / third_party）的条目，可按字段过滤。"""
    rows = load_index().get(section) or []
    return [r for r in rows if all(r.get(k) == v for k, v in filters.items())]


def _by_id(section, sample_id):
    for r in load_index().get(section) or []:
        if r.get("id") == sample_id:
            return r
    raise SampleMissing(f"samples/index.yaml 的 {section} 中没有 id 为「{sample_id}」的条目")


def _path_of(entry):
    p = SAMPLES_DIR / str(entry.get("path", ""))
    if "TODO" in str(entry.get("path", "TODO")) or not p.exists():
        raise SampleMissing(f"样本「{entry.get('id')}」（{entry.get('desc', '')}）还没提供：应放在 samples/{entry.get('path')}")
    return p


def available(entry):
    """索引条目对应的文件是否已经放进来。"""
    path = str(entry.get("path", "TODO"))
    return "TODO" not in path and (SAMPLES_DIR / path).exists()


def file(sample_id):
    """业务文件的路径。"""
    return _path_of(_by_id("files", sample_id))


def third_party(sample_id):
    """第三方资料的路径。"""
    return _path_of(_by_id("third_party", sample_id))


# ---------- 检查：python -m common.samples ----------

def check():
    idx = load_index()
    problems, ok = [], 0
    registered = set()
    for m in idx.get("messages") or []:
        for part in m.get("parts") or ["resp"]:
            p = message_path(m.get("dep", ""), m.get("interface", ""), m.get("scenario", ""), part)
            registered.add(p.resolve())
            if p.exists():
                ok += 1
            else:
                problems.append(f"已登记但文件不存在：{p.relative_to(SAMPLES_DIR)}")
    todo = 0
    for section in ("files", "third_party"):
        for e in idx.get(section) or []:
            path = str(e.get("path", "TODO"))
            p = SAMPLES_DIR / path
            registered.add(p.resolve())
            if "TODO" in path:
                todo += 1
            elif p.exists():
                ok += 1
            else:
                problems.append(f"已登记但文件不存在：{path}")
    skip = {"index.yaml", "README.md", ".gitkeep"}
    for p in SAMPLES_DIR.rglob("*"):
        if p.is_file() and p.name not in skip and p.resolve() not in registered:
            problems.append(f"文件未登记到 index.yaml：{p.relative_to(SAMPLES_DIR)}")
    handwritten = sum(1 for m in idx.get("messages") or [] if "手写" in str(m.get("source", "")))
    print(f"样本库：已就绪 {ok} 个；待提供（TODO）{todo} 个；报文中手写待录制 {handwritten} 条")
    for line in problems:
        print("  ✘ " + line)
    if not problems:
        print("  ✔ 索引与文件一致")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(check())
