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

    RuleFunc = Callable[[Union[JmAlbumDetail, JmPhotoDetail, None]], str]
    RuleSolver = List[Tuple[int, RuleFunc]]

    rule_solver_cache: Dict[Tuple[str, str], RuleSolver] = dict()

    def __init__(self, rule, base_dir=None):
        self.base_dir = self.parse_dsl(base_dir)
        self.rule_dsl = rule
        self.get_rule_solver()

    def deside_image_save_dir(self,
                              album: JmAlbumDetail,
                              photo: JmPhotoDetail,
                              ) -> str:
        def choose_param(key):
            if key == 0:
                return None
            if key == 1:
                return album
            if key == 2:
                return photo

        solver_ls = self.get_rule_solver()

        path_ls = []
        for i, (key, func) in enumerate(solver_ls):
            try:
                param = choose_param(key)
                ret = func(param)
                path_ls.append(str(ret))
            except BaseException as e:
                # noinspection PyUnboundLocalVariable
                raise JmModuleConfig.exception(
                    f'路径规则"{self.rule_dsl}"的第{i + 1}个解析出错: {e},'
                    f'param is {param}'
                )

        return fix_filepath('/'.join(path_ls), is_dir=True)

    def get_rule_solver(self):
        key = self.rule_dsl, self.base_dir
        solver_ls = self.rule_solver_cache.get(key, None)

        if solver_ls is None:
            solver_ls = self.solve_rule_dsl(*key)
            self.rule_solver_cache[key] = solver_ls

        return solver_ls

    def solve_rule_dsl(self, rule_dsl: str, base_dir: str) -> RuleSolver:
        """
        解析下载路径dsl，得到一个路径规则解析列表
        """

        if '_' not in rule_dsl:
            raise NotImplementedError(f'不支持的dsl: "{rule_dsl}"')

        rule_ls = rule_dsl.split('_')
        solver_ls = []

        for rule in rule_ls:
            if rule == 'Bd':
                solver_ls.append((0, lambda _: base_dir))
                continue

            # Axxx or Pyyy
            if not rule.startswith(('A', 'P')):
                raise NotImplementedError(f'不支持的dsl: "{rule}" in "{rule_dsl}"')

            key = 1 if rule[0] == 'A' else 2
            solver_ls.append((
                key,
                lambda entity, ref=rule[1:]: fix_windir_name(str(getattr(entity, ref)))
            ))

        return solver_ls

    dsl_support = {
        '${workspace}': lambda text: workspace(),
    }

    def parse_dsl(self, base_dir: str):
        for k, func in self.dsl_support.items():
            if k in base_dir:
                base_dir = base_dir.replace(k, func(base_dir))
        return base_dir


class JmOption:
    JM_OP_VER = '2.0'

    def __init__(self,
                 dir_rule: Dict,
                 download: Dict,
                 client: Dict,
                 filepath=None,
                 ):
        # 版本号
        self.version = self.JM_OP_VER
        # 路径规则配置
        self.dir_rule = DirRule(**dir_rule)
        # 请求配置
        self.client = DictModel(client)
        # 下载配置
        self.download = DictModel(download)
        # 其他配置
        self.filepath = filepath

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

        if filepath is None:
            raise JmModuleConfig.exception("未指定JmOption的保存路径")

        PackerUtil.pack(self.deconstruct(), filepath)

    """
    下面是 build 方法
    """

    @field_cache("__jm_client_cache__")
    def build_jm_client(self, **kwargs) -> JmcomicClient:
        """
        该方法会首次调用会创建JmcomicClient对象，
        然后保存在self.__jm_client_cache__中，
        多次调用`不会`创建新的JmcomicClient对象
        """
        return self.new_jm_client(**kwargs)

    def new_jm_client(self, **kwargs) -> JmcomicClient:
        postman_conf: dict = self.client.postman.src_dict

        # support kwargs overwrite meta_data
        if len(kwargs) != 0:
            meta_data = postman_conf.get('meta_data', {})
            meta_data.update(kwargs)
            postman_conf['meta_data'] = meta_data

        # postman
        postman = Postmans.create(data=postman_conf)

        # domain_list
        domain_list = self.client.domain
        if len(domain_list) == 0:
            domain_list = [JmModuleConfig.domain()]

        # client
        client = JmModuleConfig.client_impl_class(self.client.impl)(
            postman,
            self.client.retry_times,
            fallback_domain_list=domain_list,
        )

        # enable cache
        if self.client.cache is True:
            client.enable_cache()

        return client

    @classmethod
    def default_dict(cls) -> Dict:
        return JmModuleConfig.option_default_dict()

    @classmethod
    def default(cls):
        return cls.construct({})

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
