"""③【个性化】模拟评标系统：评标结束后主动推送结果到交易系统。
仅在项目需求文档要求时使用。TODO：按项目推送接口 WSDL 补全。"""
from common import samples
from common.config import require
from ws.soap_client import SoapClient


class EvalPushClient:
    def __init__(self, env):
        self.client = SoapClient(require(env, "trade.push_ws_url"))
        self.auth = env.get("ws_auth", {})

    def push_result(self, section_code, candidates):
        rows = "".join(
            f"<Candidate><Rank>{c['rank']}</Rank><BidderName>{c['name']}</BidderName>"
            f"<Score>{c['score']}</Score><Price>{c['price']}</Price></Candidate>"
            for c in candidates
        )
        tpl = samples.message("eval", "评标主动推送", "normal", "req", required=True)
        xml = tpl.format(app_id=self.auth.get("app_id", ""), section_code=section_code, candidates=rows)
        return self.client.call_raw("receiveEvalResult", xml)
