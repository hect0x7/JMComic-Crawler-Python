# 该文件存放jmcomic的异常机制设计和实现
from .jm_entity import *


class JmcomicException(Exception):
    description = 'jmcomic 模块异常'

    def __init__(self, msg: str, context: dict):
        self.msg = msg
        self.context = context

    def from_context(self, key):
        return self.context[key]

    def __str__(self):
        return self.msg


class ResponseUnexpectedException(JmcomicException):
    description = '响应不符合预期异常'

    @property
    def resp(self):
        return self.from_context(ExceptionTool.CONTEXT_KEY_RESP)


class RegularNotMatchException(JmcomicException):
    description = '正则表达式不匹配异常'

    @property
    def resp(self):
        """
        可能为None
        """
        return self.context.get(ExceptionTool.CONTEXT_KEY_RESP, None)

    @property
    def error_text(self):
        return self.from_context(ExceptionTool.CONTEXT_KEY_HTML)

    @property
    def pattern(self):
        return self.from_context(ExceptionTool.CONTEXT_KEY_RE_PATTERN)


class JsonResolveFailException(ResponseUnexpectedException):
    description = 'Json解析异常'


class MissingAlbumPhotoException(ResponseUnexpectedException):
    description = '不存在本子或章节异常'

    @property
    def error_jmid(self) -> str:
        return self.from_context(ExceptionTool.CONTEXT_KEY_MISSING_JM_ID)


class RequestRetryAllFailException(JmcomicException):
    description = '请求重试全部失败异常'


class PartialDownloadFailedException(JmcomicException):
    description = '部分章节或图片下载失败异常'

    @property
    def downloader(self):
        return self.from_context(ExceptionTool.CONTEXT_KEY_DOWNLOADER)

class ExceptionTool:
    """
    抛异常的工具
    1: 能简化 if-raise 语句的编写
    2: 有更好的上下文信息传递方式
    """

    CONTEXT_KEY_RESP = 'resp'
    CONTEXT_KEY_HTML = 'html'
    CONTEXT_KEY_RE_PATTERN = 'pattern'
    CONTEXT_KEY_MISSING_JM_ID = 'missing_jm_id'
    CONTEXT_KEY_DOWNLOADER = 'downloader'

    @classmethod
    def raises(cls,
               msg: str,
               context: dict = None,
               etype: Optional[Type[Exception]] = None,
               ):
        """
        抛出异常

        :param msg: 异常消息
        :param context: 异常上下文数据
        :param etype: 异常类型，默认使用 JmcomicException
        """
        if context is None:
            context = {}

        if etype is None:
            etype = JmcomicException

        # 异常对象
        e = etype(msg, context)

        # 异常处理建议
        cls.notify_all_listeners(e)

        raise e

    @classmethod
    def raises_regex(cls,
                     msg: str,
                     html: str,
                     pattern: Pattern,
                     ):
        cls.raises(
            msg,
            {
                cls.CONTEXT_KEY_HTML: html,
                cls.CONTEXT_KEY_RE_PATTERN: pattern,
            },
            RegularNotMatchException,
        )

    @classmethod
    def raises_resp(cls,
                    msg: str,
                    resp,
                    etype=ResponseUnexpectedException
                    ):
        cls.raises(
            msg, {
                cls.CONTEXT_KEY_RESP: resp
            },
            etype,
        )

    @classmethod
    def raise_missing(cls,
                      resp,
                      jmid: str,
                      ):
        """
        抛出本子/章节的异常
        :param resp: 响应对象
        :param jmid: 禁漫本子/章节id
        """
        from .jm_toolkit import JmcomicText
        url = JmcomicText.format_album_url(jmid)

        req_type = "本子" if "album" in url else "章节"
        cls.raises(
            (
                f'请求的{req_type}不存在！({url})\n'
                '原因可能为:\n'
                f'1. id有误，检查你的{req_type}id\n'
                '2. 该漫画只对登录用户可见，请配置你的cookies，或者使用移动端Client（api）\n'
            ),
            {
                cls.CONTEXT_KEY_RESP: resp,
                cls.CONTEXT_KEY_MISSING_JM_ID: jmid,
            },
            MissingAlbumPhotoException,
        )

    @classmethod
    def require_true(cls, case: bool, msg: str):
        if case:
            return

        cls.raises(msg)

    @classmethod
    def replace_old_exception_executor(cls, raises: Callable[[Callable, str, dict], None]):
        old = cls.raises

        def new(msg, context=None, _etype=None):
            if context is None:
                context = {}
            raises(old, msg, context)

        cls.raises = new

    @classmethod
    def notify_all_listeners(cls, e):
        registry: Dict[Type, Callable[Type]] = JmModuleConfig.REGISTRY_EXCEPTION_LISTENER
        if not registry:
            return None

        for accept_type, listener in registry.items():
            if isinstance(e, accept_type):
                listener(e)
