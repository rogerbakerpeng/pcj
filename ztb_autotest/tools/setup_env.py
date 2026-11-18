"""环境检查与初始化（Windows / Linux / macOS 通用）。

用法：在 ztb_autotest 根目录执行
    python tools/setup_env.py            检查环境；有 git 时自动初始化仓库
    python tools/setup_env.py --no-git   只检查，不做 git 初始化

检查内容：
  1. Python 版本（需要 3.9+）
  2. git：有则初始化仓库并做首次提交；没有则跳过（不影响使用，只是没有版本记录）
  3. 依赖包是否已安装（只提示，不自动安装）
  4. 各项目的 source_repos（被测系统源码路径）是否可访问
"""
import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


def _console_utf8():
    """Windows 命令行默认是 GBK，输出 ✔ ✘ 等字符会报错：改为无法显示的字符用 ? 代替，不中断。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


_console_utf8()

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = {  # 导入名: pip 包名
    "pytest": "pytest", "playwright": "playwright", "requests": "requests", "yaml": "PyYAML",
    "lxml": "lxml", "zeep": "zeep", "xmlschema": "xmlschema", "sqlalchemy": "SQLAlchemy", "flask": "flask",
}


def ok(msg):
    print(f"  [OK]   {msg}")


def warn(msg):
    print(f"  [提示] {msg}")


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def check_python():
    print("1. Python")
    v = sys.version_info
    if v >= (3, 9):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        warn(f"当前 Python {v.major}.{v.minor}，建议 3.9 及以上")


def check_git(do_init):
    print("2. git")
    if not shutil.which("git"):
        warn("未安装 git：可以正常使用框架，但 AI 的修改没有版本记录，建议定期备份本目录")
        warn("DeepSeek Harness 默认以 .git 识别项目根目录；没有 git 时，会话开头请说「先阅读根目录的 AGENTS.md」")
        return
    ok(run(["git", "--version"]).stdout.strip())
    top = run(["git", "rev-parse", "--show-toplevel"])
    if top.returncode == 0:
        root = Path(top.stdout.strip()).resolve()
        if root == ROOT:
            ok("已是独立的 git 仓库")
        else:
            ok(f"位于 git 仓库 {root} 中，随该仓库一起提交（不再单独初始化）")
        return
    if not do_init:
        warn("尚未初始化 git 仓库（使用了 --no-git，跳过）")
        return
    run(["git", "init"])
    run(["git", "add", "."])
    r = run(["git", "commit", "-m", "init ztb_autotest"])
    if r.returncode == 0:
        ok("已初始化 git 仓库并完成首次提交")
    else:
        warn("已初始化 git 仓库，但首次提交失败（可能未配置用户名邮箱），请执行：")
        warn('  git config --global user.name "你的名字"  和  git config --global user.email "你的邮箱"，然后 git commit -m init')


def check_packages():
    print("3. 依赖包")
    missing = [pip for mod, pip in PACKAGES.items() if importlib.util.find_spec(mod) is None]
    if missing:
        warn("缺少：" + ", ".join(missing))
        warn("安装：pip install -r requirements.txt ；UI 用例还需 playwright install chromium")
    else:
        ok("依赖已齐全")


def check_sources():
    print("4. 被测系统源码（project.yaml 中的 source_repos）")
    try:
        sys.path.insert(0, str(ROOT))
        from common.config import load_project, source_paths
        repos = source_paths(load_project())
    except Exception as e:  # noqa: BLE001
        warn(f"读取 project.yaml 失败：{e}")
        return
    if not repos:
        warn("未配置 source_repos，研发维度问题需研发人工回答")
    for name, p in repos:
        if p.exists():
            ok(f"{name} → {p}")
        else:
            warn(f"{name} 路径不可访问：{p}（推荐与 ztb_autotest 同级放置，或在 project.yaml 中改为绝对路径）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-git", action="store_true", help="不做 git 初始化")
    args = ap.parse_args()
    print(f"ztb_autotest 环境检查：{ROOT}\n")
    check_python()
    check_git(not args.no_git)
    check_packages()
    check_sources()
    print("\n完成。")
