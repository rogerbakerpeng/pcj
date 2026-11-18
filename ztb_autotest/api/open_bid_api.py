"""开标：开标、解密、开标记录。"""


class OpenBidApi:
    def __init__(self, session):
        self.s = session

    def start_open(self, section_id):
        return self.s.post("TODO/open/start", json={"sectionId": section_id})

    def decrypt(self, section_id, bidder_id):
        return self.s.post("TODO/open/decrypt", json={"sectionId": section_id, "bidderId": bidder_id})

    def finish_open(self, section_id):
        return self.s.post("TODO/open/finish", json={"sectionId": section_id})
