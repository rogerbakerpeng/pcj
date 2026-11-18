"""通用 SOAP 客户端。两种方式：
1. 有 WSDL 且参数结构化：用 zeep（call_by_wsdl）
2. 单字符串参数传业务 XML（新点常见）：用 requests 直接发（call_raw）
"""
import requests

from common.logger import get_logger
from common.xml_utils import build_soap, extract_inner_xml

log = get_logger("soap")


class SoapClient:
    def __init__(self, url, namespace="http://TODO.namespace/", timeout=30):
        self.url = url
        self.namespace = namespace
        self.timeout = timeout

    def call_raw(self, operation, inner_xml, param_name="xml"):
        envelope = build_soap(operation, self.namespace, inner_xml, param_name)
        endpoint = self.url.split("?")[0]
        log.info("调用 %s.%s", endpoint, operation)
        r = requests.post(endpoint, data=envelope.encode("utf-8"),
                          headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": operation},
                          timeout=self.timeout)
        log.info("返回 %s", r.status_code)
        return r.status_code, extract_inner_xml(r.text) if r.ok else r.text

    def call_by_wsdl(self, operation, **params):
        from zeep import Client
        return getattr(Client(self.url).service, operation)(**params)
