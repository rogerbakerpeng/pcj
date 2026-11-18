"""② Mock 评标系统：交易系统（代理点击“获取评标结果”）调用此服务。

使用：
  python -m mocks.eval_mock_server --host 0.0.0.0 --port 18080
  交易系统测试环境把评标接口地址配置为 http://<本机>:18080/eval/ws

场景切换（测试脚本中调用）：
  POST /__mock/scenario  {"scenario": "normal"}
可选场景：normal / not_finished / failed_bid / rejected / error / timeout
查看交易系统发来的请求：GET /__mock/requests
"""
import argparse
import time

from flask import Flask, request, jsonify, Response

from common import samples

# 返回报文统一取自样本库：samples/messages/eval/获取评标结果/<场景>.resp.xml
DEP, INTERFACE = "eval", "获取评标结果"
app = Flask(__name__)
STATE = {"scenario": "normal", "requests": []}

SOAP_WRAP = (
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soapenv:Body><ns:getEvalResultResponse xmlns:ns=\"http://TODO.namespace/\">"
    "<return>{payload}</return></ns:getEvalResultResponse></soapenv:Body></soapenv:Envelope>"
)


def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@app.post("/eval/ws")
def eval_ws():
    body = request.data.decode("utf-8", errors="ignore")
    STATE["requests"].append({"time": time.time(), "body": body})
    scenario = STATE["scenario"]
    if scenario == "timeout":
        time.sleep(120)
    tpl = samples.message(DEP, INTERFACE, scenario)
    if tpl is None:
        known = samples.scenarios(DEP, INTERFACE)
        return Response(f"mock 没有场景「{scenario}」的报文，已有：{known}。"
                        f"请在 samples/messages/{DEP}/{INTERFACE}/ 下放入 {scenario}.resp.xml", status=500)
    return Response(SOAP_WRAP.format(payload=_escape(tpl)), mimetype="text/xml")


@app.get("/eval/ws")
def wsdl():
    # 交易系统若需要先取 WSDL：把评标系统的真实 WSDL（改地址后）放到 samples/third_party/eval/eval.wsdl
    f = samples.SAMPLES_DIR / "third_party" / "eval" / "eval.wsdl"
    return Response(f.read_text(encoding="utf-8") if f.exists() else "", mimetype="text/xml")


@app.post("/__mock/scenario")
def set_scenario():
    STATE["scenario"] = request.json.get("scenario", "normal")
    return jsonify(ok=True, scenario=STATE["scenario"])


@app.get("/__mock/requests")
def get_requests():
    return jsonify(STATE["requests"][-50:])


@app.post("/__mock/reset")
def reset():
    STATE.update(scenario="normal", requests=[])
    return jsonify(ok=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=18080)
    a = p.parse_args()
    app.run(host=a.host, port=a.port, threaded=True)
