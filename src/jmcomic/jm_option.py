from .jm_client_impl import *


class DirRule:
    rule_sample = [
        # 根目录 / Album-id / Photo-序号 /
        'Bd_Aid_Pindex',  # 禁漫网站的默认下载方式
        # 根目录 / Album-作者 / Album-标题 / Photo-序号 /
        'Bd_Aauthor_Atitle_Pindex',
        # 根目录 / Photo-序号&标题 /
        'Bd_Pindextitle',
        # 根目录 / Photo-自定义类属性 /
        'Bd_Aauthor_Atitle_Pcustomfield',
        # 需要替换JmModuleConfig.CLASS_ALBUM / CLASS_PHOTO才能让自定义属性生效
    ]

    Detail = Union[JmAlbumDetail, JmPhotoDetail, None]
    RuleFunc = Callable[[Detail], str]
    RuleSolver = Tuple[int, RuleFunc]
    RuleSolverList = List[RuleSolver]

    rule_solver_cache: Dict[str, RuleSolver] = {}

    def __init__(self, rule: str, base_dir=None):
        base_dir = JmcomicText.parse_to_abspath(base_dir)
        self.base_dir = base_dir
        self.rule_dsl = rule
        self.solver_list = self.get_role_solver_list(rule, base_dir)

    def deside_image_save_dir(self,
                              album: JmAlbumDetail,
                              photo: JmPhotoDetail,
                              ) -> str:
        path_ls = []
        for solver in self.solver_list:
            try:
                ret = self.apply_rule_solver(album, photo, solver)
            except BaseException as e:
                # noinspection PyUnboundLocalVariable
                jm_debug('dir_rule', f'路径规则"{self.rule_dsl}"的解析出错: {e},')
                raise e

            path_ls.append(str(ret))

        return fix_filepath('/'.join(path_ls), is_dir=True)

    def get_role_solver_list(self, rule_dsl: str, base_dir: str) -> RuleSolverList:
        """
        解析下载路径dsl，得到一个路径规则解析列表
        """

        if '_' not in rule_dsl and rule_dsl != 'Bd':
            raise NotImplementedError(f'不支持的dsl: "{rule_dsl}"')

        rule_ls = rule_dsl.split('_')
        solver_ls = []

        for rule in rule_ls:
            if rule == 'Bd':
                solver_ls.append((0, lambda _: base_dir))
                continue

            rule_solver = self.get_rule_solver(rule)
            if rule_solver is None:
                raise NotImplementedError(f'不支持的dsl: "{rule}" in "{rule_dsl}"')

            solver_ls.append(rule_solver)

        return solver_ls

    @classmethod
    def get_rule_solver(cls, rule: str) -> Optional[RuleSolver]:
        # 查找缓存
        if rule in cls.rule_solver_cache:
            return cls.rule_solver_cache[rule]

        # 检查dsl
        if not rule.startswith(('A', 'P')):
            return None

        # Axxx or Pyyy
        key = 1 if rule[0] == 'A' else 2
        solve_func = lambda entity, ref=rule[1:]: fix_windir_name(str(getattr(entity, ref)))

        # 保存缓存
        rule_solver = (key, solve_func)
        cls.rule_solver_cache[rule] = rule_solver
        return rule_solver

    @classmethod
    def apply_rule_solver(cls, album, photo, rule_solver: RuleSolver) -> str:
        """
        应用规则解析器(RuleSolver)

        @param album: JmAlbumDetail
        @param photo: JmPhotoDetail
        @param rule_solver: Ptitle
        @return: photo.title
        """

        def choose_detail(key):
            if key == 0:
                return None
            if key == 1:
                return album
            if key == 2:
                return photo

        key, func = rule_solver
        detail = choose_detail(key)
        return func(detail)

    @classmethod
    def apply_rule_directly(cls, album, photo, rule: str) -> str:
        return cls.apply_rule_solver(album, photo, cls.get_rule_solver(rule))


