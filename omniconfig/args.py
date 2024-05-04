# -*- coding: utf-8 -*-
"""Arguments class for the argument parser and YAML config file."""

import argparse
import pprint
from dataclasses import MISSING, dataclass, field
from typing import Any, Union

from .utils import dump_yaml, dump_toml

__all__ = ["Arguments"]


_argparse_keys_ = frozenset(
    (
        "action",
        "choices",
        "const",
        "default",
        "dest",
        "help",
        "metavar",
        "nargs",
        "required",
        "type",
    )
)


def _format_dest(dest: str, prefix: str = "") -> str:
    return f"{prefix}_{dest}" if prefix else dest


def _format_prefix_to_flag(prefix: str) -> str:
    """Format a prefix to a flag.

    - Keep prefix's case.
    - If prefix is not started with underscore, replace all underscores with dashes.

    Args:
        prefix (str): Prefix.
    """
    if prefix:
        if prefix[0] == "_":
            return prefix
        else:
            return prefix.replace("_", "-")
    else:
        return ""


def _format_flag(flag: str, prefix: str = "") -> str:
    if flag[0] == "-":  # optional flag
        if flag[1] == "-":  # long optional flag
            return f"--{_format_prefix_to_flag(prefix)}-{flag[2:]}" if prefix else flag
        else:  # short optional flag
            return "" if prefix else flag
    else:  # positional flag
        return f"{prefix}_{flag}" if prefix else flag


@dataclass(frozen=True)
class Argument:
    """Argument for an argument parser.

    Args:
        dest (str): Argument destination.
        flags (list[str]): Argument flags.
        kwargs (dict[str, Any], optional): Keyword arguments for `argparse.ArgumentParser.add_argument`.
                                           Defaults to ``{}``.
        desc (str, optional): Argument description. Defaults to ``None``.

    Attributes:
        dest (str): Argument destination.
        flags (list[str]): Argument flags.
        kwargs (dict[str, Any], optional): Keyword arguments for `argparse.ArgumentParser.add_argument`.
                                           Defaults to ``{}``.
        desc (str, optional): Argument description. Defaults to ``None``.
        positional (bool): Whether this argument is positional.
        optional (bool): Whether this argument is optional.
        default (Any): Default value of this argument.

    Raises:
        ValueError: If `kwargs` contains invalid keys.
    """

    dest: str
    flags: list[str]
    kwargs: dict[str, Any] = field(default_factory=dict)
    desc: str = ""

    def __post_init__(self) -> None:
        assert self.dest.isidentifier(), f"Invalid dest: {self.dest}"
        if self.positional:
            assert len(self.flags) == 1, f"Invalid flags: {self.flags}"
            assert self.dest == self.flags[0], f"Invalid dest: {self.dest}"
        if not _argparse_keys_.issuperset(self.kwargs.keys()):
            raise ValueError(f"Invalid argparse keys: {self.kwargs.keys()}")

    @property
    def positional(self) -> bool:
        """Whether this argument is positional."""
        return self.flags[0][0] != "-"

    @property
    def optional(self) -> bool:
        """Whether this argument is optional."""
        return not self.positional

    @property
    def default(self) -> Any:
        """Default value of this argument."""
        default = self.kwargs.get("default", MISSING)
        if default is MISSING:
            action = self.kwargs.get("action", None)
            if action == "store_true":
                default = False
            elif action == "store_false":
                default = True
            elif action == "count":
                default = 0
            elif action in ("append", "append_const", "extend"):
                default = []
        return default

    def get_help_msg(self, prefix: str = "", *, detailed: bool = False) -> str:
        """Get the help message of this argument.

        Args:
            prefix (str, optional): Argument flag prefix. Defaults to ``""``.
            detailed (bool, optional): Whether to include detailed information. Defaults to ``False``.

        Returns:
            str: Help message of this argument.
        """
        if self.desc:
            if self.desc != argparse.SUPPRESS:
                help_msg, default = self.desc, self.default
                if prefix:
                    if help_msg[-1] == ".":
                        help_msg = help_msg[:-1]
                    help_msg += f" for {prefix}."
                if detailed and "choices" in self.kwargs:
                    help_msg += f" Choices: [{self.kwargs['choices']}]."
                if default is not MISSING and default is not argparse.SUPPRESS:
                    help_msg += f" Default: {default}."
                return help_msg
            else:
                return argparse.SUPPRESS
        else:
            return ""

    def add_to_parser(self, parser: argparse.ArgumentParser, *, prefix: str = "", suppress: bool = False) -> None:
        """Add this argument to an argument parser.

        Args:
            parser (argparse.ArgumentParser): Argument parser.
            prefix (str, optional): Argument flag prefix. Defaults to ``""``.
            suppress (bool, optional): Whether to suppress the default. Defaults to ``False``.
        """
        dest = _format_dest(self.dest, prefix)
        flags = [_format_flag(flag, prefix) for flag in self.flags]
        flags = [flag for flag in flags if flag]
        assert "-h" not in flags and "--help" not in flags, f"Invalid flags: {self.flags}"
        kwargs = self.kwargs.copy()
        if suppress:
            kwargs["default"] = argparse.SUPPRESS
        if self.desc:
            kwargs["help"] = self.get_help_msg(prefix)
        parser.add_argument(*flags, dest=dest, **kwargs)

    def get_value(self, args: argparse.Namespace | None = None, prefix: str = "") -> Any:
        """Get the value of this argument from parsed arguments.

        Args:
            args (argparse.Namespace, optional): Parsed arguments. Defaults to ``None``.
            prefix (str, optional): Argument flag prefix. Defaults to ``""``.

        Returns:
            Any: Value of this argument. If `args` is not specified, `self.default` will be returned.
        """
        if args:
            return args.__dict__.get(_format_dest(self.dest, prefix), MISSING)
        else:
            return self.default


