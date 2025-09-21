from .jm_client_impl import *


class CacheRegistry:
    REGISTRY = {}

    @classmethod
    def level_option(cls, option, _client):
        registry = cls.REGISTRY
        registry.setdefault(option, {})
        return registry[option]

    @classmethod
    def level_client(cls, _option, client):
        registry = cls.REGISTRY
        registry.setdefault(client, {})
        return registry[client]

    @classmethod
    def enable_client_cache_on_condition(cls,
                                         option: 'JmOption',
                                         client: JmcomicClient,
                                         cache: Union[None, bool, str, Callable],
                                         ):
        """
        cache parameter

        if None: no cache

        if bool:
          true: level_option

          false: no cache

        if str:
          (invoke corresponding Cache class method)

        :param option: JmOption
        :param client: JmcomicClient
        :param cache: config dsl
        """
        if cache is None:
            return

        elif isinstance(cache, bool):
            if cache is False:
                return
            else:
                cache = cls.level_option

        elif isinstance(cache, str):
            func = getattr(cls, cache, None)
            ExceptionTool.require_true(func is not None, f'未实现的cache配置名: {cache}')
            cache = func

        cache: Callable
        client.set_cache_dict(cache(option, client))


class DirRule:
    RULE_BASE_DIR = 'Bd'

    def __init__(self, rule: str, base_dir=None):
        base_dir = JmcomicText.parse_to_abspath(base_dir)
        self.base_dir = base_dir
        self.rule_dsl = rule
        self.parser_list: List[Tuple[str, Callable]] = self.get_rule_parser_list(rule)

    def decide_image_save_dir(self,
                              album: JmAlbumDetail,
                              photo: JmPhotoDetail,
                              ) -> str:
        return self.apply_rule_to_path(album, photo)

    def decide_album_root_dir(self, album: JmAlbumDetail) -> str:
        return self.apply_rule_to_path(album, None, True)

    def apply_rule_to_path(self, album, photo, only_album_rules=False) -> str:
        path_ls = []
        for rule, parser in self.parser_list:
            if only_album_rules and not (rule == self.RULE_BASE_DIR or rule.startswith('A')):
                continue

            try:
                path = parser(album, photo, rule)
            except BaseException as e:
                # noinspection PyUnboundLocalVariable
                jm_log('dir_rule', f'路径规则"{rule}"的解析出错: {e}, album={album}, photo={photo}')
                raise e
            if parser != self.parse_bd_rule:
                path = fix_windir_name(str(path)).strip()

            path_ls.append(path)

        return fix_filepath('/'.join(path_ls))

    def get_rule_parser_list(self, rule_dsl: str):
        """
        解析下载路径dsl，得到一个路径规则解析列表
        """

        rule_list = self.split_rule_dsl(rule_dsl)
        parser_list: list = []

        for rule in rule_list:
            if rule == self.RULE_BASE_DIR:
                parser_list.append((rule, self.parse_bd_rule))
                continue

            parser = self.get_rule_parser(rule)
            if parser is None:
                ExceptionTool.raises(f'不支持的dsl: "{rule}" in "{rule_dsl}"')

            parser_list.append((rule, parser))

        return parser_list

    # noinspection PyUnusedLocal
    def parse_bd_rule(self, album, photo, rule):
        return self.base_dir

    @classmethod
    def parse_f_string_rule(cls, album, photo, rule: str):
        properties = {}
        if album:
            properties.update(album.get_properties_dict())
        if photo:
            properties.update(photo.get_properties_dict())
        return rule.format(**properties)

    @classmethod
    def parse_detail_rule(cls, album, photo, rule: str):
        detail = album if rule.startswith('A') else photo
        return str(DetailEntity.get_dirname(detail, rule[1:]))

    # noinspection PyMethodMayBeStatic
    def split_rule_dsl(self, rule_dsl: str) -> List[str]:
        if '/' in rule_dsl:
            rule_list = rule_dsl.split('/')
        elif '_' in rule_dsl:
            rule_list = rule_dsl.split('_')
        else:
            rule_list = [rule_dsl]

        for i, e in enumerate(rule_list):
            rule_list[i] = e.strip()

        if rule_list[0] != self.RULE_BASE_DIR:
            rule_list.insert(0, self.RULE_BASE_DIR)

        return rule_list

    @classmethod
    def get_rule_parser(cls, rule: str):
        if '{' in rule:
            return cls.parse_f_string_rule

        if rule.startswith(('A', 'P')):
            return cls.parse_detail_rule

        return cls.parse_f_string_rule
        # ExceptionTool.raises(f'不支持的rule配置: "{rule}"')

    @classmethod
    def apply_rule_to_filename(cls, album, photo, rule: str) -> str:
        if album is None:
            album = photo.from_album
        # noinspection PyArgumentList
        return fix_windir_name(cls.get_rule_parser(rule)(album, photo, rule)).strip()


