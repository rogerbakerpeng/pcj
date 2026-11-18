"""投标文件制作工具冒烟（pywinauto 骨架）。TODO：按工具实际窗口标题、控件补全。
用 Inspect.exe 或 print_control_identifiers() 查看控件。"""
import sys


def run(tool_exe, tender_file, output_dir, price="1000000"):
    if sys.platform != "win32":
        raise RuntimeError("仅支持 Windows")
    from pywinauto.application import Application

    app = Application(backend="uia").start(tool_exe)
    main = app.window(title_re=".*投标文件制作.*")   # TODO
    main.wait("visible", timeout=60)
    # main.print_control_identifiers()
    # TODO: 打开招标文件
    # TODO: 填写报价 price
    # TODO: 签章（测试软证书）
    # TODO: 生成投标文件到 output_dir
    return output_dir


if __name__ == "__main__":
    run(r"C:\TODO\tool.exe", r"C:\TODO\tender.zbj", r".\samples\files\bid\normal")
