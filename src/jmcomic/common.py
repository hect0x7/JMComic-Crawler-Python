import atexit
import copy
import inspect
import json
import os
import re
from re import compile
import sys
import threading
from threading import Thread, current_thread
import time
from time import sleep
import traceback
import typing
from typing import (
    Dict, List, Tuple, Set,
    Type, Callable, Any, Optional, Union,
    Iterable, Iterator, Generator, Sequence,
    IO, Match, Pattern, TypeVar,
)

_win_forbid_char = set('\\/:*?"<>|\n\t\r')


# ==================== 时间、装饰器与参数工具 ====================

def time_stamp(as_int=True) -> Union[int, float]:
    return int(time.time()) if as_int else time.time()


def field_cache(field_name=None, sentinel=None, obj=None):
    def wrapper(func):
        nonlocal field_name
        if field_name is None:
            field_name = f'__cache_{func.__name__}__'

        def func_exec(*args, **kwargs):
            target = args[0] if obj is None else obj
            attr = getattr(target, field_name, sentinel)
            if attr is not sentinel:
                return attr

            attr = func(*args, **kwargs)
            setattr(target, field_name, attr)
            return attr

        return func_exec

    return wrapper


def process_single_arg_to_args_and_kwargs(obj) -> Tuple[tuple, dict]:
    def to_tuple(args) -> tuple:
        if args is None:
            return ()
        return args if isinstance(args, (tuple, list)) else (args,)

    if isinstance(obj, list):
        args, kwargs = obj
        return to_tuple(args), kwargs or {}
    if isinstance(obj, dict):
        return (), obj
    return to_tuple(obj), {}


# ==================== 文件、路径与文本工具 ====================

def fix_windir_name(dn: str, attr_char='_') -> str:
    name = ''.join(attr_char if c in _win_forbid_char else c for c in dn)
    if name.endswith('.'):
        name = name.rstrip('.')
    return name


def fix_filepath(filepath: str, *_args, **_kwargs) -> str:
    filepath = filepath.replace("\\", '/').replace("//", '/')
    if os.path.isdir(filepath):
        return filepath if filepath.endswith('/') else filepath + '/'
    return filepath


def fix_suffix(suffix: str) -> str:
    return suffix if suffix.startswith('.') else f'.{suffix}'


def mkdir_if_not_exists(dirpath: str):
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)


def of_file_name(filepath: str, trim_suffix=False) -> str:
    name = os.path.basename(filepath)
    return os.path.splitext(name)[0] if trim_suffix else name


def of_file_suffix(filepath: str, trim_comma=False) -> str:
    ext = os.path.splitext(filepath)[1]
    return ext.lstrip('.') if trim_comma else ext


def suffix_not_equal(fp1: str, fp2: str) -> bool:
    return of_file_suffix(fp1) != of_file_suffix(fp2)


def files_of_dir(abs_dir_path: str) -> List[str]:
    abs_dir_path = fix_filepath(os.path.abspath(abs_dir_path))
    return [f'{abs_dir_path}{f_or_d}' for f_or_d in sorted(os.listdir(abs_dir_path))]


def parse_unicode_escape_text(text: str) -> str:
    def decode(raw: re.Match):
        return raw.group(0).encode('utf-8').decode('unicode_escape')

    return re.sub(r"\\u\w{4}", decode, text).replace(r"\/", "/")


def str_to_line_iter(lines: str):
    for line in lines.strip().splitlines():
        line = line.strip()
        if line != '':
            yield line


def str_to_list(lines: str) -> List[str]:
    return list(str_to_line_iter(lines))


def str_to_set(lines: str) -> Set[str]:
    return set(str_to_line_iter(lines))


# ==================== 数据容器与序列化 (AdvancedDict / PackerUtil) ====================

