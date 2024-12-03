"""
Commonly useful filters for `attrs.asdict` and `attrs.astuple`.
"""
from ._make import Attribute

def _split_what(what):
    """
    Returns a tuple of `frozenset`s of classes and attributes.
    """
    classes = frozenset(cls for cls in what if isinstance(cls, type))
    attributes = frozenset(attr for attr in what if not isinstance(attr, type))
    return classes, attributes

def include(*what):
    """
    Create a filter that only allows *what*.

    Args:
        what (list[type, str, attrs.Attribute]):
            What to include. Can be a type, a name, or an attribute.

    Returns:
        Callable:
            A callable that can be passed to `attrs.asdict`'s and
            `attrs.astuple`'s *filter* argument.

    .. versionchanged:: 23.1.0 Accept strings with field names.
    """
    classes, attributes = _split_what(what)

    def include_filter(attribute, value):
        return (
            attribute.name in attributes
            or attribute.__class__ in classes
            or attribute in attributes
        )

    return include_filter

def exclude(*what):
    """
    Create a filter that does **not** allow *what*.

    Args:
        what (list[type, str, attrs.Attribute]):
            What to exclude. Can be a type, a name, or an attribute.

    Returns:
        Callable:
            A callable that can be passed to `attrs.asdict`'s and
            `attrs.astuple`'s *filter* argument.

    .. versionchanged:: 23.3.0 Accept field name string as input argument
    """
    classes, attributes = _split_what(what)

    def exclude_filter(attribute, value):
        return not (
            attribute.name in attributes
            or attribute.__class__ in classes
            or attribute in attributes
        )

    return exclude_filter
