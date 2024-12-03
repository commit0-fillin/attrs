from __future__ import annotations
import abc
import contextlib
import copy
import enum
import functools
import inspect
import itertools
import linecache
import sys
import types
import typing
from operator import itemgetter
from . import _compat, _config, setters
from ._compat import PY_3_8_PLUS, PY_3_10_PLUS, PY_3_11_PLUS, _AnnotationExtractor, _get_annotations, get_generic_base
from .exceptions import DefaultAlreadySetError, FrozenInstanceError, NotAnAttrsClassError, UnannotatedAttributeError
_OBJ_SETATTR = object.__setattr__
_INIT_FACTORY_PAT = '__attr_factory_%s'
_CLASSVAR_PREFIXES = ('typing.ClassVar', 't.ClassVar', 'ClassVar', 'typing_extensions.ClassVar')
_HASH_CACHE_FIELD = '_attrs_cached_hash'
_EMPTY_METADATA_SINGLETON = types.MappingProxyType({})
_SENTINEL = object()
_DEFAULT_ON_SETATTR = setters.pipe(setters.convert, setters.validate)

class _Nothing(enum.Enum):
    """
    Sentinel to indicate the lack of a value when `None` is ambiguous.

    If extending attrs, you can use ``typing.Literal[NOTHING]`` to show
    that a value may be ``NOTHING``.

    .. versionchanged:: 21.1.0 ``bool(NOTHING)`` is now False.
    .. versionchanged:: 22.2.0 ``NOTHING`` is now an ``enum.Enum`` variant.
    """
    NOTHING = enum.auto()

    def __repr__(self):
        return 'NOTHING'

    def __bool__(self):
        return False
NOTHING = _Nothing.NOTHING
'\nSentinel to indicate the lack of a value when `None` is ambiguous.\n'

class _CacheHashWrapper(int):
    """
    An integer subclass that pickles / copies as None

    This is used for non-slots classes with ``cache_hash=True``, to avoid
    serializing a potentially (even likely) invalid hash value. Since `None`
    is the default value for uncalculated hashes, whenever this is copied,
    the copy's value for the hash should automatically reset.

    See GH #613 for more details.
    """

    def __reduce__(self, _none_constructor=type(None), _args=()):
        return (_none_constructor, _args)

def attrib(default=NOTHING, validator=None, repr=True, cmp=None, hash=None, init=True, metadata=None, type=None, converter=None, factory=None, kw_only=False, eq=None, order=None, on_setattr=None, alias=None):
    """
    Create a new field / attribute on a class.

    Identical to `attrs.field`, except it's not keyword-only.

    Consider using `attrs.field` in new code (``attr.ib`` will *never* go away,
    though).

    ..  warning::

        Does **nothing** unless the class is also decorated with
        `attr.s` (or similar)!


    .. versionadded:: 15.2.0 *convert*
    .. versionadded:: 16.3.0 *metadata*
    .. versionchanged:: 17.1.0 *validator* can be a ``list`` now.
    .. versionchanged:: 17.1.0
       *hash* is `None` and therefore mirrors *eq* by default.
    .. versionadded:: 17.3.0 *type*
    .. deprecated:: 17.4.0 *convert*
    .. versionadded:: 17.4.0
       *converter* as a replacement for the deprecated *convert* to achieve
       consistency with other noun-based arguments.
    .. versionadded:: 18.1.0
       ``factory=f`` is syntactic sugar for ``default=attr.Factory(f)``.
    .. versionadded:: 18.2.0 *kw_only*
    .. versionchanged:: 19.2.0 *convert* keyword argument removed.
    .. versionchanged:: 19.2.0 *repr* also accepts a custom callable.
    .. deprecated:: 19.2.0 *cmp* Removal on or after 2021-06-01.
    .. versionadded:: 19.2.0 *eq* and *order*
    .. versionadded:: 20.1.0 *on_setattr*
    .. versionchanged:: 20.3.0 *kw_only* backported to Python 2
    .. versionchanged:: 21.1.0
       *eq*, *order*, and *cmp* also accept a custom callable
    .. versionchanged:: 21.1.0 *cmp* undeprecated
    .. versionadded:: 22.2.0 *alias*
    """
    if factory is not None:
        default = Factory(factory)

    if cmp is not None and (eq is not None or order is not None):
        raise ValueError("cmp and eq/order are mutually exclusive.")

    if cmp is not None:
        eq = order = cmp

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
        eq_key=None,
        order=order,
        order_key=None,
        on_setattr=on_setattr,
        alias=alias,
    )

