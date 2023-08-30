"""
该文件存放的是option插件类
"""

from .jm_option import *


class JmOptionPlugin:
    plugin_key: str

    def __init__(self, option: JmOption):
        self.option = option

    def invoke(self, **kwargs) -> None:
        """
        执行插件的功能
        @param kwargs: 给插件的参数
        """
        raise NotImplementedError

    @classmethod
    def build(cls, option: JmOption) -> 'JmOptionPlugin':
        """
        创建插件实例
        @param option: JmOption对象
        """
        return cls(option)


"""
插件功能：登录禁漫，并保存登录后的cookies，让所有client都带上此cookies
"""


class LoginPlugin(JmOptionPlugin):
    plugin_key = 'login'

    def invoke(self, username, password) -> None:
        assert isinstance(username, str), '用户名必须是str'
        assert isinstance(password, str), '密码必须是str'

        client = self.option.new_jm_client()
        client.login(username, password)
        cookies = client['cookies']

        postman: dict = self.option.client.postman.src_dict
        meta_data = postman.get('meta_data', {})
        meta_data['cookies'] = cookies
        postman['meta_data'] = meta_data
        jm_debug('plugin.login', '登录成功')


JmModuleConfig.register_plugin(LoginPlugin)
