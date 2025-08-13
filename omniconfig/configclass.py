# -*- coding: utf-8 -*-
"""ConfigMeta class for config dataclasses."""

import re
from dataclasses import _FIELD, _FIELD_INITVAR, _FIELDS, MISSING, Field
from dataclasses import fields as _get_fields
from enum import Enum
from inspect import signature
from typing import Any, Callable, Type, TypeVar

import docstring_parser

from .args import Arguments, _format_prefix_to_flag
from .utils import (
    CONFIG_SUFFIXES,
    BooleanOptionalAction,
    dump_toml,
    dump_yaml,
    format_scope_and_prefix,
    parse_field_type,
    remove_suffix,
)

__all__ = [
    "configclass",
    "get_arguments",
    "from_dict",
    "ARGPARSE_ARGS",
    "ARGPARSE_KWARGS",
    "IGNORE_FIELD",
    "ADD_PREFIX_BOOL_FIELDS",
    "COLLECT_PREFIX_BOOL_FIELDS",
]


FIELD_DOCS = "__field_docs__"
FIELD_DOC = "__doc__"
ARGPARSE_ARGS = "_argparse_args_"
ARGPARSE_KWARGS = "_argparse_kwargs_"


_T = TypeVar("_T")


def configclass(cls: Type[_T], /) -> Type[_T]:
    """Decorator for config classes.

    Args:
        cls (Type[_T]): Class to decorate.

    Returns:
        Type[_T]: Decorated class with `get_arguments` and `from_dict` classmethods,
                  and `formatted_str` method.
    """  # noqa: D401
    _set_field_docs(cls)
    if not hasattr(cls, "get_arguments"):
        setattr(cls, "get_arguments", classmethod(get_arguments))  # noqa: B010
    if not hasattr(cls, "from_dict"):
        setattr(cls, "from_dict", classmethod(from_dict))  # noqa: B010
    if not hasattr(cls, "formatted_str"):
        setattr(cls, "formatted_str", formatted_str)  # noqa: B010
    if not hasattr(cls, "dump"):
        setattr(cls, "dump", dump)  # noqa: B010
    return cls


def _set_field_docs(cls) -> None:
    """Set field docs from the docstring of a config dataclass."""
    doc: str = cls.__doc__
    fields = getattr(cls, _FIELDS)  # include both fields and initvars
    field_docs: dict[str, str] = getattr(cls, FIELD_DOCS, {})
    if doc:
        parsed_doc = docstring_parser.parse(doc)
        remove_default_regex = re.compile(r"\s*[Dd]efault(?: is | = |: | to|)\s*(.+)\.")
        # we first go through args
        initarg_docs: dict[str, str] = {}
        for param in parsed_doc.params:
            if param.args[0] == "param":
                field_name = param.arg_name
                field_doc = param.description if param.description else ""
                field_doc = remove_default_regex.sub("", field_doc).strip().replace("\n", "")
                if field_name in fields:
                    assert (
                        field_name not in initarg_docs
                    ), f"Duplicate Init Arg {field_name} in {cls.__name__} docstring"
                    initarg_docs[field_name] = field_doc
        # then we go through attributes
        attr_docs: dict[str, str] = {}
        for param in parsed_doc.params:
            if param.args[0] == "attribute":
                field_name = param.arg_name
                field_doc = param.description if param.description else ""
                field_doc = remove_default_regex.sub("", field_doc).strip().replace("\n", "")
                if field_name in fields:
                    assert field_name not in attr_docs, f"Duplicate Attribute {field_name} in {cls.__name__} docstring"
                    attr_docs[field_name] = field_doc
        # then we update the field docs
        attr_docs.update(initarg_docs)
        field_docs.update(attr_docs)
    setattr(cls, FIELD_DOCS, field_docs)


def _get_init_fields(cls) -> tuple[Field, ...]:
    return tuple(f for f in getattr(cls, _FIELDS).values() if f._field_type in (_FIELD, _FIELD_INITVAR) and f.init)


