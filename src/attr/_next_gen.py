"""
These are keyword-only APIs that call `attr.s` and `attr.ib` with different
default values.
"""
from functools import partial
from . import setters
from ._funcs import asdict as _asdict
from ._funcs import astuple as _astuple
from ._make import _DEFAULT_ON_SETATTR, NOTHING, _frozen_setattrs, attrib, attrs
from .exceptions import UnannotatedAttributeError

def define(maybe_cls=None, *, these=None, repr=None, unsafe_hash=None, hash=None, init=None, slots=True, frozen=False, weakref_slot=True, str=False, auto_attribs=None, kw_only=False, cache_hash=False, auto_exc=True, eq=None, order=False, auto_detect=True, getstate_setstate=None, on_setattr=None, field_transformer=None, match_args=True):
    def wrap(cls):
        if these is None:
            these = {}

        if unsafe_hash is None and hash is not None:
            unsafe_hash = hash

        if auto_attribs is None:
            auto_attribs = _determine_auto_attribs(cls)

        return _attrs(
            these=these,
            repr=repr,
            unsafe_hash=unsafe_hash,
            init=init,
            slots=slots,
            frozen=frozen,
            weakref_slot=weakref_slot,
            str=str,
            auto_attribs=auto_attribs,
            kw_only=kw_only,
            cache_hash=cache_hash,
            auto_exc=auto_exc,
            eq=eq,
            order=order,
            auto_detect=auto_detect,
            collect_by_mro=True,
            getstate_setstate=getstate_setstate,
            on_setattr=on_setattr,
            field_transformer=field_transformer,
            match_args=match_args,
        )(cls)

    # maybe_cls's type depends on the usage of the decorator.  It's a class
    # if it's used as `@define` but ``None`` if used as `@define()`.
    if maybe_cls is None:
        return wrap
    else:
        return wrap(maybe_cls)

def _determine_auto_attribs(cls):
    """
    Determine whether auto_attribs should be True or False based on the class definition.
    """
    annotations = getattr(cls, '__annotations__', {})
    unannotated_attrs = [name for name in dir(cls) if not name.startswith('__') and not name in annotations]
    return bool(annotations) and not any(isinstance(getattr(cls, name, None), _CountingAttr) for name in unannotated_attrs)
mutable = define
frozen = partial(define, frozen=True, on_setattr=None)

def field(*, default=NOTHING, validator=None, repr=True, hash=None, init=True, metadata=None, type=None, converter=None, factory=None, kw_only=False, eq=None, order=None, on_setattr=None, alias=None):
    if factory is not None:
        if default is not NOTHING:
            raise ValueError("Can't specify both 'default' and 'factory'.")
        default = Factory(factory)

    if converter is not None:
        converter = _ensure_converter(converter)

    if validator is not None:
        validator = _ensure_validator(validator)

    return _CountingAttr(
        default=default,
        validator=validator,
        repr=repr,
        cmp=None,
        hash=hash,
        init=init,
        metadata=metadata,
        type=type,
        converter=converter,
        kw_only=kw_only,
        eq=eq,
        order=order,
        on_setattr=on_setattr,
        alias=alias,
    )

def _ensure_converter(converter):
    """
    Helper function to ensure the converter is a Converter instance.
    """
    if isinstance(converter, Converter):
        return converter
    return Converter(converter)

def _ensure_validator(validator):
    """
    Helper function to ensure the validator is a callable or a list of callables.
    """
    if callable(validator):
        return validator
    if isinstance(validator, (list, tuple)):
        return and_(*validator)
    raise TypeError("validator must be a callable or a list of callables.")

def asdict(inst, *, recurse=True, filter=None, value_serializer=None):
    """
    Same as `attr.asdict`, except that collections types are always retained
    and dict is always used as *dict_factory*.

    .. versionadded:: 21.3.0
    """
    return _asdict(
        inst,
        recurse=recurse,
        filter=filter,
        dict_factory=dict,
        retain_collection_types=True,
        value_serializer=value_serializer,
    )

def astuple(inst, *, recurse=True, filter=None):
    """
    Same as `attr.astuple`, except that collections types are always retained
    and `tuple` is always used as the *tuple_factory*.

    .. versionadded:: 21.3.0
    """
    return _astuple(
        inst,
        recurse=recurse,
        filter=filter,
        tuple_factory=tuple,
        retain_collection_types=True
    )
