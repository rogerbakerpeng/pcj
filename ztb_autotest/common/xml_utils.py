"""XML / SOAP 工具：拼装 SOAP 包、解析、按路径取值、比较。"""
from lxml import etree

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"


def build_soap(operation, namespace, inner_xml, param_name="xml"):
    """新点等系统常见形式：方法只有一个字符串参数，里面放业务 XML。
    若实际接口是结构化参数，改用 zeep 按 WSDL 调用即可。"""
    escaped = (inner_xml.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return (
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_NS}" xmlns:ns="{namespace}">'
        f"<soapenv:Header/><soapenv:Body>"
        f"<ns:{operation}><{param_name}>{escaped}</{param_name}></ns:{operation}>"
        f"</soapenv:Body></soapenv:Envelope>"
    )


def parse(xml_text):
    if isinstance(xml_text, str):
        xml_text = xml_text.encode("utf-8")
    return etree.fromstring(xml_text)


def extract_inner_xml(soap_response):
    """从 SOAP 响应中取出 return 字段里的业务 XML。"""
    root = parse(soap_response)
    body = root.find(f"{{{SOAP_NS}}}Body")
    for el in body.iter():
        if el.text and el.text.strip().startswith("<"):
            return el.text.strip()
    return etree.tostring(body[0], encoding="unicode")


def get_text(root, xpath, default=None):
    r = root.xpath(xpath)
    if not r:
        return default
    v = r[0]
    return v.text if hasattr(v, "text") else str(v)


def get_list(root, xpath):
    return root.xpath(xpath)
