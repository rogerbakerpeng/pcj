# 接口契约

WebService 交互用 XSD 描述报文结构，外加字段规则（必填、长度、枚举、格式）。

| 文件 | 对应交互点 |
|---|---|
| xsd/fetch_project_resp.xsd | ① 交易系统返回给评标的项目信息 |
| xsd/eval_result_resp.xsd | ② 评标系统返回的评标结果（同时约束 Mock 模板） |
| rules.yaml | 字段级业务规则 |

拿到真实报文后：可用 trang 或在线工具从 XML 样例生成 XSD 初稿，再人工收紧必填项和类型。
