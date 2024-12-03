"""
Commonly used hooks for on_setattr.
"""
from . import _config
from .exceptions import FrozenAttributeError

def pipe(*setters):
    """
    Run all *setters* and return the return value of the last one.

    .. versionadded:: 20.1.0
    """
    def pipe_setter(instance, attribute, value):
        for setter in setters:
            value = setter(instance, attribute, value)
        return value
    return pipe_setter

def frozen(_, __, ___):
    """
    Prevent an attribute to be modified.

    .. versionadded:: 20.1.0
    """
    raise FrozenAttributeError("Can't set attribute: frozen")

def validate(instance, attrib, new_value):
    """
    Run *attrib*'s validator on *new_value* if it has one.

    .. versionadded:: 20.1.0
    """
    if attrib.validator is not None:
        attrib.validator(instance, attrib, new_value)
    return new_value

def convert(instance, attrib, new_value):
    """
    Run *attrib*'s converter -- if it has one -- on *new_value* and return the
    result.

    .. versionadded:: 20.1.0
    """
    if attrib.converter is not None:
        return attrib.converter(new_value)
    return new_value
NO_OP = object()
