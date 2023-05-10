from .jm_client_impl import *


class JmOptionAdvice:

    def decide_image_save_dir(self,
                              option: 'JmOption',
                              photo_detail: JmPhotoDetail,
                              ) -> StrNone:
        """
        决定一个本子图片的下载文件夹
        @param option: JmOption对象
        @param photo_detail: 本子章节实体类
        @return: 下载文件夹，为空表示不处理
        """
        pass

    def decide_image_filepath(self,
                              option: 'JmOption',
                              photo_detail: JmPhotoDetail,
                              index: int,
                              ) -> StrNone:
        """
        决定一个本子图片的绝对路径
        @param option: JmOption对象
        @param photo_detail: 本子章节实体类
        @param index: 本子章节里的第几章图片
        @return: 下载绝对路径，为空表示不处理
        """
        pass

    def decide_image_suffix(self,
                            option: 'JmOption',
                            img_detail: JmImageDetail,
                            ) -> StrNone:
        """
        决定一个图片的保存后缀名
        @param option: JmOption对象
        @param img_detail: 禁漫图片实体类
        @return: 保存后缀名，为空表示不处理
        """
        pass


class JmAdviceRegistry:
    advice_registration: Dict[Any, List[JmOptionAdvice]] = {}

    @classmethod
    def register_advice(cls, base, *advice):
        advice_ls = cls.advice_registration.get(base, None)

        if advice_ls is None:
            advice_ls = list(advice)
            cls.advice_registration[base] = advice_ls
        else:
            for e in advice:
                advice_ls.append(e)

        return advice

    @classmethod
    def get_advice(cls, base) -> List[JmOptionAdvice]:
        return cls.advice_registration.setdefault(base, [])


class DirRule:
    rule_sample = [
        # 根目录 / Album-id / Photo-序号 /
        'Bd_Aid_Pindex',  # 禁漫网站的默认下载方式

        # 根目录 / Album-作者 / Album-标题 / Photo-序号 /
        'Bd_Aauthor_Atitle_Pindex',

        '${workspace}_Aid_Pindex',
    ]

    dsl_support = {
        '${workspace}': lambda text: workspace(),
    }

    RuleFunc = Callable[[Union[JmAlbumDetail, JmPhotoDetail, None]], str]
    RuleSolver = List[Tuple[int, RuleFunc]]

    rule_solver_cache: Dict[Tuple[str, str], RuleSolver] = dict()

    def __init__(self, rule, base_dir=None):
        self.base_dir = base_dir
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
                raise AssertionError(f'路径规则"{self.rule_dsl}"的第{i + 1}个解析出错: {e}, param is {param}')

        return '/'.join(path_ls) + '/'

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

            if rule in self.dsl_support:
                solver_ls.append((0, lambda _, ref=rule: self.dsl_support[ref](ref)))
                continue

            # Axxx or Pyyy
            if not rule.startswith(('A', 'P')):
                raise NotImplementedError(f'不支持的dsl: "{rule}" in "{rule_dsl}"')

            key = 1 if rule[0] == 'A' else 2
            field_name = rule[1:]
            solver_ls.append((key, lambda album_or_photo, ref=field_name: getattr(album_or_photo, ref)))

        return solver_ls