def get_arguments(  # noqa: C901
    cls: Type[_T],
    /,
    *,
    scope: str = None,
    prefix: str = None,
    overwrites: dict[str, Callable[[Arguments], None] | None] | None = None,
    **defaults,
) -> Arguments:
    """Get arguments from a config dataclass.

    Args:
        cls (Type[_T@configclass]): Config dataclass.
        prefix (str): Prefix for the arguments.
        overwrites (dict[str, Callable[[Arguments], None] | None] | None): Overwrite the arguments.
                                                                           Defaults to ``None``.
        **defaults: Default values for the arguments.

    Returns:
        Arguments: The arguments.
    """
    if overwrites is None:
        overwrites = {}
    if hasattr(cls, "update_get_arguments"):
        overwrites, defaults = cls.update_get_arguments(overwrites=overwrites, defaults=defaults)
    scope, prefix = format_scope_and_prefix(cls, scope=scope, prefix=prefix)

    # we only include init fields since they are used to construct the config
    fields = _get_init_fields(cls)
    field_docs = getattr(cls, FIELD_DOCS, {})
    parser = Arguments(scope=scope, prefix=prefix)
    for field in fields:
        if field.name in overwrites:
            fn = overwrites[field.name]
            if fn is not None:
                fn(parser)
            continue
        _dest = field.name
        _kwargs: dict[str, Any] = field.metadata.get(ARGPARSE_KWARGS, {})
        field_type, field_type_optional = parse_field_type(field.type)

        if hasattr(field_type, "get_arguments"):
            _scope = _kwargs.get("scope", _dest)
            _prefix = _kwargs.get("prefix", remove_suffix(_dest, CONFIG_SUFFIXES))
            if field_type_optional:
                if field.default is MISSING:
                    if field.default_factory is MISSING:
                        default = None
                    else:
                        default = field.default_factory()
                else:
                    default = field.default
                parser.add_argument(
                    f"--enable-{_format_prefix_to_flag(_prefix)}",
                    dest=f"enable_{_prefix}",
                    action=BooleanOptionalAction,
                    help=f"Enable {_dest}.",
                    default=default is not None,
                )
            _n = len(_prefix) + (1 if _prefix else 0)
            parser.add_arguments(
                field_type.get_arguments(
                    scope=_scope,
                    prefix=_prefix,
                    overwrites={k[_n:]: v for k, v in overwrites.items() if k.startswith(_prefix)},
                    **{k[_n:]: v for k, v in defaults.items() if k.startswith(_prefix)},
                )
            )
            continue

        # get dest from field name
        _kwargs["dest"] = _dest
        # get help description from docstring of field
        _kwargs.setdefault("help", field.metadata.get(FIELD_DOC, field_docs.get(field.name, "")))
        # get default from field type and default
        if _dest in defaults:
            _default = defaults[_dest]
        elif "default" in _kwargs:
            _default = _kwargs["default"]
        elif field.default is not MISSING:
            _default = field.default
        elif field.default_factory is not MISSING:
            _default = field.default_factory()
        elif field_type_optional:
            _default = None
        elif field_type is bool:
            _default = False
        else:
            _default = MISSING
        if _default is not MISSING:
            _kwargs["default"] = _default
        # get action from default value
        _flag = f"--{_dest.replace('_', '-') if _dest[0] != '_' else _dest}"
        if field_type is bool:
            action = _kwargs.pop("action", MISSING)
            if _default:
                assert action in (MISSING, "store_false"), (
                    f"Invalid action {action} for field {field.name} in {cls.__name__}. "
                    f"Action should be 'store_false' for default True."
                )
            else:
                assert action in (MISSING, "store_true"), (
                    f"Invalid action {action} for field {field.name} in {cls.__name__}. "
                    f"Action should be 'store_true' for default False."
                )
            _kwargs["action"] = BooleanOptionalAction
            _kwargs.pop("type", None)
        # get flag from field name
        _flags = tuple(set(field.metadata.get(ARGPARSE_ARGS, [_flag])))
        # get type from field type
        if "type" in _kwargs or field_type is bool:
            pass
        elif field_type in (str, int, float, complex):
            _kwargs["type"] = field_type
        elif issubclass(field_type, Enum):
            _kwargs["type"] = lambda x, field_type=field_type: field_type[x.split(".")[-1]]
            _kwargs["choices"] = list(field_type)
        elif isinstance(field_type, type) and hasattr(field_type, "from_str"):
            _kwargs["type"] = field_type.from_str
        else:
            if field.default_factory is not MISSING and len(signature(field.default_factory).parameters) >= 1:
                _kwargs["type"] = field.default_factory
            else:
                assert callable(field_type), (
                    f"Invalid type {field_type} for field {field.name} in {cls.__name__}. "
                    f"Type should be a callable or one of built-in types."
                )
                _kwargs["type"] = field_type
        # add to parser
        parser.add_argument(*_flags, **_kwargs)
    return parser


