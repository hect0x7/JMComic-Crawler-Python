from jmcomic import *


def prepare_actions_input_and_secrets():
    """
    本函数替代对配置文件中的 ${} 的解析函数
    目的是为了支持：当没有配置环境变量时，可以找另一个环境变量来用
    """

    def env(match: Match) -> str:
        name = match[1]
        value = os.getenv(name, '')

        # 配置了有效的值，放行
        if value != '':
            return value

        # 未配置，或者值为空（值为空是GitHub Actions的未配置默认值）
        # 是EMAIL相关，也放行
        if name.startswith('EMAIL'):
            return value

        # 尝试从工作流中取
        value = os.getenv(f'IN_{name}', '')
        # 工作流也没有传值
        ExceptionTool.require_true(value != '', f'未配置secrets或工作流，字段为: {name}')

        return value

    JmcomicText.dsl_replacer.add_dsl_and_replacer(r'\$\{(.*?)\}', env)


def main():
    prepare_actions_input_and_secrets()
    # 关闭logging，保证安全
    disable_jm_log()
    option = create_option('../assets/option/option_workflow_export_favorites.yml')
    option.call_all_plugin('main', safe=False)


if __name__ == '__main__':
    main()