class AdvancedDict:
    """
    功能增强版 Dict，支持属性读写 (obj.key) 与字典下标读写 (obj[key])。
    """

    def __init__(self, data: dict):
        if not isinstance(data, dict):
            raise AssertionError('初始化参数必须是dict类型')
        self._data = data

    @classmethod
    def wrap(cls, data):
        if isinstance(data, dict):
            return cls(data)
        if isinstance(data, cls):
            return cls(data.src_dict)
        raise NotImplementedError(f'unsupported type: {type(data)}')

    def __getattr__(self, item):
        return self.wrap_value(self._data[item])

    def __setattr__(self, key, value):
        if key == '_data':
            return super().__setattr__(key, value)
        self._data[key] = value

    def __str__(self):
        return str(self._data)

    def __repr__(self):
        return repr(self._data)

    def __setitem__(self, key, value):
        self._data[key] = value

    @classmethod
    def wrap_value(cls, v):
        if isinstance(v, (list, tuple)):
            return [cls(e) if isinstance(e, dict) else e for e in v]
        if isinstance(v, dict):
            return cls(v)
        return v

    @property
    def src_dict(self):
        return self._data

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, item):
        return self.wrap_value(self._data[item])

    def get(self, *args, **kwargs):
        return self._data.get(*args, **kwargs)

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data)

    def __delitem__(self, key):
        del self._data[key]

    def setdefault(self, k, v):
        return self._data.setdefault(k, v)

    def pop(self, k, dv=None):
        return self._data.pop(k, dv)

    def to_file(self, filepath):
        PackerUtil.pack(self._data, filepath)

    def copy(self):
        return self.__class__(copy.deepcopy(self._data))

    __copy__ = copy


class PackerUtil:
    mode_yml = 'yml'
    mode_json = 'json'
    mode_py_pickle = 'pickle'

    @classmethod
    def decide_mode(cls, filepath: str) -> str:
        suffix = of_file_suffix(filepath, trim_comma=True)
        return cls.mode_yml if suffix == 'yaml' else suffix

    @classmethod
    def pack(cls, obj: object, filepath: str, packer=None):
        if packer is not None:
            return packer.pack(obj, filepath)

        mode = cls.decide_mode(filepath)
        if mode == cls.mode_yml:
            import yaml
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(obj, f, allow_unicode=True, indent=2)
        elif mode == cls.mode_json:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cls.to_dict(obj), f, ensure_ascii=False, indent=2)
        elif mode == cls.mode_py_pickle:
            import pickle
            with open(filepath, 'wb') as f:
                pickle.dump(obj, f)
        else:
            raise AssertionError(f"unknown mode: '{mode}'")

    @classmethod
    def unpack(cls, filepath: str, clazz: Optional[Type] = None, packer=None) -> Tuple[Any, Any]:
        if packer is not None:
            return packer.unpack(filepath, clazz), packer

        mode = cls.decide_mode(filepath)
        if mode == cls.mode_yml:
            import yaml
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.load(f, yaml.SafeLoader)
        elif mode == cls.mode_json:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if clazz is not None:
                obj = clazz()
                obj.__dict__.update(data)
                data = obj
        elif mode == cls.mode_py_pickle:
            import pickle
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
        else:
            raise AssertionError(f"unknown mode: '{mode}'")

        return data, None

    @classmethod
    def unpack_by_str(cls, text: str, mode: str = mode_yml, clazz: Optional[Type] = None) -> Tuple[Any, Any]:
        if mode in (cls.mode_yml, 'yaml'):
            import yaml
            data = yaml.load(text, yaml.SafeLoader)
        elif mode == cls.mode_json:
            data = json.loads(text)
            if clazz is not None:
                obj = clazz()
                obj.__dict__.update(data)
                data = obj
        else:
            raise AssertionError(f"unknown mode: '{mode}'")

        return data, None

    @classmethod
    def to_dict(cls, obj):
        if hasattr(obj, "__dict__"):
            d = dict(obj.__dict__)
            for key, value in d.items():
                if hasattr(value, "__dict__"):
                    d[key] = cls.to_dict(value)
            return d
        if isinstance(obj, list):
            return [cls.to_dict(item) for item in obj]
        return obj