def from_dict(cls: Type[_T], /, parsed_args: dict[str, Any], **overwrites) -> _T:
    """Create a config dataclass from formatted parsed arguments dict.

    Args:
        cls (Type[_T@configclass]): Config dataclass type.
        parsed_args (dict[str, Any]): Formatted parsed arguments dict from `Arguments.to_dict`.
        **overwrites: Overwrite values for the config dataclass.

    Returns:
        _T@configclass: The config dataclass instance.
    """
    if hasattr(cls, "update_from_dict"):
        parsed_args, overwrites = cls.update_from_dict(parsed_args=parsed_args, overwrites=overwrites)
    fields = _get_init_fields(cls)
    kwargs = {}
    for field in fields:
        if field.name in overwrites:
            kwargs[field.name] = overwrites[field.name]
        elif field.name in parsed_args:
            field_type, field_type_optional = parse_field_type(field.type)
            if hasattr(field_type, "from_dict"):
                if field_type_optional and not parsed_args.get(f"enable_{field.name}", False):
                    kwargs[field.name] = None
                else:
                    _kwargs: dict[str, Any] = field.metadata.get(ARGPARSE_KWARGS, {})
                    _prefix = _kwargs.get("prefix", remove_suffix(field.name, CONFIG_SUFFIXES))
                    _n = len(_prefix) + (1 if _prefix else 0)
                    kwargs[field.name] = field_type.from_dict(
                        parsed_args[field.name],
                        **{k[_n:]: v for k, v in overwrites.items() if k.startswith(_prefix)},
                    )
            else:
                kwargs[field.name] = parsed_args[field.name]
    return cls(**kwargs)


def formatted_str(self: _T, /, indent: int = 2, level: int = 0) -> str:
    """Get formatted string of a config dataclass.

    Args:
        self: Config dataclass instance.
        indent (int): Indentation of the formatted string. Defaults to ``2``.
        level (int): Indentation level of the formatted string. Defaults to ``0``.

    Returns:
        str: The formatted string.
    """
    level += 1
    _ = " " * indent * level
    fields = _get_fields(self)
    s = f"{self.__class__.__name__}("
    for field in fields:
        value = getattr(self, field.name)
        if hasattr(value, "formatted_str"):
            s += f"\n{_}{field.name}={value.formatted_str(indent=indent, level=level)},"
        else:
            s += f"\n{_}{field.name}={value},"
    return s[:-1] + ")"


def _to_dump_value(value: Any) -> Any:
    if hasattr(value, "dump"):
        return value.dump()
    elif value is None:
        return None
    elif isinstance(value, (str, int, float, complex, bool)):
        return value
    elif isinstance(value, Enum):
        return value.name
    elif isinstance(value, (list, tuple)):
        return [_to_dump_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: _to_dump_value(v) for k, v in value.items()}
    return str(value)


def dump(self: _T, path: str = "") -> dict[str, Any]:
    """Dump config dict of a config dataclass.

    Args:
        self: Config dataclass instance.
        path (str): Path to dump the config dict. Defaults to ``""``.

    Returns:
        dict[str, Any]: The dict.
    """
    rst = {}
    for field in _get_init_fields(self.__class__):
        field_type, field_type_optional = parse_field_type(field.type)
        value = _to_dump_value(getattr(self, field.name))
        if field_type_optional and hasattr(field_type, "get_arguments"):
            if value is None:
                rst[f"enable_{field.name}"] = False
            else:
                rst[f"enable_{field.name}"] = True
                rst[field.name] = value
        else:
            rst[field.name] = value
    if path:
        if path.endswith(".toml"):
            dump_toml(rst, path)
        elif path.endswith(("yaml", "yml")):
            dump_yaml(rst, path)
        else:
            raise ValueError(f"Unsupported file format {path}")
    return rst


def IGNORE_FIELD(parser: Arguments) -> None:
    """Ignore a field when adding arguments to a parser."""
    pass


def ADD_PREFIX_BOOL_FIELDS(prefix: str, **defaults) -> Callable[[Arguments], None]:
    """Add boolean fields with same prefix to a parser."""
    assert prefix, "Prefix should not be empty."
    assert prefix.isidentifier(), f"Prefix {prefix} should be a valid identifier."
    prefix_ = prefix + "_"

    def fn(parser: Arguments):
        for k, v in defaults.items():
            if k.startswith(prefix_):
                k = k[len(prefix_) :]
                uk = k.replace("_", "-") if k[0] != "_" else k
                parser.add_argument(
                    f"--{prefix}-{uk}",
                    action=BooleanOptionalAction,
                    dest=f"{prefix}_{k}",
                    help=f"Whether to {prefix} {k}.",
                    default=v,
                )

    return fn


def COLLECT_PREFIX_BOOL_FIELDS(
    parsed_args: dict[str, Any], prefix: str, return_as_dict: bool = False
) -> dict[str, bool] | list[str]:
    """Get values of boolean fields with same prefix from parsed arguments."""
    assert prefix, "Prefix should not be empty."
    assert prefix.isidentifier(), f"Prefix {prefix} should be a valid identifier."
    prefix_ = prefix + "_"
    results = {k[len(prefix_) :]: v for k, v in parsed_args.items() if k.startswith(prefix_)}
    if return_as_dict:
        return results
    return [k for k, v in results.items() if v]
