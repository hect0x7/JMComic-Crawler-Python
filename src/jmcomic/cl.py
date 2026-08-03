import warnings

from .cli import *


warnings.warn(
    "The 'jmcomic.cl' module is deprecated and renamed to 'jmcomic.cli'. "
    "Please update your imports. It will be removed in version 2.7.4.",
    DeprecationWarning,
    stacklevel=2,
)
