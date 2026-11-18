"""① 模拟评标系统：调用交易系统的取数接口。
交易系统是服务端，脚本扮演评标系统，不需要评标系统在线。
请求报文取自样本库 samples/messages/eval/<接口>/normal.req.xml，其中 {app_id}、{section_code} 是占位符。
TODO：按交易系统提供的 WSDL 和真实报文，补全方法名；报文用测试环境接口日志中的真实请求替换（保留占位符）。"""
from common import samples
from common.config import require
from ws.soap_client import SoapClient


class EvalFetchClient:
    def __init__(self, env):
        self.client = SoapClient(require(env, "trade.fetch_ws_url"))
        self.auth = env.get("ws_auth", {})

    def _render(self, interface, scenario="normal", **kw):
        tpl = samples.message("eval", interface, scenario, "req", required=True)
        return tpl.format(app_id=self.auth.get("app_id", ""), **kw)

    def get_project_info(self, section_code):
        return self.client.call_raw("getProjectInfo", self._render("评标取数_项目信息", section_code=section_code))

    def get_bidders(self, section_code):
        return self.client.call_raw("getBidderList", self._render("评标取数_投标人", section_code=section_code))

    def get_open_record(self, section_code):
        return self.client.call_raw("getOpenRecord", self._render("评标取数_开标记录", section_code=section_code))