def _compile_and_eval(script, globs, locs=None, filename=''):
    """
    Evaluate the script with the given global (globs) and local (locs)
    variables.
    """
    if locs is None:
        locs = {}
    
    code = compile(script, filename, 'exec')
    eval(code, globs, locs)
    
    return locs

def _make_method(name, script, filename, globs, locals=None):
    """
    Create the method with the script given and return the method object.
    """
    locs = _compile_and_eval(script, globs, locals, filename)
    return locs[name]

def _make_attr_tuple_class(cls_name, attr_names):
    """
    Create a tuple subclass to hold `Attribute`s for an `attrs` class.

    The subclass is a bare tuple with properties for names.

    class MyClassAttributes(tuple):
        __slots__ = ()
        x = property(itemgetter(0))
    """
    pass
_Attributes = _make_attr_tuple_class('_Attributes', ['attrs', 'base_attrs', 'base_attrs_map'])

def _is_class_var(annot):
    """
    Check whether *annot* is a typing.ClassVar.

    The string comparison hack is used to avoid evaluating all string
    annotations which would put attrs-based classes at a performance
    disadvantage compared to plain old classes.
    """
    pass

def _has_own_attribute(cls, attrib_name):
    """
    Check whether *cls* defines *attrib_name* (and doesn't just inherit it).
    """
    pass

def _collect_base_attrs(cls, taken_attr_names):
    """
    Collect attr.ibs from base classes of *cls*, except *taken_attr_names*.
    """
    pass

def _collect_base_attrs_broken(cls, taken_attr_names):
    """
    Collect attr.ibs from base classes of *cls*, except *taken_attr_names*.

    N.B. *taken_attr_names* will be mutated.

    Adhere to the old incorrect behavior.

    Notably it collects from the front and considers inherited attributes which
    leads to the buggy behavior reported in #428.
    """
    pass

def _transform_attrs(cls, these, auto_attribs, kw_only, collect_by_mro, field_transformer):
    """
    Transform all `_CountingAttr`s on a class into `Attribute`s.

    If *these* is passed, use that and don't look for them on the class.

    If *collect_by_mro* is True, collect them in the correct MRO order,
    otherwise use the old -- incorrect -- order.  See #428.

    Return an `_Attributes`.
    """
    pass

def _frozen_setattrs(self, name, value):
    """
    Attached to frozen classes as __setattr__.
    """
    pass

def _frozen_delattrs(self, name):
    """
    Attached to frozen classes as __delattr__.
    """
    pass

