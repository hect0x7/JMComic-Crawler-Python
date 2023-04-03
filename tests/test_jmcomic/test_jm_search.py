from test_jmcomic import *


class Test_Search(JmTestConfigurable):

    def test_analyse_search_html(self):
        search_album: JmSearchPage = self.client.search_album('MANA')
        for i, info in enumerate(search_album):
            # info: (album_id, title, category_none, label_sub_none, tag_list)
            print(f'index: {i}--------------------------------------------------------\n'
                  f'id: {info[0]}\n'
                  f'title: {info[1]}\n'
                  f'category_none: {info[2]}\n'
                  f'label_sub_none: {info[3]}\n'
                  f'tag_list: {info[4]}\n\n'
                  )
