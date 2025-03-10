import inspect
import platform
import sys
import threading
from collections.abc import Mapping, Sequence
from typing import _GenericAlias
PYPY = platform.python_implementation() == 'PyPy'
PY_3_8_PLUS = sys.version_info[:2] >= (3, 8)
PY_3_9_PLUS = sys.version_info[:2] >= (3, 9)
PY_3_10_PLUS = sys.version_info[:2] >= (3, 10)
PY_3_11_PLUS = sys.version_info[:2] >= (3, 11)
PY_3_12_PLUS = sys.version_info[:2] >= (3, 12)
PY_3_13_PLUS = sys.version_info[:2] >= (3, 13)
PY_3_14_PLUS = sys.version_info[:2] >= (3, 14)
if sys.version_info < (3, 8):
    try:
        from typing_extensions import Protocol
    except ImportError:
        Protocol = object
else:
    from typing import Protocol
if PY_3_14_PLUS:
    import annotationlib
    _get_annotations = annotationlib.get_annotations
else:

    def _get_annotations(cls):
        """
        Get annotations for *cls*.
        """
        if hasattr(cls, '__annotations__'):
            return cls.__annotations__
        return {}

class _AnnotationExtractor:
    """
    Extract type annotations from a callable, returning None whenever there
    is none.
    """
    __slots__ = ['sig']

    def __init__(self, callable):
        try:
            self.sig = inspect.signature(callable)
        except (ValueError, TypeError):
            self.sig = None

    def get_first_param_type(self):
        """
        Return the type annotation of the first argument if it's not empty.
        """
        if self.sig is None:
            return None
        params = list(self.sig.parameters.values())
        if not params:
            return None
        first_param = params[0]
        return first_param.annotation if first_param.annotation != inspect.Parameter.empty else None

    def get_return_type(self):
        """
        Return the return type if it's not empty.
        """
        if self.sig is None:
            return None
        return self.sig.return_annotation if self.sig.return_annotation != inspect.Signature.empty else None
repr_context = threading.local()

def get_generic_base(cl):
    """If this is a generic class (A[str]), return the generic base for it."""
    if isinstance(cl, _GenericAlias):
        return cl.__origin__
    return None
