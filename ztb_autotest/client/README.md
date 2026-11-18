# 招投标工具（桌面客户端）冒烟

- 只覆盖主路径：打开招标文件 → 填写报价 → 签章 → 生成投标文件
- 需 Windows + pywinauto；CA 用厂商提供的测试软证书，否则无法无人值守
- 生成的文件可自动放入 samples/files/bid/normal/（并在 samples/index.yaml 登记），补充样本库
- 投入产出比低，优先级排在接口和样本库之后