class _ClassBuilder:
    """
    Iteratively build *one* class.
    """
    __slots__ = ('_attr_names', '_attrs', '_base_attr_map', '_base_names', '_cache_hash', '_cls', '_cls_dict', '_delete_attribs', '_frozen', '_has_pre_init', '_pre_init_has_args', '_has_post_init', '_is_exc', '_on_setattr', '_slots', '_weakref_slot', '_wrote_own_setattr', '_has_custom_setattr')

    def __init__(self, cls, these, slots, frozen, weakref_slot, getstate_setstate, auto_attribs, kw_only, cache_hash, is_exc, collect_by_mro, on_setattr, has_custom_setattr, field_transformer):
        attrs, base_attrs, base_map = _transform_attrs(cls, these, auto_attribs, kw_only, collect_by_mro, field_transformer)
        self._cls = cls
        self._cls_dict = dict(cls.__dict__) if slots else {}
        self._attrs = attrs
        self._base_names = {a.name for a in base_attrs}
        self._base_attr_map = base_map
        self._attr_names = tuple((a.name for a in attrs))
        self._slots = slots
        self._frozen = frozen
        self._weakref_slot = weakref_slot
        self._cache_hash = cache_hash
        self._has_pre_init = bool(getattr(cls, '__attrs_pre_init__', False))
        self._pre_init_has_args = False
        if self._has_pre_init:
            pre_init_func = cls.__attrs_pre_init__
            pre_init_signature = inspect.signature(pre_init_func)
            self._pre_init_has_args = len(pre_init_signature.parameters) > 1
        self._has_post_init = bool(getattr(cls, '__attrs_post_init__', False))
        self._delete_attribs = not bool(these)
        self._is_exc = is_exc
        self._on_setattr = on_setattr
        self._has_custom_setattr = has_custom_setattr
        self._wrote_own_setattr = False
        self._cls_dict['__attrs_attrs__'] = self._attrs
        if frozen:
            self._cls_dict['__setattr__'] = _frozen_setattrs
            self._cls_dict['__delattr__'] = _frozen_delattrs
            self._wrote_own_setattr = True
        elif on_setattr in (_DEFAULT_ON_SETATTR, setters.validate, setters.convert):
            has_validator = has_converter = False
            for a in attrs:
                if a.validator is not None:
                    has_validator = True
                if a.converter is not None:
                    has_converter = True
                if has_validator and has_converter:
                    break
            if on_setattr == _DEFAULT_ON_SETATTR and (not (has_validator or has_converter)) or (on_setattr == setters.validate and (not has_validator)) or (on_setattr == setters.convert and (not has_converter)):
                self._on_setattr = None
        if getstate_setstate:
            self._cls_dict['__getstate__'], self._cls_dict['__setstate__'] = self._make_getstate_setstate()

    def __repr__(self):
        return f'<_ClassBuilder(cls={self._cls.__name__})>'

    def build_class(self):
        """
        Finalize class based on the accumulated configuration.

        Builder cannot be used after calling this method.
        """
        pass

    def _patch_original_class(self):
        """
        Apply accumulated methods and return the class.
        """
        pass

    def _create_slots_class(self):
        """
        Build and return a new class with a `__slots__` attribute.
        """
        pass

    def _make_getstate_setstate(self):
        """
        Create custom __setstate__ and __getstate__ methods.
        """
        pass

    def _add_method_dunders(self, method):
        """
        Add __module__ and __qualname__ to a *method* if possible.
        """
        pass

def _determine_attrs_eq_order(cmp, eq, order, default_eq):
    """
    Validate the combination of *cmp*, *eq*, and *order*. Derive the effective
    values of eq and order.  If *eq* is None, set it to *default_eq*.
    """
    pass

def _determine_attrib_eq_order(cmp, eq, order, default_eq):
    """
    Validate the combination of *cmp*, *eq*, and *order*. Derive the effective
    values of eq and order.  If *eq* is None, set it to *default_eq*.
    """
    pass

def _determine_whether_to_implement(cls, flag, auto_detect, dunders, default=True):
    """
    Check whether we should implement a set of methods for *cls*.

    *flag* is the argument passed into @attr.s like 'init', *auto_detect* the
    same as passed into @attr.s and *dunders* is a tuple of attribute names
    whose presence signal that the user has implemented it themselves.

    Return *default* if no reason for either for or against is found.
    """
    pass

