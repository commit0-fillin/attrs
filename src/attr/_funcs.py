import copy
from ._compat import PY_3_9_PLUS, get_generic_base
from ._make import _OBJ_SETATTR, NOTHING, fields
from .exceptions import AttrsAttributeNotFoundError

def asdict(inst, recurse=True, filter=None, dict_factory=dict, retain_collection_types=False, value_serializer=None):
    """
    Return the *attrs* attribute values of *inst* as a dict.

    Optionally recurse into other *attrs*-decorated classes.

    Args:
        inst: Instance of an *attrs*-decorated class.

        recurse (bool): Recurse into classes that are also *attrs*-decorated.

        filter (~typing.Callable):
            A callable whose return code determines whether an attribute or
            element is included (`True`) or dropped (`False`).  Is called with
            the `attrs.Attribute` as the first argument and the value as the
            second argument.

        dict_factory (~typing.Callable):
            A callable to produce dictionaries from.  For example, to produce
            ordered dictionaries instead of normal Python dictionaries, pass in
            ``collections.OrderedDict``.

        retain_collection_types (bool):
            Do not convert to `list` when encountering an attribute whose type
            is `tuple` or `set`.  Only meaningful if *recurse* is `True`.

        value_serializer (typing.Callable | None):
            A hook that is called for every attribute or dict key/value.  It
            receives the current instance, field and value and must return the
            (updated) value.  The hook is run *after* the optional *filter* has
            been applied.

    Returns:
        Return type of *dict_factory*.

    Raises:
        attrs.exceptions.NotAnAttrsClassError:
            If *cls* is not an *attrs* class.

    ..  versionadded:: 16.0.0 *dict_factory*
    ..  versionadded:: 16.1.0 *retain_collection_types*
    ..  versionadded:: 20.3.0 *value_serializer*
    ..  versionadded:: 21.3.0
        If a dict has a collection for a key, it is serialized as a tuple.
    """
    attrs = fields(inst.__class__)
    rv = dict_factory()
    for a in attrs:
        v = getattr(inst, a.name)
        if filter is not None and not filter(a, v):
            continue
        if value_serializer is not None:
            v = value_serializer(inst, a, v)
        if recurse:
            if has(v.__class__):
                v = asdict(v, recurse=True, filter=filter, dict_factory=dict_factory,
                           retain_collection_types=retain_collection_types,
                           value_serializer=value_serializer)
            elif isinstance(v, (tuple, list, set, frozenset)):
                v = _asdict_anything(v, recurse, filter, dict_factory,
                                     retain_collection_types, value_serializer)
        rv[a.name] = v
    return rv

def _asdict_anything(val, recurse, filter, dict_factory, retain_collection_types, value_serializer):
    """
    ``asdict`` only works on attrs instances, this works on anything.
    """
    if isinstance(val, dict):
        return dict_factory((
            _asdict_anything(k, recurse, filter, dict_factory, retain_collection_types, value_serializer),
            _asdict_anything(v, recurse, filter, dict_factory, retain_collection_types, value_serializer)
        ) for k, v in val.items())
    elif isinstance(val, (tuple, list, set, frozenset)):
        if retain_collection_types is True:
            cf = type(val)
        else:
            cf = list

        return cf([
            _asdict_anything(i, recurse, filter, dict_factory, retain_collection_types, value_serializer)
            for i in val
        ])
    elif has(val.__class__):
        return asdict(val, recurse=recurse, filter=filter, dict_factory=dict_factory,
                      retain_collection_types=retain_collection_types,
                      value_serializer=value_serializer)
    else:
        return val

def astuple(inst, recurse=True, filter=None, tuple_factory=tuple, retain_collection_types=False):
    """
    Return the *attrs* attribute values of *inst* as a tuple.

    Optionally recurse into other *attrs*-decorated classes.

    Args:
        inst: Instance of an *attrs*-decorated class.

        recurse (bool):
            Recurse into classes that are also *attrs*-decorated.

        filter (~typing.Callable):
            A callable whose return code determines whether an attribute or
            element is included (`True`) or dropped (`False`).  Is called with
            the `attrs.Attribute` as the first argument and the value as the
            second argument.

        tuple_factory (~typing.Callable):
            A callable to produce tuples from. For example, to produce lists
            instead of tuples.

        retain_collection_types (bool):
            Do not convert to `list` or `dict` when encountering an attribute
            which type is `tuple`, `dict` or `set`. Only meaningful if
            *recurse* is `True`.

    Returns:
        Return type of *tuple_factory*

    Raises:
        attrs.exceptions.NotAnAttrsClassError:
            If *cls* is not an *attrs* class.

    ..  versionadded:: 16.2.0
    """
    attrs = fields(inst.__class__)
    rv = []
    for a in attrs:
        v = getattr(inst, a.name)
        if filter is not None and not filter(a, v):
            continue
        if recurse:
            if has(v.__class__):
                v = astuple(v, recurse=True, filter=filter, tuple_factory=tuple_factory,
                            retain_collection_types=retain_collection_types)
            elif isinstance(v, (tuple, list, set, frozenset, dict)):
                v = _astuple_anything(v, recurse, filter, tuple_factory, retain_collection_types)
        rv.append(v)
    
    return tuple_factory(rv)

