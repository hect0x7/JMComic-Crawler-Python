from test_jmcomic import *

# 移动端专用的禁漫域名
domain_list = [
    "https://www.jmapinode1.cc",
    "https://www.jmapinode2.cc",
    "https://www.jmapinode3.cc",
    "https://www.jmapibranch2.cc"
]


class Test_MobileClient(JmTestConfigurable):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.option.new_jm_client(domain_list, impl='api')

    def test_search(self):
        page = self.client.search_site('MANA')

        if len(page) >= 1:
            for aid, ainfo in page[0:1:1]:
                print(aid, ainfo['description'], ainfo['category'])

        for aid, atitle, tag_list in page.iter_id_title_tag():
            print(aid, atitle, tag_list)
