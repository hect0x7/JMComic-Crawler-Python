"""
该文件存放的是 Feature（下载特性）机制

Feature 用于在下载生命周期中挂载上下文相关的动态附加行为，
例如下载完成后自适应导出为 PDF、ZIP 或长图等。
它不仅是插件的封装，更能根据调用来源（整本/单章）智能调整执行策略。

用法:
    from jmcomic import download_album, Feature

    # 最简单
    download_album(id, option, extra=Feature.export_pdf)

    # 带参数
    download_album(id, option, extra=Feature.export_pdf(pdf_dir='./output'))

    # 多个 Feature（列表 / 运算符均可）
    download_album(id, option, extra=[Feature.export_pdf, Feature.export_zip])
    download_album(id, option, extra=Feature.export_pdf + Feature.export_zip)
"""

from .jm_plugin import *


class Feature:
    """
    下载特性。传入 download_album / download_photo 的 extra 参数，
    下载完成后自动执行。

    Feature 记录在 downloader 上，由 downloader 在 after_album / after_photo
    钩子中根据 feature_from 自动判断是否执行。
    """

    # 类型声明（保证 IDE 自动补全）
    export_pdf: 'PluginFeature'
    export_zip: 'PluginFeature'
    export_long_img: 'PluginFeature'

    def should_invoke(self, when: str, feature_from: str) -> bool:
        """
        判断在当前钩子(when)下，根据来源(feature_from)，是否应该执行。
        默认返回 True（任何钩子都执行）。子类可覆写来限制执行时机。

        :param when: 当前触发的钩子名称，如 'after_album', 'after_photo'
        :param feature_from: Feature 的注册来源，如 'download_album', 'download_photo'
        :returns: 是否应该执行
        """
        return True

    def invoke(self, option, **context):
        """
        执行此 Feature。子类需实现该方法。

        :param option: 当前的 JmOption
        :param context: album, photo, downloader, feature_from 等上下文
        """
        raise NotImplementedError

    # ---- 组合运算符，统一返回 FeatureChain ----

    def __add__(self, other):
        return FeatureChain._combine(self, other)

    def __or__(self, other):
        return FeatureChain._combine(self, other)

    def __and__(self, other):
        return FeatureChain._combine(self, other)

    def _to_list(self):
        return [self]


class PluginFeature(Feature):
    """
    插件特性。封装 jmcomic 的插件，在 invoke 时调用相应的插件类。
    参数根据 feature_from 动态适配，无需写死。
    """

    def __init__(self, plugin_key, **kwargs):
        self.plugin_key = plugin_key
        self.kwargs = kwargs
        # 用户通过 __call__ 显式传入的参数名，这些参数不会被 _adapt_kwargs 动态适配
        self._user_keys: set = set()

    def should_invoke(self, when: str, feature_from: str) -> bool:
        """
        根据注册来源推导执行时机：
        download_album → after_album, download_photo → after_photo
        """
        if feature_from == 'download_album':
            return when == 'after_album'
        elif feature_from == 'download_photo':
            return when == 'after_photo'
        return False

    def __call__(self, **kwargs):
        """带自定义参数，返回新实例（继承默认参数）"""
        new_kwargs = self.kwargs.copy()
        new_kwargs.update(kwargs)
        new_instance = PluginFeature(self.plugin_key, **new_kwargs)
        # 记录用户显式传入的参数名，这些参数不被动态适配
        new_instance._user_keys = set(kwargs.keys())
        return new_instance

    def invoke(self, option, feature_from=None, **context):
        """
        执行此 Feature 对应的插件。
        根据 feature_from 动态适配 filename_rule 和 level 等参数。
        """
        pclass = JmModuleConfig.REGISTRY_PLUGIN.get(self.plugin_key)
        if pclass is None:
            ExceptionTool.raises(f'PluginFeature 引用了未注册的插件: {self.plugin_key}')

        # 根据 feature_from 动态适配参数
        adapted = self._adapt_kwargs(feature_from)
        merged_kwargs = {**adapted, **context}

        option.invoke_plugin(
            pclass=pclass,
            kwargs=merged_kwargs,
            extra={},
            pinfo={'plugin': self.plugin_key, 'kwargs': adapted},
        )

    def _adapt_kwargs(self, feature_from):
        """
        根据 feature_from 动态适配参数：
        - filename_rule 前缀：download_album → A前缀，download_photo → P前缀
        - level：download_album → 'album'，download_photo → 'photo'

        注意：用户通过 __call__ 显式传入的参数（记录在 _user_keys 中）不会被适配。
        """
        kwargs = self.kwargs.copy()

        if feature_from == 'download_album':
            # album 模式：P前缀规则 → A前缀规则, level → album
            if 'filename_rule' not in self._user_keys and 'filename_rule' in kwargs:
                rule = kwargs['filename_rule']
                if rule and rule[0] == 'P':
                    kwargs['filename_rule'] = 'A' + rule[1:]
            if 'level' not in self._user_keys and 'level' in kwargs and kwargs['level'] == 'photo':
                kwargs['level'] = 'album'

        elif feature_from == 'download_photo':
            # photo 模式：A前缀规则 → P前缀规则, level → photo
            if 'filename_rule' not in self._user_keys and 'filename_rule' in kwargs:
                rule = kwargs['filename_rule']
                if rule and rule[0] == 'A':
                    kwargs['filename_rule'] = 'P' + rule[1:]
            if 'level' not in self._user_keys and 'level' in kwargs and kwargs['level'] == 'album':
                kwargs['level'] = 'photo'

        return kwargs

    def __repr__(self):
        if self.kwargs:
            args = ', '.join(f'{k}={v!r}' for k, v in self.kwargs.items())
            return f'PluginFeature({self.plugin_key!r}, {args})'
        return f'PluginFeature({self.plugin_key!r})'


class FeatureChain:
    """多个 Feature 的组合"""

    def __init__(self, features):
        self._features = features

    @classmethod
    def _combine(cls, left, right):
        return cls(left._to_list() + right._to_list())

    def __add__(self, other):
        return FeatureChain._combine(self, other)

    def __or__(self, other):
        return FeatureChain._combine(self, other)

    def __and__(self, other):
        return FeatureChain._combine(self, other)

    def _to_list(self):
        return list(self._features)

    def __repr__(self):
        return f'FeatureChain({self._features})'


# 预定义特性（用插件类的 plugin_key 引用，附带默认参数）
# filename_rule 和 level 会根据 feature_from 在 invoke 时动态适配：
#   download_album → A前缀 + level=album
#   download_photo → P前缀 + level=photo
Feature.export_pdf = PluginFeature(Img2pdfPlugin.plugin_key, pdf_dir='./', filename_rule='Atitle')
Feature.export_zip = PluginFeature(ZipPlugin.plugin_key, level='photo', zip_dir='./', filename_rule='Ptitle')
Feature.export_long_img = PluginFeature(LongImgPlugin.plugin_key, img_dir='./', filename_rule='Pid')
