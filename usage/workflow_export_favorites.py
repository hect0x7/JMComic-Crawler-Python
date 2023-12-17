from jmcomic import *


def prepare_actions_input_and_secrets():
    # JmcomicText.match_os_env
    pass


def main():
    JmcomicText.dsl_replacer.add_dsl_and_replacer(r'\$\{(.*?)\}', prepare_actions_input_and_secrets)
    option = create_option('../assets/option/option_workflow_export_favorites.yml')
    option.call_all_plugin('main')


if __name__ == '__main__':
    main()
