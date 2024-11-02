# -*- coding: utf-8 -*-
"""Utils for omniconfig."""

import argparse
import types
import typing
from dataclasses import MISSING, InitVar
from enum import Enum

import toml
import yaml

__all__ = [
    "CONFIG_SUFFIXES",
    "parse_field_type",
    "convert_camelize_to_snake_case",
    "remove_suffix",
    "format_scope_and_prefix",
    "update_dict",
    "load_yaml",
    "dump_yaml",
    "load_toml",
    "dump_toml",
    "BooleanOptionalAction",
]


CONFIG_SUFFIXES = ("_config", "_configs", "_args", "_arguments", "_params", "_parameters", "_attrs", "_attributes")


def parse_field_type(tp: typing.Any) -> tuple[typing.Any, bool]:
    """Parse a field type.

    Args:
        tp (typing.Any): Type to parse.

    Returns:
        tuple[typing.Any, bool]: The parsed type and whether it is optional.
    """
    if isinstance(tp, InitVar):
        tp = tp.type
    if hasattr(tp, "__origin__"):
        if tp.__origin__ is typing.Union:
            ntp = tuple(arg for arg in tp.__args__ if arg is not type(None))
            return typing.Union[ntp], len(tp.__args__) != len(ntp)
        elif tp.__origin__ is typing.Optional:
            return tp.__args__[0], True
        else:
            return tp, False
    else:
        if isinstance(tp, types.UnionType):
            ntp = tuple(arg for arg in tp.__args__ if arg is not type(None))
            return typing.Union[ntp], len(tp.__args__) != len(ntp)
        else:
            return tp, False


def remove_suffix(name: str, suffixes: tuple[str]) -> str:
    """Remove suffixes from a name.

    Args:
        name: Name to remove suffixes.
        suffixes: Suffixes to remove.

    Returns:
        Name without suffixes.
    """
    if name:
        for suffix in suffixes:
            if name.endswith(suffix):
                return name[: -len(suffix)]
    return name


def convert_camelize_to_snake_case(name: str) -> str:
    """Convert a name from camel case to snake case.

    Args:
        name (str): The name to convert.

    Returns:
        str: The converted name.
    """
    return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")


def format_scope_and_prefix(cls: type, *, scope: str | None = None, prefix: str | None = None) -> tuple[str, str]:
    """Format scope and prefix from a class.

    Args:
        cls (type): The class to format.
        scope (str, optional): The scope to use. Defaults to ``None``.
        prefix (str, optional): The prefix to use. Defaults to ``None``.

    Returns:
        tuple[str, str]: The formatted scope and prefix.
    """
    cls_sname = convert_camelize_to_snake_case(cls.__name__)
    cls_cname = remove_suffix(cls_sname, CONFIG_SUFFIXES)
    if scope is None:
        scope = cls_sname
    if prefix is None:
        prefix = cls_cname
    elif prefix:
        prefix = remove_suffix(prefix, CONFIG_SUFFIXES)
        _pparts, _nparts = prefix.split("_"), cls_cname.split("_")
        # remove common part from the end
        _cparts = []
        while _pparts and _nparts and _pparts[-1] == _nparts[-1]:
            _cparts.append(_pparts.pop())
            _nparts.pop()
        prefix = "_".join(_pparts + _cparts[::-1])
    return scope, prefix


def update_dict(
    d: dict[typing.Any, typing.Any], u: dict[typing.Any, typing.Any], strict: bool = False
) -> dict[typing.Any, typing.Any]:
    """Update a dictionary recursively.

    Args:
        d (dict[typing.Any, typing.Any]): The dictionary to update.
        u (dict[typing.Any, typing.Any]): The dictionary to update from.
        strict (bool, optional): Whether to update strictly. Defaults to False.

    Returns:
        dict[typing.Any, typing.Any]: The updated dictionary.
    """
    if len(d) == 0:
        return u
    for k, v in u.items():
        if not strict or k in d:
            if isinstance(v, dict):
                d[k] = update_dict(d.get(k, {}), v)
            else:
                d[k] = v
    return d


