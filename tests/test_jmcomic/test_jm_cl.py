from test_jmcomic import *


class Test_MobileClient(JmTestConfigurable):

    def test_cl(self):
        for cmd in str_to_list('''
        jmcomic 438516        
        jmcomic 438516 p438516
        '''):
            self.assertEqual(os.system(cmd), 0)