def attrs(maybe_cls=None, these=None, repr_ns=None, repr=None, cmp=None, hash=None, init=None, slots=False, frozen=False, weakref_slot=True, str=False, auto_attribs=False, kw_only=False, cache_hash=False, auto_exc=False, eq=None, order=None, auto_detect=False, collect_by_mro=False, getstate_setstate=None, on_setattr=None, field_transformer=None, match_args=True, unsafe_hash=None):
    """
    A class decorator that adds :term:`dunder methods` according to the
    specified attributes using `attr.ib` or the *these* argument.

    Consider using `attrs.define` / `attrs.frozen` in new code (``attr.s`` will
    *never* go away, though).

    Args:
        repr_ns (str):
            When using nested classes, there was no way in Python 2 to
            automatically detect that.  This argument allows to set a custom
            name for a more meaningful ``repr`` output.  This argument is
            pointless in Python 3 and is therefore deprecated.

    .. caution::
        Refer to `attrs.define` for the rest of the parameters, but note that they
        can have different defaults.

        Notably, leaving *on_setattr* as `None` will **not** add any hooks.

    .. versionadded:: 16.0.0 *slots*
    .. versionadded:: 16.1.0 *frozen*
    .. versionadded:: 16.3.0 *str*
    .. versionadded:: 16.3.0 Support for ``__attrs_post_init__``.
    .. versionchanged:: 17.1.0
       *hash* supports `None` as value which is also the default now.
    .. versionadded:: 17.3.0 *auto_attribs*
    .. versionchanged:: 18.1.0
       If *these* is passed, no attributes are deleted from the class body.
    .. versionchanged:: 18.1.0 If *these* is ordered, the order is retained.
    .. versionadded:: 18.2.0 *weakref_slot*
    .. deprecated:: 18.2.0
       ``__lt__``, ``__le__``, ``__gt__``, and ``__ge__`` now raise a
       `DeprecationWarning` if the classes compared are subclasses of
       each other. ``__eq`` and ``__ne__`` never tried to compared subclasses
       to each other.
    .. versionchanged:: 19.2.0
       ``__lt__``, ``__le__``, ``__gt__``, and ``__ge__`` now do not consider
       subclasses comparable anymore.
    .. versionadded:: 18.2.0 *kw_only*
    .. versionadded:: 18.2.0 *cache_hash*
    .. versionadded:: 19.1.0 *auto_exc*
    .. deprecated:: 19.2.0 *cmp* Removal on or after 2021-06-01.
    .. versionadded:: 19.2.0 *eq* and *order*
    .. versionadded:: 20.1.0 *auto_detect*
    .. versionadded:: 20.1.0 *collect_by_mro*
    .. versionadded:: 20.1.0 *getstate_setstate*
    .. versionadded:: 20.1.0 *on_setattr*
    .. versionadded:: 20.3.0 *field_transformer*
    .. versionchanged:: 21.1.0
       ``init=False`` injects ``__attrs_init__``
    .. versionchanged:: 21.1.0 Support for ``__attrs_pre_init__``
    .. versionchanged:: 21.1.0 *cmp* undeprecated
    .. versionadded:: 21.3.0 *match_args*
    .. versionadded:: 22.2.0
       *unsafe_hash* as an alias for *hash* (for :pep:`681` compliance).
    .. deprecated:: 24.1.0 *repr_ns*
    .. versionchanged:: 24.1.0
       Instances are not compared as tuples of attributes anymore, but using a
       big ``and`` condition. This is faster and has more correct behavior for
       uncomparable values like `math.nan`.
    .. versionadded:: 24.1.0
       If a class has an *inherited* classmethod called
       ``__attrs_init_subclass__``, it is executed after the class is created.
    .. deprecated:: 24.1.0 *hash* is deprecated in favor of *unsafe_hash*.
    """
    pass
_attrs = attrs
'\nInternal alias so we can use it in functions that take an argument called\n*attrs*.\n'

def _has_frozen_base_class(cls):
    """
    Check whether *cls* has a frozen ancestor by looking at its
    __setattr__.
    """
    pass

def _generate_unique_filename(cls, func_name):
    """
    Create a "filename" suitable for a function being generated.
    """
    pass

def _add_hash(cls, attrs):
    """
    Add a hash method to *cls*.
    """
    pass

