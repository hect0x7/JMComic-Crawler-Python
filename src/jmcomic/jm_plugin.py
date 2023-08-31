"""
该文件存放的是option扩展功能类
"""

from .jm_option import JmOption, JmModuleConfig, jm_debug


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
扩展功能：登录禁漫，并保存登录后的cookies，让所有client都带上此cookies
"""


class JmLoginPlugin(JmOptionPlugin):
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


class UsageLogPlugin(JmOptionPlugin):
    plugin_key = 'usage-log'

    def invoke(self, **kwargs) -> None:
        import threading
        threading.Thread(
            target=self.monitor_resource_usage,
            kwargs=kwargs,
            daemon=True,
        ).start()

    def monitor_resource_usage(
            self,
            interval=1,
            enable_warning=True,
            warning_cpu_percent=70,
            warning_mem_percent=50,
            warning_thread_count=100,
    ):
        try:
            import psutil
        except ImportError:
            msg = (f'插件`{self.plugin_key}`依赖psutil库，请先安装psutil再使用。'
                   f'安装命令: [pip install psutil]')
            import warnings
            warnings.warn(msg)
            # import sys
            # print(msg, file=sys.stderr)
            return

        import os
        from time import sleep
        from threading import active_count
        # 获取当前进程
        process = psutil.Process(os.getpid())

        cpu_percent = None
        # noinspection PyUnusedLocal
        thread_count = None
        # noinspection PyUnusedLocal
        mem_usage = None

        def warning():
            warning_msg_list = []
            if cpu_percent >= warning_cpu_percent:
                warning_msg_list.append(f'进程占用cpu过高 ({cpu_percent}% >= {warning_cpu_percent}%)')

            mem_percent = psutil.virtual_memory().percent
            if mem_percent >= warning_mem_percent:
                warning_msg_list.append(f'系统内存占用过高 ({mem_percent}% >= {warning_mem_percent}%)')

            if thread_count >= warning_thread_count:
                warning_msg_list.append(f'线程数过多 ({thread_count} >= {warning_thread_count})')

            if len(warning_msg_list) != 0:
                warning_msg_list.insert(0, '硬件占用告警，占用过高可能导致系统卡死！')
                warning_msg_list.append('')
                jm_debug('plugin.psutil.warning', '\n'.join(warning_msg_list))

        while True:
            # 获取CPU占用率（0~100）
            cpu_percent = process.cpu_percent()
            # 获取内存占用（MB）
            mem_usage = process.memory_info().rss / (1024 * 1024)
            thread_count = active_count()
            # 获取网络占用情况
            # network_info = psutil.net_io_counters()
            # network_bytes_sent = network_info.bytes_sent
            # network_bytes_received = network_info.bytes_recv

            # 打印信息
            msg = ', '.join([
                f'线程数: {thread_count}',
                f'CPU占用: {cpu_percent}%',
                f'内存占用: {mem_usage}MB',
                # f"发送的字节数: {network_bytes_sent}",
                # f"接收的字节数: {network_bytes_received}",
            ])
            jm_debug('plugin.psutil.log', msg)

            if enable_warning is True:
                # 警告
                warning()

            # 等待一段时间
            sleep(interval)


JmModuleConfig.register_plugin(JmLoginPlugin)
JmModuleConfig.register_plugin(UsageLogPlugin)