class JmOption(SaveableEntity):
    _proxies_mapping = {
        'clash': ProxyBuilder.clash_proxy,
        'v2Ray': ProxyBuilder.v2Ray_proxy
    }

    when_del_save_file = False
    cache_jm_client = True

    def __init__(self,
                 dir_rule: DirRule,
                 client_config: dict,
                 filepath: StrNone = None,
                 disable_jm_module_debug=False,
                 download_use_disk_cache=True,
                 download_convert_image_suffix: StrNone = None,
                 download_image_then_decode=True,
                 download_multi_thread_photo_len_limit=30,
                 download_multi_thread_photo_batch_count=10,
                 ):

        # 请求配置
        self.client_config = client_config
        self.client_config['postman_type_list'] = list(Postmans.postman_impl_class_dict.keys())

        # 下载配置
        self.dir_rule = dir_rule
        self.download_use_disk_cache = download_use_disk_cache
        self.download_image_then_decode = download_image_then_decode
        self.download_multi_thread_photo_len_limit = download_multi_thread_photo_len_limit
        self.download_multi_thread_photo_batch_count = download_multi_thread_photo_batch_count
        # suffix的标准形式是 ".xxx"。如果传入的是"xxx"，要补成 ".xxx"
        if download_convert_image_suffix is not None:
            download_convert_image_suffix = fix_suffix(download_convert_image_suffix)
        self.download_convert_image_suffix = download_convert_image_suffix

        # 其他配置
        self.filepath = filepath
        self.disable_jm_module_debug = disable_jm_module_debug
        if disable_jm_module_debug:
            disable_jm_debug()

    """
    下面是决定图片保存路径的方法
    """

    def decide_image_save_dir(self, photo_detail) -> str:
        # 先检查advice的回调，如果回调支持，则优先使用回调
        for advice in JmAdviceRegistry.get_advice(self):
            save_dir = advice.decide_image_save_dir(self, photo_detail)
            if save_dir is not None:
                return save_dir

        # 使用 self.dir_rule 决定 save_dir
        save_dir = self.dir_rule.deside_image_save_dir(
            photo_detail.from_album,
            photo_detail
        )

        mkdir_if_not_exists(save_dir)
        return save_dir

    def decide_image_suffix(self, img_detail: JmImageDetail):
        # 先检查advice的回调，如果回调支持，则优先使用回调
        for advice in JmAdviceRegistry.get_advice(self):
            suffix = advice.decide_image_suffix(self, img_detail)
            if suffix is not None:
                return suffix

        # 动图则使用原后缀
        suffix = img_detail.img_file_suffix
        if suffix.endswith("gif"):
            return suffix

        # 非动图，以配置为先
        return self.download_convert_image_suffix or suffix

    def decide_image_filepath(self, photo_detail: JmPhotoDetail, index: int) -> str:
        # 先检查advice的回调，如果回调支持，则优先使用回调
        for advice in JmAdviceRegistry.get_advice(self):
            filepath = advice.decide_image_filepath(self, photo_detail, index)
            if filepath is not None:
                return filepath

        # 通过拼接生成绝对路径
        save_dir = self.decide_image_save_dir(photo_detail)
        image: JmImageDetail = photo_detail[index]
        suffix = self.decide_image_suffix(image)
        return save_dir + image.img_file_name + suffix

    """
    下面是对Advice的支持
    """

    def register_advice(self, *advice):
        JmAdviceRegistry.register_advice(self, *advice)

    """
    下面是创建对象相关方法
    """

    @classmethod
    def default(cls) -> 'JmOption':
        return JmOption(
            DirRule(workspace(), 'Bd_PTitle'),
            cls.default_client_config(),
        )

    @classmethod
    def create_from_file(cls, filepath: str) -> 'JmOption':
        jm_option: JmOption = PackerUtil.unpack(filepath, JmOption)[0]
        jm_option.filepath = filepath
        return jm_option

    @classmethod
    def default_client_config(cls):
        return {
            'domain': JmModuleConfig.domain(),
            'meta_data': {
                'cookies': None,
                'headers': JmModuleConfig.headers(),
                'allow_redirects': True,
            },
            'postman_type_list': [
                'requests',
                'requests_Session',
                'cffi',
                'cffi_Session',
            ]
        }

    def save_base_dir(self):
        return of_dir_path(self.filepath)

    def save_file_name(self) -> str:
        return of_file_name(self.filepath)

    def save_to_file(self, filepath=None):
        if filepath is None:
            filepath = self.filepath

        if filepath is None:
            raise AssertionError("未指定JmOption的保存路径")

        super().save_to_file(filepath)

    """
    下面是 build 方法
    """

    def build_jm_client(self) -> JmcomicClient:
        if self.cache_jm_client is not True:
            client = self.new_jm_client()
        else:
            key = self
            client = JmModuleConfig.jm_client_caches.get(key, None)
            if client is None:
                client = self.new_jm_client()
                JmModuleConfig.jm_client_caches.setdefault(key, client)

        return client

    def new_jm_client(self) -> JmHtmlClient:
        meta_data = self.client_config['meta_data']
        postman_clazz = Postmans.get_impl_clazz(self.client_config.get('postman_type', 'cffi'))
        proxies = None
        domain = None
        postman: Optional[Postman] = None

        def decide_proxies(key='proxies'):
            nonlocal proxies
            proxies = meta_data.get(key, None)

            # 无代理，或代理已配置好好的
            if proxies is None or isinstance(proxies, dict):
                return

            # 有代理
            if proxies in self._proxies_mapping:
                proxies = self._proxies_mapping[proxies]()
            else:
                proxies = ProxyBuilder.build_proxy(proxies)

            meta_data[key] = proxies

        def decide_domain(key='domain') -> str:
            nonlocal domain
            domain = self.client_config.get(key, None)
            if domain is None:
                temp_postman = postman_clazz.create(
                    headers=JmModuleConfig.headers(JmModuleConfig.JM_REDIRECT_URL),
                    proxies=proxies,
                )
                domain = JmModuleConfig.domain(temp_postman)

            domain = JmcomicText.parse_to_jm_domain(domain)
            self.client_config[key] = domain
            return domain

        def handle_headers(key='headers'):
            headers = meta_data.get(key, None)
            if headers is None or (not isinstance(headers, dict)) or len(headers) == 0:
                # 未配置headers，使用默认headers
                headers = JmModuleConfig.headers(domain)

            meta_data[key] = headers

        def handle_postman():
            nonlocal postman
            postman = postman_clazz(meta_data)

        # 1. 决定 代理
        decide_proxies()
        # 2. 指定 JM域名
        decide_domain()
        # 3. 处理 headers
        handle_headers()
        # 4. 创建 postman
        handle_postman()

        jm_debug('option', f'New Client → [{domain}], impl: {postman_clazz}')

        # 创建 JmHtmlClient 对象
        client = JmHtmlClient(
            postman=postman,
            domain=domain,
            retry_times=self.client_config.get('retry_times', None)
        )

        return client


def _register_yaml_constructor():
    from yaml import add_constructor, Loader, Node

    tag_mapping = {
        'tag:yaml.org,2002:python/object:jmcomic.jm_option.JmOption': JmOption,
        'tag:yaml.org,2002:python/object:jmcomic.jm_option.DirRule': DirRule,
    }

    def constructor(loader: Loader, node: Node):
        for tag, clazz in tag_mapping.items():
            if node.tag == tag:
                state = loader.construct_mapping(node)
                try:
                    obj = clazz(**state)
                except TypeError as e:
                    raise AssertionError(f"构造函数不匹配: {clazz.__name__}\nTypeError: {e}")

                # obj.__dict__.update(state)
                return obj

    for tag in tag_mapping.keys():
        add_constructor(tag, constructor)


_register_yaml_constructor()