def _make_ne():
    """
    Create __ne__ method.
    """
    pass

def _make_eq(cls, attrs):
    """
    Create __eq__ method for *cls* with *attrs*.
    """
    pass

def _make_order(cls, attrs):
    """
    Create ordering methods for *cls* with *attrs*.
    """
    pass

def _add_eq(cls, attrs=None):
    """
    Add equality methods to *cls* with *attrs*.
    """
    pass

def _add_repr(cls, ns=None, attrs=None):
    """
    Add a repr method to *cls*.
    """
    pass

def fields(cls):
    """
    Return the tuple of *attrs* attributes for a class.

    The tuple also allows accessing the fields by their names (see below for
    examples).

    Args:
        cls (type): Class to introspect.

    Raises:
        TypeError: If *cls* is not a class.

        attrs.exceptions.NotAnAttrsClassError:
            If *cls* is not an *attrs* class.

    Returns:
        tuple (with name accessors) of `attrs.Attribute`

    .. versionchanged:: 16.2.0 Returned tuple allows accessing the fields
       by name.
    .. versionchanged:: 23.1.0 Add support for generic classes.
    """
    pass

def fields_dict(cls):
    """
    Return an ordered dictionary of *attrs* attributes for a class, whose keys
    are the attribute names.

    Args:
        cls (type): Class to introspect.

    Raises:
        TypeError: If *cls* is not a class.

        attrs.exceptions.NotAnAttrsClassError:
            If *cls* is not an *attrs* class.

    Returns:
        dict[str, attrs.Attribute]: Dict of attribute name to definition

    .. versionadded:: 18.1.0
    """
    pass

def validate(inst):
    """
    Validate all attributes on *inst* that have a validator.

    Leaves all exceptions through.

    Args:
        inst: Instance of a class with *attrs* attributes.
    """
    pass

def _is_slot_attr(a_name, base_attr_map):
    """
    Check if the attribute name comes from a slot class.
    """
    pass

def _setattr(attr_name: str, value_var: str, has_on_setattr: bool) -> str:
    """
    Use the cached object.setattr to set *attr_name* to *value_var*.
    """
    pass

def _setattr_with_converter(attr_name: str, value_var: str, has_on_setattr: bool, converter: Converter) -> str:
    """
    Use the cached object.setattr to set *attr_name* to *value_var*, but run
    its converter first.
    """
    pass

def _assign(attr_name: str, value: str, has_on_setattr: bool) -> str:
    """
    Unless *attr_name* has an on_setattr hook, use normal assignment. Otherwise
    relegate to _setattr.
    """
    pass

def _assign_with_converter(attr_name: str, value_var: str, has_on_setattr: bool, converter: Converter) -> str:
    """
    Unless *attr_name* has an on_setattr hook, use normal assignment after
    conversion. Otherwise relegate to _setattr_with_converter.
    """
    pass

def _determine_setters(frozen: bool, slots: bool, base_attr_map: dict[str, type]):
    """
    Determine the correct setter functions based on whether a class is frozen
    and/or slotted.
    """
    pass

def _attrs_to_init_script(attrs: list[Attribute], is_frozen: bool, is_slotted: bool, call_pre_init: bool, pre_init_has_args: bool, call_post_init: bool, does_cache_hash: bool, base_attr_map: dict[str, type], is_exc: bool, needs_cached_setattr: bool, has_cls_on_setattr: bool, method_name: str) -> tuple[str, dict, dict]:
    """
    Return a script of an initializer for *attrs*, a dict of globals, and
    annotations for the initializer.

    The globals are required by the generated script.
    """
    pass

def _default_init_alias_for(name: str) -> str:
    """
    The default __init__ parameter name for a field.

    This performs private-name adjustment via leading-unscore stripping,
    and is the default value of Attribute.alias if not provided.
    """
    pass