def load_yaml(path: str) -> typing.Any:
    """Load a yaml file and return the corresponding object.

    Args:
        path (str): Path to the yaml file.

    Returns:
        typing.Any: The object loaded from the yaml file.
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(
    obj: typing.Any, /, path: str = None, str_unsupported: bool = True, ignore_aliases: bool = True, **kwargs
) -> str:
    """Dump an object to a yaml file or string.

    Args:
        obj (typing.Any): The object to dump.
        path (str): Path to the yaml file.
        str_unsupported (bool, optional): Whether to dump unsupported types as strings. Defaults to ``True``.
        ignore_aliases (bool, optional): Whether to ignore aliases. Defaults to ``True``.
        **kwargs: Additional arguments to pass to ``yaml.dump``.
    """
    kwargs.setdefault("default_flow_style", False)
    kwargs.setdefault("sort_keys", False)
    kwargs.setdefault("indent", 2)
    # dynamic create a dumper class from yaml.SafeDumper
    if str_unsupported or ignore_aliases:
        Dumper = type("Dumper", (yaml.SafeDumper,), {})
        if str_unsupported:
            Dumper.add_representer(
                None,
                lambda self, data: self.represent_scalar(
                    "tag:yaml.org,2002:str",
                    data.name if isinstance(data, Enum) else "MISSING" if data is MISSING else str(data),
                ),
            )
        if ignore_aliases:
            Dumper.ignore_aliases = lambda self, data: True
    else:
        Dumper = yaml.SafeDumper
    if path is None:
        return yaml.dump(obj, Dumper=Dumper, **kwargs)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(obj, f, Dumper=Dumper, **kwargs)


def load_toml(path: str) -> typing.Any:
    """Load a toml file and return the corresponding object.

    Args:
        path (str): Path to the toml file.

    Returns:
        typing.Any: The object loaded from the toml file.
    """
    with open(path, "r", encoding="utf-8") as f:
        return toml.load(f)


def dump_toml(obj: typing.Any, /, path: str = None) -> str:
    """Dump an object to a toml file or string.

    Args:
        obj (typing.Any): The object to dump.
        path (str): Path to the toml file.
        str_unsupported (bool, optional): Whether to dump unsupported types as strings. Defaults to ``True``.
        ignore_aliases (bool, optional): Whether to ignore aliases. Defaults to ``True``.
        **kwargs: Additional arguments to pass to ``yaml.dump``.
    """
    if path is None:
        return toml.dumps(obj)
    with open(path, "w", encoding="utf-8") as f:
        toml.dump(obj, f)


class BooleanOptionalAction(argparse.Action):
    def __init__(
        self,
        option_strings: list[str],
        dest: str,
        default: bool | None = None,
        required: bool = False,
        help: str | None = None,
        metavar: str | None = None,
        invert: bool = False,
        opposite_flags: bool = False,
    ):
        _option_strings = []
        value_map = {}
        for option_string in option_strings:
            assert option_string.startswith("-")
            _option_strings.append(option_string)
            value_map[option_string] = not invert
            if opposite_flags and option_string.startswith("--"):
                if option_string.startswith("--enable-"):
                    option_string = "--dis" + option_string[4:]
                elif option_string.startswith("--disable-"):
                    option_string = "--en" + option_string[5:]
                elif option_string.startswith("--no-"):
                    option_string = "--" + option_string[5:]
                else:
                    option_string = "--no-" + option_string[2:]
                _option_strings.append(option_string)
                value_map[option_string] = invert

        super().__init__(
            option_strings=_option_strings,
            dest=dest,
            nargs="?",
            default=default,
            type=str,
            choices=["true", "false"],
            required=required,
            help=help,
            metavar=metavar,
        )
        self.value_map = value_map

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str,
        option_string: str | None = None,
    ):
        if values is None:
            setattr(namespace, self.dest, self.value_map[option_string])
        elif values == "true":
            setattr(namespace, self.dest, self.value_map[option_string])
        elif values == "false":
            setattr(namespace, self.dest, not self.value_map[option_string])
        else:
            parser.error(f"Invalid value {values!r} for {option_string!r}")