# ==================== 多线程与并发任务启动器 ====================

def multi_thread_launcher(iter_objs: Iterable,
                          apply_each_obj_func: Callable,
                          wait_finish: bool = True,
                          ) -> List[Thread]:
    thread_list: List[Thread] = []
    for obj in iter_objs:
        args, kwargs = process_single_arg_to_args_and_kwargs(obj)
        t = Thread(target=apply_each_obj_func, args=args, kwargs=kwargs, daemon=True)
        t.start()
        thread_list.append(t)

    if wait_finish:
        for t in thread_list:
            t.join()

    return thread_list


# ==================== 网络代理与 HTTP Postman ====================

class ProxyBuilder:
    proxy_protocols = ['https', 'http']
    addr_f = '{}:{}'

    @classmethod
    def build_proxy(cls, address):
        return {protocol: address for protocol in cls.proxy_protocols}

    @classmethod
    def clash_proxy(cls, ip='127.0.0.1', port='7890'):
        return cls.build_proxy(cls.addr_f.format(ip, port))

    @classmethod
    def v2ray_proxy(cls, ip='127.0.0.1', port='10809'):
        return cls.build_proxy(cls.addr_f.format(ip, port))

    @classmethod
    def fiddler_proxy(cls, ip='127.0.0.1', port='8888'):
        return cls.build_proxy(cls.addr_f.format(ip, port))

    @classmethod
    def system_proxy(cls):
        import urllib.request
        proxies: dict = urllib.request.getproxies()
        if len(proxies) == 0:
            return {}

        addr = proxies.get('http') or proxies.get('https')
        if addr is None:
            return {}

        prot = '://'
        if prot in addr:
            addr = addr[addr.find(prot) + len(prot):]

        return cls.build_proxy(addr)

    @classmethod
    def build_by_str(cls, text):
        proxy = getattr(cls, text + '_proxy', None)
        if proxy is None:
            return cls.build_proxy(text)
        return proxy()

    v2Ray_proxy = v2ray_proxy


class Postman:
    postman_key = 'abstract'

    @classmethod
    def create(cls, **kwargs):
        return cls(kwargs)

    def __init__(self, meta_data: Optional[dict] = None) -> None:
        if meta_data is None:
            meta_data = {}
        elif not isinstance(meta_data, dict):
            raise AssertionError('meta_data is not a dict')
        self.meta_data: dict = meta_data

    def before_request(self, kwargs: dict) -> dict:
        ret = self.meta_data.copy()
        for k, v in kwargs.items():
            if v is not None:
                ret[k] = v
        return ret

    def get(self, url: str, **kwargs):
        raise NotImplementedError

    def post(self, url: str, **kwargs):
        raise NotImplementedError

    def get_meta_data(self, key=None, dv=None) -> Any:
        if key is None:
            return self.meta_data
        return self.meta_data.get(key, dv)

    def __getitem__(self, item):
        return self.get_meta_data()[item]

    def __setitem__(self, key, value):
        self.get_meta_data()[key] = value

    def copy(self) -> 'Postman':
        return self.__class__(self.meta_data.copy())


class SessionPostman(Postman):
    postman_key = 'abstract-session'

    # noinspection PyMissingConstructor
    def __init__(self, meta_data: Optional[dict] = None) -> None:
        if meta_data is None:
            meta_data = {}
        elif not isinstance(meta_data, dict):
            raise AssertionError('meta_data is not a dict')
        self.session = self.create_session(meta_data)

    def create_session(self, kwargs: dict):
        raise NotImplementedError

    def before_request(self, kwargs: dict) -> dict:
        return kwargs

    def get(self, url: str, **kwargs):
        return self.session.get(url, **self.before_request(kwargs))

    def post(self, url: str, **kwargs):
        return self.session.post(url, **self.before_request(kwargs))

    def get_meta_data(self, key=None, dv=None) -> Any:
        if key is None:
            return self.session.__dict__
        return getattr(self.session, key, dv)

    def __getitem__(self, item):
        return getattr(self.session, item)

    def __setitem__(self, key, value):
        setattr(self.session, key, value)


