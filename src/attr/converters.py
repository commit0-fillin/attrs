"""
Commonly useful converters.
"""
import typing
from ._compat import _AnnotationExtractor
from ._make import NOTHING, Factory, pipe
__all__ = ['default_if_none', 'optional', 'pipe', 'to_bool']

def optional(converter):
    """
    A converter that allows an attribute to be optional. An optional attribute
    is one which can be set to `None`.

    Type annotations will be inferred from the wrapped converter's, if it has
    any.

    Args:
        converter (typing.Callable):
            the converter that is used for non-`None` values.

    .. versionadded:: 17.1.0
    """
    def optional_converter(value):
        if value is None:
            return None
        return converter(value)
    
    return optional_converter

def default_if_none(default=NOTHING, factory=None):
    """
    A converter that allows to replace `None` values by *default* or the result
    of *factory*.

    Args:
        default:
            Value to be used if `None` is passed. Passing an instance of
            `attrs.Factory` is supported, however the ``takes_self`` option is
            *not*.

        factory (typing.Callable):
            A callable that takes no parameters whose result is used if `None`
            is passed.

    Raises:
        TypeError: If **neither** *default* or *factory* is passed.

        TypeError: If **both** *default* and *factory* are passed.

        ValueError:
            If an instance of `attrs.Factory` is passed with
            ``takes_self=True``.

    .. versionadded:: 18.2.0
    """
    if default is NOTHING and factory is None:
        raise TypeError("Must pass either `default` or `factory`.")
    
    if default is not NOTHING and factory is not None:
        raise TypeError("Must pass either `default` or `factory`, not both.")
    
    if isinstance(default, Factory):
        if default.takes_self:
            raise ValueError("Factory cannot have `takes_self=True`.")
        factory = default.factory
        default = NOTHING

    def default_if_none_converter(value):
        if value is None:
            if factory is not None:
                return factory()
            return default
        return value
    
    return default_if_none_converter

def to_bool(val):
    """
    Convert "boolean" strings (for example, from environment variables) to real
    booleans.

    Values mapping to `True`:

    - ``True``
    - ``"true"`` / ``"t"``
    - ``"yes"`` / ``"y"``
    - ``"on"``
    - ``"1"``
    - ``1``

    Values mapping to `False`:

    - ``False``
    - ``"false"`` / ``"f"``
    - ``"no"`` / ``"n"``
    - ``"off"``
    - ``"0"``
    - ``0``

    Raises:
        ValueError: For any other value.

    .. versionadded:: 21.3.0
    """
    if isinstance(val, bool):
        return val
    
    if isinstance(val, (str, int)):
        val = str(val).lower()
        if val in ("true", "t", "yes", "y", "on", "1"):
            return True
        if val in ("false", "f", "no", "n", "off", "0"):
            return False
    
    raise ValueError(f"Cannot convert {val!r} to bool")
