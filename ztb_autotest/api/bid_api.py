"""投标：报名、下载招标文件、上传投标文件（工具生成的加密文件）。"""
from pathlib import Path


class BidApi:
    def __init__(self, session):
        self.s = session

    def upload_bid_file(self, section_id, file_path):
        p = Path(file_path)
        with open(p, "rb") as f:
            r = self.s.http.post(
                f"{self.s.base_url}/TODO/bid/upload",
                data={"sectionId": section_id},
                files={"file": (p.name, f)},
            )
        return r.json()
