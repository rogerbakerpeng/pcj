"""配置加载（单项目结构）：一份 ztb_autotest 对应一个项目，配置在根目录 project.yaml。

project.yaml
    name          项目名称
    systems       本项目包含的系统（trade / ywtb ...），决定运行哪几组产品基线用例
    features      可选功能开关（对应 @pytest.mark.feature）
    source_repos  被测系统源码路径（只读），相对路径相对 ztb_autotest 根目录
    envs          各环境配置（local / test / uat ...），其中：
        deps      本环境对外部系统的提供方式：mock / real / manual / none（对应 @pytest.mark.needs）
        readonly  true 时数据库只读、不清理（共用的测试环境、联调环境建议开启）

环境变量：envs 下任何字符串都可以写 ${变量名}，运行时从环境变量取值，口令不要写进 project.yaml。
口令也可以放在根目录的 .env 文件（每行 变量名=值，已在 .gitignore 中，不提交、不外传）；系统环境变量优先于 .env。
"""
import os
import re
from pathlib import Path
from urllib.parse import quote, unquote

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_FILE = BASE_DIR / "project.yaml"

DEP_MODES = ("mock", "real", "manual", "none")
_VAR = re.compile(r"\$\{(\w+)\}")


def load_dotenv(path=None):
    """读取根目录 .env 到环境变量（已存在的环境变量不覆盖）。只由人维护，AI 不读取、不输出其内容。"""
    f = Path(path) if path else BASE_DIR / ".env"
    if not f.exists():
        return 0
    n = 0
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            n += 1
    return n


load_dotenv()


class EnvNotConfigured(Exception):
    """环境配置缺失。属于环境问题：停下来补配置，不要改用例、不要重跑。"""


def load_project():
    if not PROJECT_FILE.exists():
        raise FileNotFoundError(f"缺少项目配置：{PROJECT_FILE}")
    with open(PROJECT_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _expand(value, url_encode=False):
    """把 ${变量名} 换成环境变量的值；变量未设置时原样保留，由预检报出。
    url_encode=True 用于连接串：自动做 URL 编码，原始密码和已编码的密码（如 %40）都可以直接用。"""
    def repl(m):
        v = os.getenv(m.group(1))
        if v is None:
            return m.group(0)
        return quote(unquote(v), safe="") if url_encode else v
    return _VAR.sub(repl, value)


def _expand_tree(node):
    if isinstance(node, dict):
        return {k: _expand_tree(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_tree(v) for v in node]
    if isinstance(node, str):
        return _expand(node)
    return node


def get_env(project, env_name):
    envs = project.get("envs") or {}
    if env_name not in envs:
        raise KeyError(f"project.yaml 中没有环境：{env_name}，已有：{list(envs)}")
    env = envs[env_name] or {}
    db_url = (env.get("db") or {}).get("url") if isinstance(env.get("db"), dict) else None
    env = _expand_tree(env)
    # 数据库连接串中的 ${变量} 自动做 URL 编码，密码里有 @ : / 等字符也不用手工转义
    if db_url:
        env["db"]["url"] = _expand(str(db_url), url_encode=True)
    # 账号密码用环境变量覆盖，例如 ZTB_PWD_AGENT，避免把真实密码提交到仓库
    for role, acc in (env.get("accounts") or {}).items():
        if isinstance(acc, dict):
            acc["password"] = os.getenv(f"ZTB_PWD_{role.upper()}", acc.get("password"))
    return env


def is_missing(value):
    """仍是 TODO、为空，或含未解析的 ${变量}。"""
    return value is None or (isinstance(value, str) and ("TODO" in value or "${" in value or not value.strip()))


def find_missing(node, path=""):
    """返回配置中未填写的项的路径列表，如 ['trade.base_url']。只返回路径，不返回值，避免口令进日志。"""
    bad = []
    if isinstance(node, dict):
        for k, v in node.items():
            bad += find_missing(v, f"{path}.{k}" if path else str(k))
    elif is_missing(node):
        bad.append(path)
    return bad


def lookup(env, dotted):
    node = env
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def require(env, dotted):
    """取一个必需的配置项；缺失时抛 EnvNotConfigured（conftest 会立即停止本次运行并说明缺什么）。"""
    value = lookup(env, dotted)
    if isinstance(value, dict):
        bad = find_missing(value, dotted)
        if bad:
            raise EnvNotConfigured("、".join(bad))
        return value
    if is_missing(value):
        raise EnvNotConfigured(dotted)
    return value


def dep_mode(env, dep):
    """本环境对外部依赖的提供方式；未声明返回 None。"""
    mode = (env.get("deps") or {}).get(dep)
    if mode is None:
        return None
    mode = str(mode).strip().lower()
    if mode not in DEP_MODES:
        raise EnvNotConfigured(f"deps.{dep} 的值应为 {' / '.join(DEP_MODES)}，现在是 {mode!r}")
    return mode


def source_paths(project):
    """返回 [(名称, 绝对路径)]，相对路径按 ztb_autotest 根目录解析。"""
    result = []
    for r in project.get("source_repos") or []:
        p = Path(str(r.get("path", "")))
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        result.append((r.get("name"), p))
    return result