def has(cls):
    """
    Check whether *cls* is a class with *attrs* attributes.

    Args:
        cls (type): Class to introspect.

    Raises:
        TypeError: If *cls* is not a class.

    Returns:
        bool:
    """
    if not isinstance(cls, type):
        raise TypeError("has() requires a class")
    return hasattr(cls, "__attrs_attrs__")

def assoc(inst, **changes):
    """
    Copy *inst* and apply *changes*.

    This is different from `evolve` that applies the changes to the arguments
    that create the new instance.

    `evolve`'s behavior is preferable, but there are `edge cases`_ where it
    doesn't work. Therefore `assoc` is deprecated, but will not be removed.

    .. _`edge cases`: https://github.com/python-attrs/attrs/issues/251

    Args:
        inst: Instance of a class with *attrs* attributes.

        changes: Keyword changes in the new copy.

    Returns:
        A copy of inst with *changes* incorporated.

    Raises:
        attrs.exceptions.AttrsAttributeNotFoundError:
            If *attr_name* couldn't be found on *cls*.

        attrs.exceptions.NotAnAttrsClassError:
            If *cls* is not an *attrs* class.

    ..  deprecated:: 17.1.0
        Use `attrs.evolve` instead if you can. This function will not be
        removed du to the slightly different approach compared to
        `attrs.evolve`, though.
    """
    import warnings
    warnings.warn("assoc() is deprecated, use evolve() instead.", DeprecationWarning, stacklevel=2)

    new_inst = copy.copy(inst)
    attrs = fields(inst.__class__)
    for attr_name, new_value in changes.items():
        if not any(attr.name == attr_name for attr in attrs):
            raise AttrsAttributeNotFoundError(f"Attribute {attr_name} not found")
        setattr(new_inst, attr_name, new_value)
    return new_inst

def evolve(*args, **changes):
    """
    Create a new instance, based on the first positional argument with
    *changes* applied.

    Args:

        inst:
            Instance of a class with *attrs* attributes. *inst* must be passed
            as a positional argument.

        changes:
            Keyword changes in the new copy.

    Returns:
        A copy of inst with *changes* incorporated.

    Raises:
        TypeError:
            If *attr_name* couldn't be found in the class ``__init__``.

        attrs.exceptions.NotAnAttrsClassError:
            If *cls* is not an *attrs* class.

    .. versionadded:: 17.1.0
    .. deprecated:: 23.1.0
       It is now deprecated to pass the instance using the keyword argument
       *inst*. It will raise a warning until at least April 2024, after which
       it will become an error. Always pass the instance as a positional
       argument.
    .. versionchanged:: 24.1.0
       *inst* can't be passed as a keyword argument anymore.
    """
    if not args:
        raise TypeError("evolve() missing 1 required positional argument: 'inst'")
    inst = args[0]
    if not has(inst.__class__):
        raise NotAnAttrsClassError(f"{inst.__class__.__name__} is not an attrs-decorated class.")
    
    new_values = {}
    for attr in fields(inst.__class__):
        if attr.init:
            try:
                new_values[attr.name] = changes.pop(attr.name, getattr(inst, attr.name))
            except AttributeError:
                raise TypeError(f"Attribute {attr.name} doesn't exist or is not initializable.")
    
    if changes:
        raise TypeError(f"got an unexpected keyword argument: {next(iter(changes))!r}")
    
    return inst.__class__(**new_values)

def resolve_types(cls, globalns=None, localns=None, attribs=None, include_extras=True):
    """
    Resolve any strings and forward annotations in type annotations.

    This is only required if you need concrete types in :class:`Attribute`'s
    *type* field. In other words, you don't need to resolve your types if you
    only use them for static type checking.

    With no arguments, names will be looked up in the module in which the class
    was created. If this is not what you want, for example, if the name only
    exists inside a method, you may pass *globalns* or *localns* to specify
    other dictionaries in which to look up these names. See the docs of
    `typing.get_type_hints` for more details.

    Args:
        cls (type): Class to resolve.

        globalns (dict | None): Dictionary containing global variables.

        localns (dict | None): Dictionary containing local variables.

        attribs (list | None):
            List of attribs for the given class. This is necessary when calling
            from inside a ``field_transformer`` since *cls* is not an *attrs*
            class yet.

        include_extras (bool):
            Resolve more accurately, if possible. Pass ``include_extras`` to
            ``typing.get_hints``, if supported by the typing module. On
            supported Python versions (3.9+), this resolves the types more
            accurately.

    Raises:
        TypeError: If *cls* is not a class.

        attrs.exceptions.NotAnAttrsClassError:
            If *cls* is not an *attrs* class and you didn't pass any attribs.

        NameError: If types cannot be resolved because of missing variables.

    Returns:
        *cls* so you can use this function also as a class decorator. Please
        note that you have to apply it **after** `attrs.define`. That means the
        decorator has to come in the line **before** `attrs.define`.

    ..  versionadded:: 20.1.0
    ..  versionadded:: 21.1.0 *attribs*
    ..  versionadded:: 23.1.0 *include_extras*
    """
    if not isinstance(cls, type):
        raise TypeError("resolve_types() requires a class.")

    if attribs is None:
        if not has(cls):
            raise NotAnAttrsClassError(f"{cls.__name__} is not an attrs-decorated class.")
        attribs = fields(cls)

    hints = typing.get_type_hints(cls, globalns=globalns, localns=localns, include_extras=include_extras)

    for a in attribs:
        if a.name in hints:
            a.type = hints[a.name]

    return cls