class Attribute:
    """
    *Read-only* representation of an attribute.

    .. warning::

       You should never instantiate this class yourself.

    The class has *all* arguments of `attr.ib` (except for ``factory`` which is
    only syntactic sugar for ``default=Factory(...)`` plus the following:

    - ``name`` (`str`): The name of the attribute.
    - ``alias`` (`str`): The __init__ parameter name of the attribute, after
      any explicit overrides and default private-attribute-name handling.
    - ``inherited`` (`bool`): Whether or not that attribute has been inherited
      from a base class.
    - ``eq_key`` and ``order_key`` (`typing.Callable` or `None`): The
      callables that are used for comparing and ordering objects by this
      attribute, respectively. These are set by passing a callable to
      `attr.ib`'s ``eq``, ``order``, or ``cmp`` arguments. See also
      :ref:`comparison customization <custom-comparison>`.

    Instances of this class are frequently used for introspection purposes
    like:

    - `fields` returns a tuple of them.
    - Validators get them passed as the first argument.
    - The :ref:`field transformer <transform-fields>` hook receives a list of
      them.
    - The ``alias`` property exposes the __init__ parameter name of the field,
      with any overrides and default private-attribute handling applied.


    .. versionadded:: 20.1.0 *inherited*
    .. versionadded:: 20.1.0 *on_setattr*
    .. versionchanged:: 20.2.0 *inherited* is not taken into account for
        equality checks and hashing anymore.
    .. versionadded:: 21.1.0 *eq_key* and *order_key*
    .. versionadded:: 22.2.0 *alias*

    For the full version history of the fields, see `attr.ib`.
    """
    __slots__ = ('name', 'default', 'validator', 'repr', 'eq', 'eq_key', 'order', 'order_key', 'hash', 'init', 'metadata', 'type', 'converter', 'kw_only', 'inherited', 'on_setattr', 'alias')

    def __init__(self, name, default, validator, repr, cmp, hash, init, inherited, metadata=None, type=None, converter=None, kw_only=False, eq=None, eq_key=None, order=None, order_key=None, on_setattr=None, alias=None):
        eq, eq_key, order, order_key = _determine_attrib_eq_order(cmp, eq_key or eq, order_key or order, True)
        bound_setattr = _OBJ_SETATTR.__get__(self)
        bound_setattr('name', name)
        bound_setattr('default', default)
        bound_setattr('validator', validator)
        bound_setattr('repr', repr)
        bound_setattr('eq', eq)
        bound_setattr('eq_key', eq_key)
        bound_setattr('order', order)
        bound_setattr('order_key', order_key)
        bound_setattr('hash', hash)
        bound_setattr('init', init)
        bound_setattr('converter', converter)
        bound_setattr('metadata', types.MappingProxyType(dict(metadata)) if metadata else _EMPTY_METADATA_SINGLETON)
        bound_setattr('type', type)
        bound_setattr('kw_only', kw_only)
        bound_setattr('inherited', inherited)
        bound_setattr('on_setattr', on_setattr)
        bound_setattr('alias', alias)

    def __setattr__(self, name, value):
        raise FrozenInstanceError()

    def evolve(self, **changes):
        """
        Copy *self* and apply *changes*.

        This works similarly to `attrs.evolve` but that function does not work
        with {class}`Attribute`.

        It is mainly meant to be used for `transform-fields`.

        .. versionadded:: 20.3.0
        """
        pass

    def __getstate__(self):
        """
        Play nice with pickle.
        """
        return tuple((getattr(self, name) if name != 'metadata' else dict(self.metadata) for name in self.__slots__))

    def __setstate__(self, state):
        """
        Play nice with pickle.
        """
        self._setattrs(zip(self.__slots__, state))
_a = [Attribute(name=name, default=NOTHING, validator=None, repr=True, cmp=None, eq=True, order=False, hash=name != 'metadata', init=True, inherited=False, alias=_default_init_alias_for(name)) for name in Attribute.__slots__]
Attribute = _add_hash(_add_eq(_add_repr(Attribute, attrs=_a), attrs=[a for a in _a if a.name != 'inherited']), attrs=[a for a in _a if a.hash and a.name != 'inherited'])