class JmOption:

    def __init__(self,
                 dir_rule: Dict,
                 download: Dict,
                 client: Dict,
                 plugins: Dict,
                 filepath=None,
                 call_after_init_plugin=True,
                 ):
        # 路径规则配置
        self.dir_rule = DirRule(**dir_rule)
        # 客户端配置
        self.client = AdvancedDict(client)
        # 下载配置
        self.download = AdvancedDict(download)
        # 插件配置
        self.plugins = AdvancedDict(plugins)
        # 其他配置
        self.filepath = filepath

        # 需要主线程等待完成的插件
        self.need_wait_plugins = []

        if call_after_init_plugin:
            self.call_all_plugin('after_init', safe=True)

    def copy_option(self):
        return self.__class__(
            dir_rule={
                'rule': self.dir_rule.rule_dsl,
                'base_dir': self.dir_rule.base_dir,
            },
            download=self.download.src_dict,
            client=self.client.src_dict,
            plugins=self.plugins.src_dict,
            filepath=self.filepath,
            call_after_init_plugin=False
        )

    """
    下面是decide系列方法，为了支持重写和增加程序动态性。
    """

    # noinspection PyUnusedLocal
    def decide_image_batch_count(self, photo: JmPhotoDetail):
        return self.download.threading.image

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def decide_photo_batch_count(self, album: JmAlbumDetail):
        return self.download.threading.photo

    # noinspection PyMethodMayBeStatic
    def decide_image_filename(self, image: JmImageDetail) -> str:
        """
        返回图片的文件名，不包含后缀
        默认返回禁漫的图片文件名，例如：00001 (.jpg)
        """
        return image.filename_without_suffix

    def decide_image_suffix(self, image: JmImageDetail) -> str:
        """
        返回图片的后缀，如果返回的后缀和原后缀不一致，则会进行图片格式转换
        """
        # 动图则使用原后缀
        if image.is_gif:
            return image.img_file_suffix

        # 非动图，以配置为先
        return self.download.image.suffix or image.img_file_suffix

    def decide_image_save_dir(self, photo, ensure_exists=True) -> str:
        # 使用 self.dir_rule 决定 save_dir
        save_dir = self.dir_rule.decide_image_save_dir(
            photo.from_album,
            photo
        )

        if ensure_exists:
            save_dir = JmcomicText.try_mkdir(save_dir)

        return save_dir

    def decide_image_filepath(self, image: JmImageDetail, consider_custom_suffix=True) -> str:
        # 以此决定保存文件夹、后缀、不包含后缀的文件名
        save_dir = self.decide_image_save_dir(image.from_photo)
        suffix = self.decide_image_suffix(image) if consider_custom_suffix else image.img_file_suffix
        return os.path.join(save_dir, fix_windir_name(self.decide_image_filename(image)) + suffix)

    def decide_download_cache(self, _image: JmImageDetail) -> bool:
        return self.download.cache

    def decide_download_image_decode(self, image: JmImageDetail) -> bool:
        # .gif file needn't be decoded
        if image.is_gif:
            return False

        return self.download.image.decode

    """
    下面是创建对象相关方法
    """

    @classmethod
    def default_dict(cls) -> Dict:
        return JmModuleConfig.option_default_dict()

    @classmethod
    def default(cls) -> 'JmOption':
        """
        使用默认的 JmOption
        """
        return cls.construct({})

    @classmethod
    def construct(cls, origdic: Dict, cover_default=True) -> 'JmOption':
        dic = cls.merge_default_dict(origdic) if cover_default else origdic

        # log
        log = dic.pop('log', True)
        if log is False:
            disable_jm_log()

        # version
        version = dic.pop('version', None)
        # noinspection PyTypeChecker
        if version is not None and float(version) >= float(JmModuleConfig.JM_OPTION_VER):
            # 版本号更高，跳过兼容代码
            return cls(**dic)

        # 旧版本option，做兼容
        cls.compatible_with_old_versions(dic)

        return cls(**dic)

    @classmethod
    def compatible_with_old_versions(cls, dic):
        """
        兼容旧的option版本
        """
        # 1: 并发配置项
        dt: dict = dic['download']['threading']
        if 'batch_count' in dt:
            batch_count = dt.pop('batch_count')
            dt['image'] = batch_count

        # 2: 插件配置项 plugin -> plugins
        if 'plugin' in dic:
            dic['plugins'] = dic.pop('plugin')

    def deconstruct(self) -> Dict:
        return {
            'version': JmModuleConfig.JM_OPTION_VER,
            'log': JmModuleConfig.FLAG_ENABLE_JM_LOG,
            'dir_rule': {
                'rule': self.dir_rule.rule_dsl,
                'base_dir': self.dir_rule.base_dir,
            },
            'download': self.download.src_dict,
            'client': self.client.src_dict,
            'plugins': self.plugins.src_dict
        }

    """
    下面是文件IO方法
    """

    @classmethod
    def from_file(cls, filepath: str) -> 'JmOption':
        dic: dict = PackerUtil.unpack(filepath)[0]
        dic.setdefault('filepath', filepath)
        return cls.construct(dic)

    def to_file(self, filepath=None):
        if filepath is None:
            filepath = self.filepath

        ExceptionTool.require_true(filepath is not None, "未指定JmOption的保存路径")

        PackerUtil.pack(self.deconstruct(), filepath)

    """
    下面是创建客户端的相关方法
    """

    @field_cache()
    def build_jm_client(self, **kwargs):
        """
        该方法会首次调用会创建JmcomicClient对象，
        然后保存在self中，
        多次调用`不会`创建新的JmcomicClient对象
        """
        return self.new_jm_client(**kwargs)

    def new_jm_client(self,
                      domain_list=None,
                      impl=None,
                      cache=None,
                      domain_retry_strategy=None,
                      **kwargs
                      ) -> Union[JmHtmlClient, JmApiClient]:
        """
        创建新的Client（客户端），不同Client之间的元数据不共享
        """
        from copy import deepcopy

        # 所有需要用到的 self.client 配置项如下
        postman_conf: dict = deepcopy(self.client.postman.src_dict)  # postman dsl 配置

        meta_data: dict = postman_conf['meta_data']  # 元数据

        retry_times: int = self.client.retry_times  # 重试次数

        cache: str = cache if cache is not None else self.client.cache  # 启用缓存

        impl: str = impl or self.client.impl  # client_key

        if isinstance(impl, type):
            # eg: impl = JmHtmlClient
            # noinspection PyUnresolvedReferences
            impl = impl.client_key

        # start construct client

        # domain
        def decide_domain_list():
            nonlocal domain_list

            if domain_list is None:
                domain_list = self.client.domain

            if not isinstance(domain_list, (list, str)):
                # dict
                domain_list = domain_list.get(impl, [])

            if isinstance(domain_list, str):
                # multi-lines text
                domain_list = str_to_list(domain_list)

            # list or str
            if len(domain_list) == 0:
                domain_list = self.decide_client_domain(impl)

            return domain_list

        # support kwargs overwrite meta_data
        if len(kwargs) != 0:
            meta_data.update(kwargs)

        # postman
        postman = Postmans.create(data=postman_conf)

        # client
        clazz = JmModuleConfig.client_impl_class(impl)
        if clazz == AbstractJmClient or not issubclass(clazz, AbstractJmClient):
            raise NotImplementedError(clazz)

        client: JmcomicClient = clazz(
            postman=postman,
            domain_list=decide_domain_list(),
            retry_times=retry_times,
            domain_retry_strategy=domain_retry_strategy,
        )

        # enable cache
        CacheRegistry.enable_client_cache_on_condition(self, client, cache)

        # noinspection PyTypeChecker
        return client

    def update_cookies(self, cookies: dict):
        metadata: dict = self.client.postman.meta_data.src_dict
        orig_cookies: Optional[Dict] = metadata.get('cookies', None)
        if orig_cookies is None:
            metadata['cookies'] = cookies
        else:
            orig_cookies.update(cookies)
            metadata['cookies'] = orig_cookies

    # noinspection PyMethodMayBeStatic,PyTypeChecker
    def decide_client_domain(self, client_key: str) -> List[str]:
        def is_client_type(ctype) -> bool:
            return self.client_key_is_given_type(client_key, ctype)

        if is_client_type(JmApiClient):
            # 移动端
            return JmModuleConfig.DOMAIN_API_LIST

        if is_client_type(JmHtmlClient):
            # 网页端
            domain_list = JmModuleConfig.DOMAIN_HTML_LIST
            if domain_list is not None:
                return domain_list
            return [JmModuleConfig.get_html_domain()]

        ExceptionTool.raises(f'没有配置域名，且是无法识别的client类型: {client_key}')

    @classmethod
    def client_key_is_given_type(cls, client_key, ctype: Type[JmcomicClient]):
        if client_key == ctype.client_key:
            return True

        clazz = JmModuleConfig.client_impl_class(client_key)
        if issubclass(clazz, ctype):
            return True

        return False

    @classmethod
    def merge_default_dict(cls, user_dict, default_dict=None):
        """
        深度合并两个字典
        """
        if default_dict is None:
            default_dict = cls.default_dict()

        for key, value in user_dict.items():
            if isinstance(value, dict) and isinstance(default_dict.get(key), dict):
                default_dict[key] = cls.merge_default_dict(value, default_dict[key])
            else:
                default_dict[key] = value
        return default_dict

    # 下面的方法提供面向对象的调用风格

    def download_album(self,
                       album_id,
                       downloader=None,
                       callback=None,
                       ):
        from .api import download_album
        download_album(album_id, self, downloader, callback)

    def download_photo(self,
                       photo_id,
                       downloader=None,
                       callback=None
                       ):
        from .api import download_photo
        download_photo(photo_id, self, downloader, callback)

    # 下面的方法为调用插件提供支持

    def call_all_plugin(self, group: str, safe=True, **extra):
        plugin_list: List[dict] = self.plugins.get(group, [])
        if plugin_list is None or len(plugin_list) == 0:
            return

        # 保证 jm_plugin.py 被加载
        from .jm_plugin import JmOptionPlugin

        plugin_registry = JmModuleConfig.REGISTRY_PLUGIN
        for pinfo in plugin_list:
            key, kwargs = pinfo['plugin'], pinfo.get('kwargs', None)  # kwargs为None
            pclass: Optional[Type[JmOptionPlugin]] = plugin_registry.get(key, None)

            ExceptionTool.require_true(pclass is not None, f'[{group}] 未注册的plugin: {key}')

            try:
                self.invoke_plugin(pclass, kwargs, extra, pinfo)
            except BaseException as e:
                if safe is True:
                    traceback_print_exec()
                else:
                    raise e

    def invoke_plugin(self, pclass, kwargs: Optional[Dict], extra: dict, pinfo: dict):
        # 检查插件的参数类型
        kwargs = self.fix_kwargs(kwargs)
        # 把插件的配置数据kwargs和附加数据extra合并，extra会覆盖kwargs
        if len(extra) != 0:
            kwargs.update(extra)

        # 保证 jm_plugin.py 被加载
        from .jm_plugin import JmOptionPlugin, PluginValidationException

        pclass: Type[JmOptionPlugin]
        plugin: Optional[JmOptionPlugin] = None

        try:
            # 构建插件对象
            plugin: JmOptionPlugin = pclass.build(self)

            # 设置日志开关
            if pinfo.get('log', True) is not True:
                plugin.log_enable = False

            jm_log('plugin.invoke', f'调用插件: [{pclass.plugin_key}]')

            # 调用插件功能
            plugin.invoke(**kwargs)

        except PluginValidationException as e:
            # 插件抛出的参数校验异常
            self.handle_plugin_valid_exception(e, pinfo, kwargs, plugin, pclass)

        except JmcomicException as e:
            # 模块内部异常，通过不是插件抛出的，而是插件调用了例如Client，Client请求失败抛出的
            self.handle_plugin_jmcomic_exception(e, pinfo, kwargs, plugin, pclass)

        except BaseException as e:
            # 为插件兜底，捕获其他所有异常
            self.handle_plugin_unexpected_error(e, pinfo, kwargs, plugin, pclass)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def handle_plugin_valid_exception(self, e, pinfo: dict, kwargs: dict, _plugin, _pclass):
        from .jm_plugin import PluginValidationException
        e: PluginValidationException

        mode = pinfo.get('valid', self.plugins.valid)

        if mode == 'ignore':
            # ignore
            return

        if mode == 'log':
            # log
            jm_log('plugin.validation',
                   f'插件 [{e.plugin.plugin_key}] 参数校验异常：{e.msg}'
                   )
            return

        if mode == 'raise':
            # raise
            raise e

        # 其他的mode可以通过继承+方法重写来扩展

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def handle_plugin_unexpected_error(self, e, pinfo: dict, kwargs: dict, _plugin, pclass):
        msg = str(e)
        jm_log('plugin.error', f'插件 [{pclass.plugin_key}]，运行遇到未捕获异常，异常信息: [{msg}]')
        raise e

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def handle_plugin_jmcomic_exception(self, e, pinfo: dict, kwargs: dict, _plugin, pclass):
        msg = str(e)
        jm_log('plugin.exception', f'插件 [{pclass.plugin_key}] 调用失败，异常信息: [{msg}]')
        raise e

    # noinspection PyMethodMayBeStatic
    def fix_kwargs(self, kwargs: Optional[Dict]) -> Dict[str, Any]:
        """
        kwargs将来要传给方法参数，这要求kwargs的key是str类型，
        该方法检查kwargs的key的类型，如果不是str，尝试转为str，不行则抛异常。
        """
        if kwargs is None:
            kwargs = {}
        else:
            ExceptionTool.require_true(
                isinstance(kwargs, dict),
                f'插件的kwargs参数必须为dict类型，而不能是类型: {type(kwargs)}'
            )

        kwargs: dict
        new_kwargs: Dict[str, Any] = {}

        for k, v in kwargs.items():
            if isinstance(v, str):
                newv = JmcomicText.parse_dsl_text(v)
                v = newv

            if isinstance(k, str):
                new_kwargs[k] = v
                continue

            if isinstance(k, (int, float)):
                newk = str(k)
                jm_log('plugin.kwargs', f'插件参数类型转换: {k} ({type(k)}) -> {newk} ({type(newk)})')
                new_kwargs[newk] = v
                continue

            ExceptionTool.raises(
                f'插件kwargs参数类型有误，'
                f'字段: {k}，预期类型为str，实际类型为{type(k)}'
            )

        return new_kwargs

    def wait_all_plugins_finish(self):
        from .jm_plugin import JmOptionPlugin
        for plugin in self.need_wait_plugins:
            plugin: JmOptionPlugin
            plugin.wait_until_finish()