@dataclass
class Arguments:
    """Arguments for an argument parser.

    Args:
        scope (str): Argument scope.
        prefix (str, optional): Argument prefix. If not specified, `scope` will be used. Defaults to ``None``.

    Attributes:
        scope (str): Argument scope.
        prefix (str): Argument prefix.
        arguments (tuple[Union[Argument, Arguments], ...]): Arguments.
        flags (set[str]): Argument flags.
        dests (set[str]): Argument destinations.
        inside (list[Arguments]): List of arguments inside which this arguments is used.
    """

    scope: str = ""
    prefix: str = None
    _arguments: list[Union[Argument, "Arguments"]] = field(init=False, default_factory=list)
    _flags: set[str] = field(init=False, default_factory=set)
    _dests: set[str] = field(init=False, default_factory=set)
    _parent: list["Arguments"] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.scope:
            assert self.scope.isidentifier(), f"Invalid scope: {self.scope}"
        else:
            self.scope = ""
        if self.prefix is None:
            self.prefix = self.scope
        elif self.prefix:
            assert self.prefix.isidentifier(), f"Invalid prefix: {self.prefix}"
        else:
            self.prefix = ""

    @property
    def arguments(self) -> tuple[Union[Argument, "Arguments"], ...]:
        """Arguments."""
        return self._arguments  # type: ignore

    @property
    def flags(self) -> frozenset[str]:
        """Argument flags."""
        return self._flags  # type: ignore

    @property
    def dests(self) -> frozenset[str]:
        """Argument destinations."""
        return self._dests  # type: ignore

    def _contains_dest(self, dest: str) -> bool:
        if dest in self._dests:
            return True
        if self._parent:
            parent_dest = _format_dest(dest, self.prefix)
            for parent in self._parent:
                if parent._contains_dest(parent_dest):
                    return True
        return False

    def _contains_flag(self, flag: str) -> bool:
        if flag in self._flags:
            return True
        if self._parent:
            parent_flag = _format_flag(flag, self.prefix)
            if parent_flag:
                for parent in self._parent:
                    if parent._contains_flag(parent_flag):
                        return True
        return False

    def _add_dest(self, dest: str) -> None:
        self._dests.add(dest)
        if self._parent:
            parent_dest = _format_dest(dest, self.prefix)
            for parent in self._parent:
                parent._add_dest(parent_dest)

    def _add_flag(self, flag: str | None) -> None:
        if flag:
            self._flags.add(flag)
            if self._parent:
                parent_flag = _format_flag(flag, self.prefix)
                if parent_flag:
                    for parent in self._parent:
                        parent._add_flag(parent_flag)

    def add_argument(self, *args, **kwargs) -> None:
        """Add an argument.

        Args:
            *args (tuple[str]): Positional arguments for `argparse.ArgumentParser.add_argument`.
            **kwargs (dict[str, Any]): Keyword arguments for `argparse.ArgumentParser.add_argument`.

        Raises:
            AssertionError: If `args` contains invalid flags.
        """
        # region format args
        assert args and all(isinstance(arg, str) for arg in args), f"flags must be non-empty strings: {args}"
        is_optionals: list[bool] = []
        flags: list[str] = []
        for flag in args:
            if flag[0] == "-":  # optional argument
                is_optionals.append(True)
                assert not flag.startswith("---"), f"long flags must start with two dashes: {args}"
            else:  # positional argument
                is_optionals.append(False)
                assert flag.isidentifier(), f"positional flags must be valid identifiers: {args}"
            assert flag, f"flags must not be empty strings: {args}"
            flags.append(flag)
        is_optional = is_optionals[0]
        if is_optional:  # optional argument
            assert all(is_optionals), f"optional arguments must have all optional flags: {args}"
            # sort flags so that long flags come first and short flags come last, e.g., --flag, -f
            # between long flags or short flags, order is preserved
            long_flags = [flag for flag in flags if flag[1] == "-"]
            short_flags = [flag for flag in flags if flag[1] != "-"]
            flags = long_flags + short_flags
            assert all(len(flag) == 2 for flag in short_flags), f"short flags must have exactly one character: {args}"
        else:  # positional argument
            assert len(flags) == 1, f"positional arguments must have exactly one flag: {args}"
        # endregion
        # region infer dest
        dest = kwargs.pop("dest", flags[0].lstrip("-").replace("-", "_"))
        assert isinstance(dest, str) and dest.isidentifier(), f"dest must be a valid python identifier: {dest}"
        # endregion
        assert not self._contains_dest(dest), f"dest must be unique: {dest}"
        self._add_dest(dest)
        for flag in flags:
            assert not self._contains_flag(flag), f"flag must be unique: {flag}"
            self._add_flag(flag)
        desc = kwargs.pop("help", "").strip()
        self._arguments.append(Argument(dest=dest, flags=flags, kwargs=kwargs, desc=desc))

    def add_arguments(self, args: "Arguments") -> None:
        """Add arguments.

        Args:
            args (Arguments): Arguments to add.

        Raises:
            AssertionError: If `args` contains invalid flags.
        """
        assert isinstance(args, Arguments), f"args must be an instance of Arguments: {args}"
        assert not self._contains_dest(args.scope), f"dest must be unique: {args.scope}"
        self._add_dest(args.scope)
        for dest in args.dests:
            dest = _format_dest(dest, args.prefix)
            assert not self._contains_dest(dest), f"dest must be unique: {dest}"
            self._add_dest(dest)
        for flag in args.flags:
            flag = _format_flag(flag, args.prefix)
            if flag:
                assert not self._contains_flag(flag), f"flag must be unique: {flag}"
                self._add_flag(flag)
        self._arguments.append(args)
        args._parent.append(self)

    def add_to_parser(self, parser: argparse.ArgumentParser, *, prefix: str = "", suppress: bool = False) -> None:
        """Add arguments to a parser.

        Args:
            parser (argparse.ArgumentParser): Parser to add arguments to.
            prefix (str, optional): Prefix to add to argument flags and dests. Defaults to ``""``.
            suppress (bool, optional): Whether to suppress default. Defaults to ``False``.
        """
        prefix = (f"{prefix}_{self.prefix}" if self.prefix else prefix) if prefix else self.prefix
        for arg in self.arguments:
            arg.add_to_parser(parser, prefix=prefix, suppress=suppress)

    def to_dict(
        self,
        parsed_args: argparse.Namespace | None = None,
        /,
        *,
        prefix: str = "",
        detailed: bool = False,
        reduced: bool = False,
    ) -> dict[str, Any]:
        """Parse parsed arguments to a dictionary.

        Args:
            parsed_args (argparse.Namespace, optional): Parsed arguments. Defaults to ``None``.
            prefix (str, optional): Prefix to add to argument flags and dests. Defaults to ``""``.
            detailed (bool, optional): Whether to include detailed information. Defaults to ``False``.
            reduced (bool, optional): Whether to keep argument when value is missing. Defaults to ``False``.

        Returns:
            dict[str, Any]: Parsed dictionary. Keys are argument destinations. Values are argument values.
        """
        prefix = (f"{prefix}_{self.prefix}" if self.prefix else prefix) if prefix else self.prefix
        parsed: dict[str, Any] = {}
        for arg in self.arguments:
            if isinstance(arg, Arguments):
                assert arg.scope not in parsed, f"scope {arg.scope} is not unique in {self.scope}"
                parsed[arg.scope] = arg.to_dict(parsed_args, prefix=prefix, detailed=detailed, reduced=reduced)
            else:
                assert arg.dest not in parsed, f"dest {arg.dest} is not unique in {self.scope}"
                value = arg.get_value(parsed_args, prefix=prefix)
                if not reduced or value is not MISSING:
                    if detailed:
                        help_msg = arg.get_help_msg(prefix, detailed=True)
                        parsed[arg.dest] = dict(flags=arg.flags, help=help_msg, value=value, kwargs=arg.kwargs)
                    else:
                        parsed[arg.dest] = value if value is not MISSING else "MISSING"
        return parsed

    def __str__(self) -> str:
        return pprint.PrettyPrinter(indent=2).pformat(self.to_dict(detailed=True))

    def parse(self, loaded: dict[str, Any], /, *, reduced: bool = False) -> dict[str, Any]:
        """Parse loaded configs to arguments.

        Args:
            loaded (dict[str, Any]): Loaded configs.
        """
        parsed: dict[str, Any] = {}
        for arg in self.arguments:
            if isinstance(arg, Arguments):
                if arg.scope in loaded:
                    parsed[arg.scope] = arg.parse(loaded[arg.scope])
                elif not reduced:
                    parsed[arg.scope] = arg.to_dict()
            elif arg.dest in loaded:
                value = loaded[arg.dest]
                if isinstance(value, str) and "type" in arg.kwargs:
                    value = arg.kwargs["type"](value)
                elif isinstance(value, list) and "nargs" in arg.kwargs and arg.kwargs["nargs"] != 1:
                    if len(value) > 0 and isinstance(value[0], str) and "type" in arg.kwargs:
                        value = [arg.kwargs["type"](v) for v in value]
                parsed[arg.dest] = value
            elif not reduced:
                value = arg.default
                assert value is not MISSING, f"missing default value for {arg.dest}"
                parsed[arg.dest] = value
        return parsed

    def dump_yaml(self, path: str | None = None) -> str | None:
        """Dump arguments to YAML.

        Args:
            path (str, optional): Path to dump YAML to. Defaults to ``None``.

        Returns:
            str: Dumped YAML string if `path` is ``None``.
        """
        return dump_yaml(self.to_dict(detailed=False), path=path)

    def dump_toml(self, path: str | None = None) -> str | None:
        """Dump arguments to TOML.

        Args:
            path (str, optional): Path to dump TOML to. Defaults to ``None``.

        Returns:
            str: Dumped TOML string if `path` is ``None``.
        """
        return dump_toml(self.to_dict(detailed=False), path=path)