class _CountingAttr:
    """
    Intermediate representation of attributes that uses a counter to preserve
    the order in which the attributes have been defined.

    *Internal* data structure of the attrs library.  Running into is most
    likely the result of a bug like a forgotten `@attr.s` decorator.
    """
    __slots__ = ('counter', '_default', 'repr', 'eq', 'eq_key', 'order', 'order_key', 'hash', 'init', 'metadata', '_validator', 'converter', 'type', 'kw_only', 'on_setattr', 'alias')
    __attrs_attrs__ = (*tuple((Attribute(name=name, alias=_default_init_alias_for(name), default=NOTHING, validator=None, repr=True, cmp=None, hash=True, init=True, kw_only=False, eq=True, eq_key=None, order=False, order_key=None, inherited=False, on_setattr=None) for name in ('counter', '_default', 'repr', 'eq', 'order', 'hash', 'init', 'on_setattr', 'alias'))), Attribute(name='metadata', alias='metadata', default=None, validator=None, repr=True, cmp=None, hash=False, init=True, kw_only=False, eq=True, eq_key=None, order=False, order_key=None, inherited=False, on_setattr=None))
    cls_counter = 0

    def __init__(self, default, validator, repr, cmp, hash, init, converter, metadata, type, kw_only, eq, eq_key, order, order_key, on_setattr, alias):
        _CountingAttr.cls_counter += 1
        self.counter = _CountingAttr.cls_counter
        self._default = default
        self._validator = validator
        self.converter = converter
        self.repr = repr
        self.eq = eq
        self.eq_key = eq_key
        self.order = order
        self.order_key = order_key
        self.hash = hash
        self.init = init
        self.metadata = metadata
        self.type = type
        self.kw_only = kw_only
        self.on_setattr = on_setattr
        self.alias = alias

    def validator(self, meth):
        """
        Decorator that adds *meth* to the list of validators.

        Returns *meth* unchanged.

        .. versionadded:: 17.1.0
        """
        pass

    def default(self, meth):
        """
        Decorator that allows to set the default for an attribute.

        Returns *meth* unchanged.

        Raises:
            DefaultAlreadySetError: If default has been set before.

        .. versionadded:: 17.1.0
        """
        pass
_CountingAttr = _add_eq(_add_repr(_CountingAttr))

class Factory:
    """
    Stores a factory callable.

    If passed as the default value to `attrs.field`, the factory is used to
    generate a new value.

    Args:
        factory (typing.Callable):
            A callable that takes either none or exactly one mandatory
            positional argument depending on *takes_self*.

        takes_self (bool):
            Pass the partially initialized instance that is being initialized
            as a positional argument.

    .. versionadded:: 17.1.0  *takes_self*
    """
    __slots__ = ('factory', 'takes_self')

    def __init__(self, factory, takes_self=False):
        self.factory = factory
        self.takes_self = takes_self

    def __getstate__(self):
        """
        Play nice with pickle.
        """
        return tuple((getattr(self, name) for name in self.__slots__))

    def __setstate__(self, state):
        """
        Play nice with pickle.
        """
        for name, value in zip(self.__slots__, state):
            setattr(self, name, value)
_f = [Attribute(name=name, default=NOTHING, validator=None, repr=True, cmp=None, eq=True, order=False, hash=True, init=True, inherited=False) for name in Factory.__slots__]
Factory = _add_hash(_add_eq(_add_repr(Factory, attrs=_f), attrs=_f), attrs=_f)

