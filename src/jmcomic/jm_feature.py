"""
该文件存放的是 Feature 机制

Feature 用于封装复杂、高级的功能特性，例如pdf导出插件，以前用户需要知道插件名称，调用时机，option插件参数等等，使用feature相当于包办了这些。

用法:
    from jmcomic import download_album, Feature

    # 最简单
    download_album(id, option, extra=Feature.export_pdf)

    # 带自定义参数
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

    def should_invoke(self, feature_from: str, when: str) -> bool:
        """
        判断在当前钩子(when)下，根据来源(feature_from)，是否应该执行。
        默认返回 True（任何钩子都执行）。子类可覆写来限制执行时机。

        :param feature_from: Feature 的注册来源，如 'download_album', 'download_photo'
        :param when: 当前触发的钩子名称，如 'after_album', 'after_photo'
        :returns: 是否应该执行
        """
        return True

    def invoke(self, option: JmOption, feature_from: str, when: str, **kwargs):
        """
        执行此 Feature。子类需实现该方法。

        :param option: 当前的 JmOption
        :param feature_from 注册来源，如 'download_album', 'download_photo'
        :param when: 钩子回调时机，如 'after_album', 'after_photo'
        :param kwargs: album, photo, downloader 等回调参数
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

    def should_invoke(self, feature_from: str, when: str) -> bool:
        """
        默认根据注册来源推导执行时机：
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
        return new_instance

    def invoke(self, option: JmOption, feature_from: str, when: str, **extra):
        """
        执行此 Feature 对应的插件。
        根据 feature_from 动态适配 filename_rule 等参数。
        """
        pclass: type = JmModuleConfig.REGISTRY_PLUGIN.get(self.plugin_key)
        ExceptionTool.require_true(pclass is not None, f'PluginFeature 引用了未注册的插件: {self.plugin_key}, from {feature_from}, when {when}')

        # 根据 feature_from 动态适配参数
        plugin_kwargs: dict = self._adapt_plugin_kwargs(feature_from, when)

        option.invoke_plugin(
            pclass=pclass,
            kwargs=plugin_kwargs,
            extra=extra,
            pinfo={'plugin': self.plugin_key, 'kwargs': plugin_kwargs},
        )

    def _adapt_plugin_kwargs(self, feature_from: str, when: str) -> dict:
        """
        根据feature_from和when动态确定以下插件参数:
        filename_rule
        """
        kwargs = self.kwargs.copy()
        kwargs.setdefault('filename_rule', '[JM{Aid}]{Atitle}' if feature_from == 'download_album' else '[JM{Pid}]{Ptitle}')
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
# filename_rule 会根据 feature_from 在 invoke 时动态适配 A/P 前缀
# zip 的打包粒度由插件根据上下文（album/photo）自动推导，无需 level 参数
Feature.export_pdf = PluginFeature(Img2pdfPlugin.plugin_key, pdf_dir='./')
Feature.export_zip = PluginFeature(ZipPlugin.plugin_key, zip_dir='./')
Feature.export_long_img = PluginFeature(LongImgPlugin.plugin_key, img_dir='./')
