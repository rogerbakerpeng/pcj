"""契约校验：XSD 结构 + rules.yaml 字段规则。"""
import re
from pathlib import Path

import yaml

from common.xml_utils import parse

DIR = Path(__file__).parent


def check_xsd(xml_text, xsd_name):
    import xmlschema  # 延迟导入：只有真正做契约校验时才需要该依赖
    schema = xmlschema.XMLSchema(str(DIR / "xsd" / xsd_name))
    errors = [str(e.reason) for e in schema.iter_errors(xml_text)]
    return errors


def check_rules(xml_text, rule_set):
    rules = yaml.safe_load((DIR / "rules.yaml").read_text(encoding="utf-8"))[rule_set]
    root = parse(xml_text)
    errors = []
    for xpath, rule in rules.items():
        nodes = root.getroottree().xpath(xpath)
        if rule.get("required") and not nodes:
            errors.append(f"{xpath} 缺失")
        for n in nodes:
            v = (n.text or "").strip()
            if "enum" in rule and v not in rule["enum"]:
                errors.append(f"{xpath} 值 {v} 不在枚举 {rule['enum']}")
            if "max_len" in rule and len(v) > rule["max_len"]:
                errors.append(f"{xpath} 超长 {len(v)}>{rule['max_len']}")
            if "pattern" in rule and v and not re.match(rule["pattern"], v):
                errors.append(f"{xpath} 格式不符：{v}")
    return errors


def assert_contract(xml_text, xsd_name, rule_set):
    errors = check_xsd(xml_text, xsd_name) + check_rules(xml_text, rule_set)
    assert not errors, "契约校验失败：\n" + "\n".join(errors)