class JmOption:
    JM_OP_VER = '2.0'

    def __init__(self,
                 dir_rule: Dict,
                 download: Dict,
                 client: Dict,
                 plugin: Dict,
                 filepath=None,
                 ):
        # 版本号
        self.version = self.JM_OP_VER
        # 路径规则配置
        self.dir_rule = DirRule(**dir_rule)
        # 请求配置
        self.client = AdvancedEasyAccessDict(client)
        # 下载配置
        self.download = AdvancedEasyAccessDict(download)
        # 插件配置
        self.plugin = AdvancedEasyAccessDict(plugin)
        # 其他配置
        self.filepath = filepath

        self.call_all_plugin('after_init')

    @property
    def download_cache(self):
        return self.download.cache

    @property
    def download_image_decode(self):
        return self.download.image.decode

    @property
    def download_threading_batch_count(self):
        return self.download.threading.batch_count

    @property
    def download_image_suffix(self):
        return self.download.image.suffix

    """
    下面是决定图片保存路径的方法
    """

    # noinspection PyUnusedLocal
    def decide_image_batch_count(self, photo: JmPhotoDetail):
        return self.download_threading_batch_count

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def decide_photo_batch_count(self, album: JmAlbumDetail):
        return os.cpu_count()

    def decide_image_save_dir(self, photo) -> str:
        # 使用 self.dir_rule 决定 save_dir
        save_dir = self.dir_rule.deside_image_save_dir(
            photo.from_album,
            photo
        )

        mkdir_if_not_exists(save_dir)
        return save_dir

    def decide_album_dir(self, album: JmAlbumDetail) -> str:
        """
        该方法目前仅在 plugin-zip 中使用，不建议外部调用
        """
        dir_layer = []
        dir_rule = self.dir_rule
        for rule in dir_rule.rule_dsl.split('_'):
            if rule == 'Bd':
                dir_layer.append(dir_rule.base_dir)
                continue

            if rule[0] == 'A':
                name = dir_rule.apply_rule_directly(album, None, rule)
                dir_layer.append(name)

            if rule[0] == 'P':
                break

        from os.path import join
        return join(*dir_layer)

    def decide_image_suffix(self, image: JmImageDetail):
        # 动图则使用原后缀
        suffix = image.img_file_suffix
        if suffix.endswith("gif"):
            return suffix

        # 非动图，以配置为先
        return self.download_image_suffix or suffix

    def decide_image_filepath(self, image: JmImageDetail) -> str:
        # 通过拼接生成绝对路径
        save_dir = self.decide_image_save_dir(image.from_photo)
        suffix = self.decide_image_suffix(image)
        return save_dir + image.img_file_name + suffix

    """
    下面是创建对象相关方法
    """

    @classmethod
    def default_dict(cls) -> Dict:
        return JmModuleConfig.option_default_dict()

    @classmethod
    def default(cls, proxies=None, domain=None) -> 'JmOption':
        """
        使用默认的 JmOption
        proxies, domain 为常用配置项，为了方便起见直接支持参数配置。
        其他配置项建议还是使用配置文件
        @param proxies: clash; 127.0.0.1:7890; v2ray
        @param domain: 18comic.vip; ["18comic.vip"]
        """
        if proxies is not None or domain is not None:
            return cls.construct({
                'client': {
                    'domain': [domain] if isinstance(domain, str) else domain,
                    'postman': {'meta_data': {'proxies': ProxyBuilder.build_by_str(proxies)}},
                },
            })

        return cls.construct({})

    @classmethod
    def construct(cls, dic: Dict, cover_default=True) -> 'JmOption':
        if cover_default:
            dic = cls.merge_default_dict(dic)

        version = dic.pop('version', None)
        if float(version) != float(cls.JM_OP_VER):
            # 版本兼容
            raise NotImplementedError('不支持的option版本')

        debug = dic.pop('debug', True)
        if debug is False:
            disable_jm_debug()

        return cls(**dic)

    def deconstruct(self) -> Dict:
        return {
            'version': self.version,
            'debug': JmModuleConfig.enable_jm_debug,
            'dir_rule': {
                'rule': self.dir_rule.rule_dsl,
                'base_dir': self.dir_rule.base_dir,
            },
            'download': self.download.src_dict,
            'client': self.client.src_dict,
        }

    @classmethod
    def from_file(cls, filepath: str) -> 'JmOption':
        dic: dict = PackerUtil.unpack(filepath)[0]
        return cls.construct(dic)

    def to_file(self, filepath=None):
        if filepath is None:
            filepath = self.filepath

        ExceptionTool.require_true(filepath is not None, "未指定JmOption的保存路径")

        PackerUtil.pack(self.deconstruct(), filepath)

    """
    下面是 build 方法
    """

    @field_cache("__jm_client_cache__")
    def build_jm_client(self, **kwargs):
        """
        该方法会首次调用会创建JmcomicClient对象，
        然后保存在self.__jm_client_cache__中，
        多次调用`不会`创建新的JmcomicClient对象
        """
        return self.new_jm_client(**kwargs)

    def new_jm_client(self, domain_list=None, impl=None, **kwargs) -> JmcomicClient:
        postman_conf: dict = self.client.postman.src_dict

        # support kwargs overwrite meta_data
        if len(kwargs) != 0:
            meta_data = postman_conf.get('meta_data', {})
            meta_data.update(kwargs)
            postman_conf['meta_data'] = meta_data

        # postman
        postman = Postmans.create(data=postman_conf)

        # domain_list
        if domain_list is None:
            domain_list = self.client.domain

        domain_list: List[str]
        if len(domain_list) == 0:
            domain_list = [JmModuleConfig.domain()]

        # client
        client = JmModuleConfig.client_impl_class(impl or self.client.impl)(
            postman,
            self.client.retry_times,
            fallback_domain_list=domain_list,
        )

        # enable cache
        if self.client.cache is True:
            client.enable_cache()

        return client

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

    def download_album(self, album_id):
        from .api import download_album
        download_album(album_id, self)

    def download_photo(self, photo_id):
        from .api import download_photo
        download_photo(photo_id, self)

    # 下面的方法为调用插件提供支持

    def call_all_plugin(self, group: str, **extra):
        plugin_list: List[dict] = self.plugin.get(group, [])
        if plugin_list is None or len(plugin_list) == 0:
            return

        # 保证 jm_plugin.py 被加载
        from .jm_plugin import JmOptionPlugin

        plugin_registry = JmModuleConfig.PLUGIN_REGISTRY
        for pinfo in plugin_list:
            key, kwargs = pinfo['plugin'], pinfo['kwargs']
            plugin_class: Optional[Type[JmOptionPlugin]] = plugin_registry.get(key, None)

            ExceptionTool.require_true(plugin_class is not None, f'[{group}] 未注册的plugin: {key}')

            self.invoke_plugin(plugin_class, kwargs, extra)

    def invoke_plugin(self, plugin_class, kwargs: Any, extra: dict):
        # 保证 jm_plugin.py 被加载
        from .jm_plugin import JmOptionPlugin

        plugin_class: Type[JmOptionPlugin]
        pkey = plugin_class.plugin_key

        try:
            # 检查插件的参数类型
            kwargs = self.fix_kwargs(kwargs)
            # 把插件的配置数据kwargs和附加数据extra合并
            # extra会覆盖kwargs
            if len(extra) != 0:
                kwargs.update(extra)
            # 构建插件对象
            plugin = plugin_class.build(self)
            # 调用插件功能
            jm_debug('plugin.invoke', f'调用插件: [{pkey}]')
            plugin.invoke(**kwargs)
        except JmcomicException as e:
            msg = str(e)
            jm_debug('plugin.exception', f'插件[{pkey}]调用失败，异常信息: {msg}')
            raise e
        except BaseException as e:
            msg = str(e)
            jm_debug('plugin.error', f'插件[{pkey}]运行遇到未捕获异常，异常信息: {msg}')
            raise e

    # noinspection PyMethodMayBeStatic
    def fix_kwargs(self, kwargs) -> Dict[str, Any]:
        """
        kwargs将来要传给方法参数，这要求kwargs的key是str类型，
        该方法检查kwargs的key的类型，如果不是str，尝试转为str，不行则抛异常。
        """
        ExceptionTool.require_true(
            isinstance(kwargs, dict),
            f'插件的kwargs参数必须为dict类型，而不能是类型: {type(kwargs)}'
        )

        kwargs: dict
        new_kwargs: Dict[str, Any] = {}

        for k, v in kwargs.items():
            if isinstance(k, str):
                new_kwargs[k] = v
                continue

            if isinstance(k, (int, float)):
                newk = str(k)
                jm_debug('plugin.kwargs', f'插件参数类型转换: {k} ({type(k)}) -> {newk} ({type(newk)})')
                new_kwargs[newk] = v
                continue

            ExceptionTool.raises(
                f'插件kwargs参数类型有误，'
                f'字段: {k}，预期类型为str，实际类型为{type(k)}'
            )

        return new_kwargs
