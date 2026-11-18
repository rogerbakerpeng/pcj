"""交易系统 vs 评标系统 对账：
- ① 侧：交易系统库中的投标人/报价 与 ① 接口返回给评标的数据是否一致
- ② 侧：评标系统结果 与 交易系统落库结果是否一致
可定期运行（如每晚），不一致输出明细。
"""
from common.xml_utils import parse, get_list


def compare(trade_rows, eval_rows, key, fields):
    issues = []
    t = {r[key]: r for r in trade_rows}
    e = {r[key]: r for r in eval_rows}
    for k in t.keys() - e.keys():
        issues.append(f"[仅交易系统有] {key}={k}")
    for k in e.keys() - t.keys():
        issues.append(f"[仅评标系统有] {key}={k}")
    for k in t.keys() & e.keys():
        for f in fields:
            if str(t[k].get(f)) != str(e[k].get(f)):
                issues.append(f"[{key}={k}] {f}: 交易={t[k].get(f)} 评标={e[k].get(f)}")
    return issues


def candidates_from_xml(xml_text):
    root = parse(xml_text)
    return [
        {"name": c.findtext("BidderName"), "rank": c.findtext("Rank"),
         "score": c.findtext("Score"), "price": c.findtext("Price")}
        for c in get_list(root, "//Candidate")
    ]


def reconcile_section(db, section_id, eval_result_xml):
    # TODO 表名字段名
    trade = db.query(
        "SELECT bidder_name AS name, ranking AS `rank`, score, price FROM TODO_eval_result WHERE section_id=:sid",
        sid=section_id,
    )
    return compare(trade, candidates_from_xml(eval_result_xml), "name", ["rank", "score", "price"])


if __name__ == "__main__":
    # TODO: 遍历近 N 天已评标的标段，逐个对账并输出报告
    pass
