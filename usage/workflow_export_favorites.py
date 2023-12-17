from jmcomic import *


def prepare_actions_input_and_secrets():
    def env(match: Match) -> str:
        name = match[1]
        value = os.getenv(name, None)
        if value is not None:
            return value

        # 未配置secrets，尝试从工作流中取
        value = os.getenv(f'IN_{name}', '')
        # 工作流也没有传值
        ExceptionTool.require_true(value != '', f'未配置secrets或工作流，字段为: {name}')
        return value

    JmcomicText.dsl_replacer.add_dsl_and_replacer(r'\$\{(.*?)\}', env)


def main():
    prepare_actions_input_and_secrets()
    option = create_option('../assets/option/option_workflow_export_favorites.yml')
    option.call_all_plugin('main')


if __name__ == '__main__':
    main()
