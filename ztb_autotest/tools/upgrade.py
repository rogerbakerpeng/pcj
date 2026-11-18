"""框架升级：把新版本的 ztb_autotest 合并进本项目，只更新框架，不覆盖项目自己的内容。

    python tools/upgrade.py <新版本的 zip 或解压后的目录>            # 先看会改什么（不改任何文件）
    python tools/upgrade.py <新版本的 zip 或解压后的目录> --apply    # 确认后执行

旧版本项目（还没有本脚本）第一次升级：把新版本解压到项目外面，用新版本里的脚本，指定项目目录：
    python <新版本目录>/tools/upgrade.py <新版本目录> --project <项目的 ztb_autotest 目录>

分类见根目录 framework.yaml：
  框架层  直接替换为新版本（本地改过的会提示，替换前已备份）
  模板层  项目没改过的直接更新；改过的保留项目版本，新模板放到 .framework/pending/<版本>/ 供对照合并
  项目层  从不改动（新版本里新增的占位文件会补上）

每次执行前把要替换、删除的文件备份到 .framework/backup/<旧版本>_to_<新版本>_<时间>/。
.framework/installed.json 记录每个文件「框架装进来时」的样子，用来判断项目有没有改过它。

框架维护者发布新版本前执行一次：python tools/upgrade.py --record   （重新生成 installed.json 后再打包）
"""
import argparse
import os
import fnmatch
import hashlib
import json
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import yaml