class RequestsPostman(Postman):
    postman_key = 'requests'

    def get(self, url: str, **kwargs):
        import requests
        return requests.get(url, **self.before_request(kwargs))

    def post(self, url: str, **kwargs):
        import requests
        return requests.post(url, **self.before_request(kwargs))

    def before_request(self, kwargs: dict) -> dict:
        kwargs = super().before_request(kwargs)
        kwargs.pop('impersonate', None)
        return kwargs


class RequestsSessionPostman(SessionPostman):
    postman_key = 'requests-session'

    def create_session(self, kwargs: dict):
        import requests
        session = requests.Session()
        if not kwargs.get('headers'):
            session.headers.clear()
        for k, v in kwargs.items():
            if k == 'impersonate' or v is None:
                continue
            if k == 'cookies' and isinstance(v, dict):
                v = requests.sessions.cookiejar_from_dict(v)
            setattr(session, k, v)
        return session

    def __setitem__(self, key, value):
        if key == 'cookies' and isinstance(value, dict):
            import requests
            value = requests.sessions.cookiejar_from_dict(value)
        super().__setitem__(key, value)

    def before_request(self, kwargs: dict) -> dict:
        kwargs = super().before_request(kwargs)
        kwargs.pop('impersonate', None)
        return kwargs


class CurlCffiPostman(Postman):
    postman_key = 'curl_cffi'

    def get(self, url: str, **kwargs):
        from curl_cffi import requests
        return requests.get(url, **self.before_request(kwargs))

    def post(self, url: str, **kwargs):
        from curl_cffi import requests
        return requests.post(url, **self.before_request(kwargs))


class CurlCffiSessionPostman(SessionPostman):
    postman_key = 'curl_cffi_session'

    def create_session(self, kwargs: dict):
        from curl_cffi import requests
        return requests.Session(**kwargs)


class Postmans:
    impl_clazz_dict: Dict[str, Type[Postman]] = {
        RequestsPostman.postman_key: RequestsPostman,
        RequestsSessionPostman.postman_key: RequestsSessionPostman,
        CurlCffiPostman.postman_key: CurlCffiPostman,
        CurlCffiSessionPostman.postman_key: CurlCffiSessionPostman,
        'cffi': CurlCffiPostman,
    }

    @classmethod
    def register(cls, clazz: Type[Postman], key: Optional[str] = None):
        cls.impl_clazz_dict[key or clazz.postman_key] = clazz

    @classmethod
    def get_impl_clazz(cls, key: str) -> Type[Postman]:
        clazz = cls.impl_clazz_dict.get(key, None)
        if clazz is None:
            raise AssertionError(f'key "{key}" not found in registry of {Postman}')
        return clazz

    @classmethod
    def new_session(cls, **kwargs) -> Postman:
        return cls.get_impl_clazz('curl_cffi_session').create(**kwargs)

    @classmethod
    def new_postman(cls, **kwargs) -> Postman:
        return cls.get_impl_clazz('curl_cffi').create(**kwargs)

    @classmethod
    def create(cls, filepath='./postman.yml', data: Optional[dict] = None) -> Postman:
        if data is None:
            data = PackerUtil.unpack(filepath)[0]
            if data is None:
                raise AssertionError(f'空配置文件: {filepath}')

        if 'metadata' in data:
            data.setdefault('meta_data', data['metadata'])

        meta_data = data.setdefault('meta_data', {})
        proxies = meta_data.get('proxies', None)
        if proxies is not None and not isinstance(proxies, dict):
            meta_data['proxies'] = ProxyBuilder.build_by_str(proxies)

        impl_type = data.get('type', 'requests')
        if impl_type.startswith('requests') and 'impersonate' in meta_data:
            meta_data.pop('impersonate')

        clazz = cls.get_impl_clazz(impl_type)
        return clazz(meta_data)