class Converter:
    """
    Stores a converter callable.

    Allows for the wrapped converter to take additional arguments. The
    arguments are passed in the order they are documented.

    Args:
        converter (Callable): A callable that converts the passed value.

        takes_self (bool):
            Pass the partially initialized instance that is being initialized
            as a positional argument. (default: `False`)

        takes_field (bool):
            Pass the field definition (an :class:`Attribute`) into the
            converter as a positional argument. (default: `False`)

    .. versionadded:: 24.1.0
    """
    __slots__ = ('converter', 'takes_self', 'takes_field', '_first_param_type', '_global_name', '__call__')

    def __init__(self, converter, *, takes_self=False, takes_field=False):
        self.converter = converter
        self.takes_self = takes_self
        self.takes_field = takes_field
        ex = _AnnotationExtractor(converter)
        self._first_param_type = ex.get_first_param_type()
        if not (self.takes_self or self.takes_field):
            self.__call__ = lambda value, _, __: self.converter(value)
        elif self.takes_self and (not self.takes_field):
            self.__call__ = lambda value, instance, __: self.converter(value, instance)
        elif not self.takes_self and self.takes_field:
            self.__call__ = lambda value, __, field: self.converter(value, field)
        else:
            self.__call__ = lambda value, instance, field: self.converter(value, instance, field)
        rt = ex.get_return_type()
        if rt is not None:
            self.__call__.__annotations__['return'] = rt

    @staticmethod
    def _get_global_name(attr_name: str) -> str:
        """
        Return the name that a converter for an attribute name *attr_name*
        would have.
        """
        pass

    def _fmt_converter_call(self, attr_name: str, value_var: str) -> str:
        """
        Return a string that calls the converter for an attribute name
        *attr_name* and the value in variable named *value_var* according to
        `self.takes_self` and `self.takes_field`.
        """
        pass

    def __getstate__(self):
        """
        Return a dict containing only converter and takes_self -- the rest gets
        computed when loading.
        """
        return {'converter': self.converter, 'takes_self': self.takes_self, 'takes_field': self.takes_field}

    def __setstate__(self, state):
        """
        Load instance from state.
        """
        self.__init__(**state)
_f = [Attribute(name=name, default=NOTHING, validator=None, repr=True, cmp=None, eq=True, order=False, hash=True, init=True, inherited=False) for name in ('converter', 'takes_self', 'takes_field')]
Converter = _add_hash(_add_eq(_add_repr(Converter, attrs=_f), attrs=_f), attrs=_f)

def make_class(name, attrs, bases=(object,), class_body=None, **attributes_arguments):
    """
    A quick way to create a new class called *name* with *attrs*.

    Args:
        name (str): The name for the new class.

        attrs( list | dict):
            A list of names or a dictionary of mappings of names to `attr.ib`\\
            s / `attrs.field`\\ s.

            The order is deduced from the order of the names or attributes
            inside *attrs*.  Otherwise the order of the definition of the
            attributes is used.

        bases (tuple[type, ...]): Classes that the new class will subclass.

        class_body (dict):
            An optional dictionary of class attributes for the new class.

        attributes_arguments: Passed unmodified to `attr.s`.

    Returns:
        type: A new class with *attrs*.

    .. versionadded:: 17.1.0 *bases*
    .. versionchanged:: 18.1.0 If *attrs* is ordered, the order is retained.
    .. versionchanged:: 23.2.0 *class_body*
    """
    pass

@attrs(slots=True, unsafe_hash=True)
class _AndValidator:
    """
    Compose many validators to a single one.
    """
    _validators = attrib()

    def __call__(self, inst, attr, value):
        for v in self._validators:
            v(inst, attr, value)

def and_(*validators):
    """
    A validator that composes multiple validators into one.

    When called on a value, it runs all wrapped validators.

    Args:
        validators (~collections.abc.Iterable[typing.Callable]):
            Arbitrary number of validators.

    .. versionadded:: 17.1.0
    """
    pass

def pipe(*converters):
    """
    A converter that composes multiple converters into one.

    When called on a value, it runs all wrapped converters, returning the
    *last* value.

    Type annotations will be inferred from the wrapped converters', if they
    have any.

        converters (~collections.abc.Iterable[typing.Callable]):
            Arbitrary number of converters.

    .. versionadded:: 20.1.0
    """
    pass