def _console_utf8():
    """Windows 命令行默认是 GBK，输出 ✔ ✘ 等字符会报错：改为无法显示的字符用 ? 代替，不中断。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


_console_utf8()

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / ".framework"
RECORD = STATE_DIR / "installed.json"
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".git", ".runtime", ".framework"}
SKIP_NAMES = {".env"}
MAX_DELETE = 5            # 一次要删除的框架文件超过这个数就不删，防止新版本包不完整时误删


def sha(path):
    """文件指纹。文本文件先把 CRLF 换成 LF：Windows 上 git 会自动转换换行符，不能因此认为文件被改过。"""
    data = path.read_bytes()
    if b"\0" not in data[:8192]:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def load_manifest(root):
    f = root / "framework.yaml"
    if not f.exists():
        return None
    return yaml.safe_load(f.read_text(encoding="utf-8")) or {}


def _match(rel, patterns):
    for p in patterns or []:
        if p.endswith("/**"):
            if rel.startswith(p[:-2]):
                return True
        elif fnmatch.fnmatch(rel, p):
            return True
    return False


def classify(rel, manifest):
    """framework / template / project。先认精确列出的框架文件，再认项目层，再按目录归类；都不是的按项目层。"""
    fw = manifest.get("framework") or []
    if rel in fw:
        return "framework"
    if _match(rel, manifest.get("project")):
        return "project"
    if _match(rel, fw):
        return "framework"
    if _match(rel, manifest.get("template")):
        return "template"
    return "project"


def walk(root):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(part in SKIP_PARTS for part in p.relative_to(root).parts) or p.name in SKIP_NAMES:
            continue
        yield rel, p


def load_record():
    if RECORD.exists():
        return json.loads(RECORD.read_text(encoding="utf-8"))
    return None


def write_record(version, files):
    STATE_DIR.mkdir(exist_ok=True)
    RECORD.write_text(json.dumps({"version": version, "files": files}, ensure_ascii=False, indent=1, sort_keys=True),
                      encoding="utf-8")


def record_current():
    manifest = load_manifest(ROOT)
    files = {rel: sha(p) for rel, p in walk(ROOT) if classify(rel, manifest) in ("framework", "template")}
    write_record(manifest.get("version"), files)
    print(f"已记录 {len(files)} 个框架层和模板层文件（版本 {manifest.get('version')}）→ {RECORD.relative_to(ROOT)}")


def _zip_name(info):
    """zip 里的中文文件名：带 UTF-8 标志的直接用；否则按 UTF-8、再按 GBK（Windows 自带压缩）还原。"""
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437")
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return info.filename


def extract_zip(src, dst):
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            name = _zip_name(info)
            target = (dst / name).resolve()
            base = dst.resolve()
            if os.path.normcase(os.path.commonpath([str(target), str(base)])) != os.path.normcase(str(base)):
                raise SystemExit(f"zip 中有不安全的路径：{name}")
            if info.is_dir() or name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as fsrc, open(target, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)


def open_source(src):
    """返回新版本的根目录（含 framework.yaml 的目录）。zip 解压到临时目录。"""
    src = Path(str(src).strip('"')).expanduser().resolve()
    if src.is_file() and src.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="ztb_upgrade_"))
        extract_zip(src, tmp)
        src = tmp
    if not src.is_dir():
        raise SystemExit(f"找不到新版本：{src}")
    cands = [src] + [p.parent for p in src.rglob("framework.yaml")]
    for c in cands:
        if (c / "framework.yaml").exists():
            return c
    raise SystemExit("新版本里没有 framework.yaml：它不是支持升级的版本，请向框架维护者要新包")


def plan(new_root):
    new_manifest = load_manifest(new_root)
    old_manifest = load_manifest(ROOT) or {}
    record = load_record()
    recorded = (record or {}).get("files", {})
    actions = {k: [] for k in ("add", "replace", "replace_local_changed", "template_update",
                               "template_pending", "delete", "same")}
    new_files = {}
    for rel, p in walk(new_root):
        new_files[rel] = sha(p)
        cls = classify(rel, new_manifest)
        local = ROOT / rel
        if not local.exists():
            actions["add"].append((rel, cls))
            continue
        local_sha = sha(local)
        if local_sha == new_files[rel]:
            actions["same"].append((rel, cls))
            continue
        if cls == "project":
            continue
        if cls == "framework":
            changed = rel in recorded and recorded[rel] != local_sha
            unknown = rel not in recorded
            actions["replace_local_changed" if (changed or unknown and record is not None) else "replace"].append((rel, cls))
            continue
        # 模板：项目没改过（与装入时一致）才更新；框架这次没动这个模板的，保留项目版本、不用合并
        if rel in recorded and recorded[rel] == local_sha:
            actions["template_update"].append((rel, cls))
        elif rel in recorded and recorded[rel] == new_files[rel]:
            actions["same"].append((rel, cls))
        else:
            actions["template_pending"].append((rel, cls))
    # 新版本已去掉的框架层文件：只删框架装进来、且项目没改过的
    for rel, p in walk(ROOT):
        if rel in new_files:
            continue
        if classify(rel, old_manifest or new_manifest) != "framework":
            continue
        if rel in recorded and recorded[rel] == sha(p):
            actions["delete"].append((rel, "framework"))
    return new_manifest, old_manifest, record, actions, new_files


def show(actions, old_v, new_v, has_record):
    print(f"框架升级：{old_v or '未知（没有 framework.yaml 的旧版本）'} → {new_v}\n")
    if not has_record:
        print("  注意：本项目没有安装记录（.framework/installed.json），无法判断模板文件是否被改过，")
        print("        内容不同的模板一律保留项目版本、新模板放到 pending 里对照合并。\n")
    rows = [
        ("add", "新增文件"),
        ("replace", "框架层：替换为新版本" + ("" if has_record else "（没有安装记录，无法判断本地是否改过；旧内容已备份）")),
        ("replace_local_changed", "框架层：本地改过，仍会替换（旧内容已备份，项目需要的改动请移到 项目规则.md 或项目层）"),
        ("template_update", "模板层：项目没改过，直接更新"),
        ("template_pending", "模板层：项目改过，保留项目版本；新模板放到 pending 供对照合并"),
        ("delete", "框架层：新版本已去掉，删除"),
    ]
    for key, title in rows:
        items = actions[key]
        print(f"  {title}：{len(items)}")
        for rel, cls in items[:40]:
            print(f"      {rel}" + (f"（{ {'framework': '框架层', 'template': '模板层', 'project': '项目层'}[cls] }）" if key == "add" else ""))
        if len(items) > 40:
            print(f"      …… 另 {len(items) - 40} 个")
    print(f"  未变化：{len(actions['same'])}")


def apply(new_root, new_manifest, old_manifest, record, actions, new_files):
    old_v = (old_manifest or {}).get("version") or "unknown"
    new_v = new_manifest.get("version")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = STATE_DIR / "backup" / f"{old_v}_to_{new_v}_{stamp}"
    pending = STATE_DIR / "pending" / str(new_v)

    def keep(rel):
        src = ROOT / rel
        if src.exists():
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def copy_in(rel):
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(new_root / rel, dst)
        except OSError as e:
            raise SystemExit(f"写入失败：{rel}（{e}）。\n"
                             "Windows 上常见原因：文件正被编辑器或其他程序占用；或路径太长（超过 260 字符），"
                             "可把项目放到较短的目录下，或在系统中开启长路径支持。已替换的文件可从备份目录恢复。")

    for rel, _ in actions["replace"] + actions["replace_local_changed"] + actions["template_update"]:
        keep(rel)
        copy_in(rel)
    for rel, _ in actions["add"]:
        copy_in(rel)
    for rel, _ in actions["template_pending"]:
        dst = pending / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(new_root / rel, dst)
    for rel, _ in actions["delete"]:
        keep(rel)
        (ROOT / rel).unlink()

    # 安装记录：框架层、模板层按「新版本装进来时的样子」记录；保留了项目版本的模板记新模板，
    # 这样人按新模板合并后，下次升级就能识别为「没改过」
    files = {}
    for rel, h in new_files.items():
        if classify(rel, new_manifest) in ("framework", "template"):
            files[rel] = h
    write_record(new_v, files)

    print(f"\n已升级到 {new_v}。")
    if backup.exists():
        print(f"  被替换、删除的旧文件备份在：{backup.relative_to(ROOT)}")
    if actions["template_pending"]:
        print(f"  {len(actions['template_pending'])} 个模板需要对照合并，新模板在：{pending.relative_to(ROOT)}")
        print("  可以对 AI 说：")
        print(f"    先完整阅读 ztb_autotest/AGENTS.md。框架已升级到 {new_v}，{pending.relative_to(ROOT).as_posix()} 下是新版本模板。")
        print("    逐个与项目中的同名文件对照：保留本项目补全和沉淀的内容，吸收新模板的结构和改进；")
        print("    拿不准的列出来问我。合并完删除 pending 目录。")
    print("  接着执行：python tools/preflight.py --common   和   pytest --collect-only -q   确认能正常加载")


def main():
    ap = argparse.ArgumentParser(description="框架升级（只更新框架，不覆盖项目内容）")
    ap.add_argument("source", nargs="?", help="新版本的 zip 或解压后的目录")
    ap.add_argument("--apply", action="store_true", help="执行升级；不加时只显示会改什么")
    ap.add_argument("--project", help="要升级的项目 ztb_autotest 目录；默认是本脚本所在的项目。旧版本项目没有本脚本时，用新版本里的脚本加这个参数")
    ap.add_argument("--allow-delete", action="store_true", help="允许一次删除较多的框架文件（一般不需要）")
    ap.add_argument("--record", action="store_true", help="框架维护者用：记录当前框架层和模板层文件，发布前执行")
    a = ap.parse_args()
    if a.project:
        global ROOT, STATE_DIR, RECORD
        ROOT = Path(a.project.strip('"')).expanduser().resolve()
        if not (ROOT / "AGENTS.md").exists():
            raise SystemExit(f"{ROOT} 看起来不是 ztb_autotest 目录（没有 AGENTS.md）")
        STATE_DIR = ROOT / ".framework"
        RECORD = STATE_DIR / "installed.json"
    if a.record:
        record_current()
        return 0
    if not a.source:
        ap.error("请给出新版本的 zip 或目录")
    new_root = open_source(a.source)
    if new_root.resolve() == ROOT:
        raise SystemExit("新版本目录就是当前项目目录，请把新版本解压到别处")
    new_manifest, old_manifest, record, actions, new_files = plan(new_root)
    show(actions, (old_manifest or {}).get("version"), new_manifest.get("version"), record is not None)
    if len(actions["delete"]) > MAX_DELETE and not a.allow_delete:
        print(f"\n要删除的框架文件有 {len(actions['delete'])} 个，超过 {MAX_DELETE} 个，可能是新版本包不完整或文件名乱码。")
        print("请先确认新版本包没有问题；确实要删除时加 --allow-delete。这次不会删除任何文件。")
        actions["delete"] = []
    if not a.apply:
        print("\n以上为预览，没有改动任何文件。确认后加 --apply 执行。")
        return 0
    apply(new_root, new_manifest, old_manifest, record, actions, new_files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
