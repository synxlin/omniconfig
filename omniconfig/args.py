# -*- coding: utf-8 -*-
"""Arguments class for the argument parser and YAML config file."""

import argparse
import typing as tp
from dataclasses import MISSING, dataclass, field

from .utils import dump_toml, dump_yaml

__all__ = ["Arguments"]


_argparse_keys_ = frozenset(
    ("action", "choices", "const", "default", "dest", "help", "metavar", "nargs", "required", "type")
)


def _format_dest(dest: str, /, *, prefix: str = "") -> str:
    """Format an argument destination.

    Args:
        dest (`str`):
            Argument destination.
        prefix (`str`, *optional*, defaults to `""`):
            Argument prefix.

    Returns:
        `str`:
            Formatted argument destination.
    """
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


def _format_flag(flag: str, /, *, prefix: str = "") -> str:
    """Format an argument flag.

    Args:
        flag (`str`):
            Argument flag.
        prefix (`str`, *optional*, defaults to `""`):
            Argument prefix.

    Returns:
        `str`:
            Formatted argument flag.
    """
    if flag[0] == "-":  # optional flag
        if flag[1] == "-":  # long optional flag
            return f"--{_format_prefix_to_flag(prefix)}-{flag[2:]}" if prefix else flag
        else:  # short optional flag
            return "" if prefix else flag
    else:  # positional flag
        return f"{prefix}_{flag}" if prefix else flag


def _format_desc(
    desc: str, /, *, prefix: str = "", dest: str = "", choices: tp.Sequence[tp.Any] = (), default: tp.Any = MISSING
) -> str:
    """Format an argument description.

    Args:
        desc (`str`):
            Argument description.
        prefix (`str`, *optional*, defaults to `""`):
            Argument prefix.
        default (`tp.Any`, *optional*, defaults to `MISSING`):
            Default argument value.
        choices (`Sequence[tp.Any]`, *optional*, defaults to `()`):
            Argument choices.

    Returns:
        `str`:
            Formatted help message.
    """
    if desc:
        if desc != argparse.SUPPRESS:
            if prefix:
                if desc[-1] == ".":
                    desc = desc[:-1]
                desc += f" for {prefix}."
            if dest:
                desc += f" Dest: {dest}."
            if choices:
                desc += f" Choices: {list(choices)}."
            if default is not MISSING:
                if not isinstance(default, str) or default != argparse.SUPPRESS:
                    desc += f" Default: {default}."
            return desc
        else:
            return argparse.SUPPRESS
    else:
        return ""


@dataclass(kw_only=True, frozen=True)
class Argument:
    """Argument for an argument parser.

    Args:
        dest (`str`):
            Argument destination.
        flags (`list[str]`):
            Argument flags.
        kwargs (`dict[str, tp.Any]`, *optional*, defaults to `{}`):
            Keyword arguments for `argparse.ArgumentParser.add_argument`.
        desc (`str`, *optional*, defaults to `""`):
            Argument description.

    Attributes:
        positional (`bool`):
            Whether this argument is positional, i.e., its flag does not start with a dash.
        optional (`bool`):
            Whether this argument is optional, i.e., its flag starts with a dash.
        default (`tp.Any`):
            Default value of this argument.

    Raises:
        ValueError: If `kwargs` contains invalid keys.
    """

    dest: str
    flags: list[str]
    kwargs: dict[str, tp.Any] = field(default_factory=dict)
    desc: str = ""

    def __post_init__(self) -> None:
        assert self.dest.isidentifier(), f'Invalid dest: "{self.dest}"'
        if any(flag[0] == "-" for flag in self.flags):  # optional argument
            assert all(flag[0] == "-" for flag in self.flags), f'Invalid flags: "{self.flags}"'
        else:  # positional argument
            assert len(self.flags) == 1, f'Invalid flags: "{self.flags}"'
            assert self.dest == self.flags[0], f'Invalid dest: "{self.dest}"'
        assert _argparse_keys_.issuperset(self.kwargs.keys()), f"Invalid argparse keys: {self.kwargs.keys()}"

    @property
    def default(self) -> tp.Any:
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

    def add_to_parser(self, parser: argparse.ArgumentParser, *, prefix: str = "", suppress: bool = False) -> None:
        """Add this argument to an argument parser.

        Args:
            parser (`argparse.ArgumentParser`):
                Argument parser.
            prefix (`str`, *optional*, defaults to `""`):
                Argument prefix.
            suppress (`bool`, *optional*, defaults to `False`):
                Whether to suppress the default.
        """
        dest = _format_dest(self.dest, prefix=prefix)
        assert dest.isidentifier(), f'Invalid dest: "{dest}"'
        flags = [_format_flag(flag, prefix=prefix) for flag in self.flags]
        flags = [flag for flag in flags if flag]
        assert "-h" not in flags and "--help" not in flags, f'Invalid flags: "{self.flags}"'
        kwargs = self.kwargs.copy()
        if suppress:
            kwargs["default"] = argparse.SUPPRESS
        desc = kwargs.pop("help", self.desc).strip()
        if desc:
            kwargs["help"] = _format_desc(
                desc, prefix=prefix, dest=dest, choices=kwargs.get("choices", ()), default=self.default
            )
        parser.add_argument(*flags, dest=dest, **kwargs)


@dataclass
class Arguments:
    """Arguments with the same scope and prefix for an argument parser.

    Args:
        scope (`str`, *optional*, defaults to `""`):
            Arguments scope / destination.
        prefix (`str`, *optional*, defaults to `None`):
            Arguments prefix. If `None`, uses `scope`.

    Attributes:
        arguments (`tuple[Union[Argument, Arguments], ...]`):
            Arguments in the scope.
        flags (`set[str]`):
            Flags of all arguments in the scope.
        dests (`frozenset[str]`):
            Destinations of all arguments in the scope.
        inside (`frozenset[Arguments]`):
            List of arguments inside which this arguments is used.
    """

    scope: str = ""
    prefix: str = None
    _arguments: list[tp.Union[Argument, "Arguments"]] = field(init=False, default_factory=list)
    _flags: set[str] = field(init=False, default_factory=set)
    _dests: set[str] = field(init=False, default_factory=set)
    _parents: list["Arguments"] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.scope:
            assert self.scope.isidentifier(), f'Invalid scope: "{self.scope}"'
        else:
            self.scope = ""
        if self.prefix is None:
            self.prefix = self.scope
        elif self.prefix:
            assert self.prefix.isidentifier(), f'Invalid prefix: "{self.prefix}"'
        else:
            self.prefix = ""

    @property
    def arguments(self) -> tuple[tp.Union[Argument, "Arguments"], ...]:
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
        if self._parents:
            dest_in_parent = _format_dest(dest, prefix=self.prefix)
            return any(parent._contains_dest(dest_in_parent) for parent in self._parents)
        return False

    def _contains_flag(self, flag: str) -> bool:
        if flag in self._flags:
            return True
        if self._parents:
            flag_in_parent = _format_flag(flag, prefix=self.prefix)
            if flag_in_parent:
                return any(parent._contains_flag(flag_in_parent) for parent in self._parents)
        return False

    def _add_dest(self, dest: str) -> None:
        self._dests.add(dest)
        if self._parents:
            dest_in_parent = _format_dest(dest, prefix=self.prefix)
            for parent in self._parents:
                parent._add_dest(dest_in_parent)

    def _add_flag(self, flag: str | None) -> None:
        if flag:
            self._flags.add(flag)
            if self._parents:
                flag_in_parent = _format_flag(flag, prefix=self.prefix)
                if flag_in_parent:
                    for parent in self._parents:
                        parent._add_flag(flag_in_parent)

    def add_argument(self, *args, **kwargs) -> None:
        """Add an argument.

        Args:
            *args (`tuple[str, ...]`):
                Positional arguments for `argparse.ArgumentParser.add_argument`.
            **kwargs (`dict[str, tp.Any]`):
                Keyword arguments for `argparse.ArgumentParser.add_argument`.

        Raises:
            AssertionError: If `args` contains invalid flags.
        """
        # region format args
        is_optionals: list[bool] = []
        flags: list[str] = []
        for flag in args:
            assert flag and isinstance(flag, str), f'flag must be a non-empty string: "{flag}" in {args}'
            if flag[0] == "-":  # optional argument
                is_optionals.append(True)
                assert not flag.startswith("---"), f"long flags must start with two dashes: {args}"
            else:  # positional argument
                is_optionals.append(False)
                assert flag.isidentifier(), f"positional flags must be valid identifiers: {args}"
            assert flag, f"flags must not be empty strings: {args}"
            flags.append(flag)
        assert flags, f"flags must not be empty: {args}"
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
        assert isinstance(dest, str) and dest.isidentifier(), f'dest must be a valid python identifier: "{dest}"'
        # endregion
        assert not self._contains_dest(dest), f'dest must be unique: "{dest}"'
        self._add_dest(dest)
        for flag in flags:
            assert not self._contains_flag(flag), f'flag must be unique: "{flag}"'
            self._add_flag(flag)
        desc = kwargs.pop("help", "").strip()
        self._arguments.append(Argument(dest=dest, flags=flags, kwargs=kwargs, desc=desc))

    def add_arguments(self, args: "Arguments") -> None:
        """Add arguments.

        Args:
            args (`Arguments`):
                Arguments to add.

        Raises:
            AssertionError: If `args` contains invalid flags.
        """
        assert isinstance(args, Arguments), f"args must be an instance of Arguments: {args}"
        assert not self._contains_dest(args.scope), f'dest must be unique: "{args.scope}"'
        self._add_dest(args.scope)
        for dest in args.dests:
            dest = _format_dest(dest, prefix=args.prefix)
            assert not self._contains_dest(dest), f'dest must be unique: "{dest}"'
            self._add_dest(dest)
        for flag in args.flags:
            flag = _format_flag(flag, prefix=args.prefix)
            if flag:
                assert not self._contains_flag(flag), f'flag must be unique: "{flag}"'
                self._add_flag(flag)
        self._arguments.append(args)
        args._parents.append(self)

    def add_to_parser(self, parser: argparse.ArgumentParser, *, prefix: str = "", suppress: bool = False) -> None:
        """Add arguments to a parser.

        Args:
            parser (`argparse.ArgumentParser`):
                Argument parser.
            prefix (`str`, *optional*, defaults to `""`):
                Arguments prefix.
            suppress (`bool`, *optional*, defaults to `False`):
                Whether to suppress default.
        """
        prefix = (f"{prefix}_{self.prefix}" if self.prefix else prefix) if prefix else self.prefix
        for arg in self.arguments:
            arg.add_to_parser(parser, prefix=prefix, suppress=suppress)

    def to_dict(self) -> dict[str, tp.Any]:
        """Convert the default settings to a dictionary.

        Returns:
            `dict[str, tp.Any]`: Parsed dictionary.
                Keys are argument destinations. Values are argument values.
        """
        defaults: dict[str, tp.Any] = {}
        for arg in self.arguments:
            if isinstance(arg, Arguments):
                assert arg.scope not in defaults, f'scope "{arg.scope}" is not unique in "{self.scope}"'
                defaults[arg.scope] = arg.to_dict()
            else:
                assert arg.dest not in defaults, f'dest "{arg.dest}" is not unique in "{self.scope}"'
                defaults[arg.dest] = arg.default
        return defaults

    def parse(
        self, loaded: dict[str, tp.Any], /, *, flatten: bool, parsed: bool, prefix: str = ""
    ) -> tuple[dict[str, tp.Any], dict[str, tp.Any]]:
        """Parse loaded arguments to dictionaries of known and unknown arguments.

        Args:
            loaded (`dict[str, tp.Any]`):
                Loaded arguments.
            flatten (`bool`):
                Whether loaded arguments are flattened.
            parsed (`bool`):
                Whether loaded arguments have parsed values.
            prefix (`str`, *optional*, defaults to `""`):
                Arguments prefix.

        Returns:
            `tuple[dict[str, tp.Any], dict[str, tp.Any]]`:
                Parsed dictionaries of known and unknown arguments.
                Dictionary for known arguments is always not flattened.
                Dictionary for unknown arguments is flattened if `flatten` is `True`, i.e., same as `loaded`.
        """
        prefix = (f"{prefix}_{self.prefix}" if self.prefix else prefix) if prefix else self.prefix
        unknown: dict[str, tp.Any] = dict(loaded.items())
        known: dict[str, tp.Any] = {}
        for arg in self.arguments:
            if isinstance(arg, Arguments):
                assert arg.scope not in known, f'scope "{arg.scope}" is not unique in "{self.scope}"'
                if flatten:
                    _known, _unknown = arg.parse(unknown, flatten=flatten, parsed=parsed, prefix=prefix)
                    if _known:
                        known[arg.scope] = _known
                    unknown = _unknown
                else:
                    if arg.scope in unknown:
                        _known, _unknown = arg.parse(
                            unknown.pop(arg.scope), flatten=flatten, parsed=parsed, prefix=prefix
                        )
                        if _unknown:
                            unknown[arg.scope] = _unknown
                        known[arg.scope] = _known
            else:
                assert arg.dest not in known, f'dest "{arg.dest}" is not unique in "{self.scope}"'
                dest = _format_dest(arg.dest, prefix=prefix) if flatten else arg.dest
                if dest in unknown:
                    value = unknown.pop(dest)
                    if not parsed:
                        if isinstance(value, str) and "type" in arg.kwargs:
                            value = arg.kwargs["type"](value)
                        elif isinstance(value, list) and "nargs" in arg.kwargs:
                            if len(value) > 0 and isinstance(value[0], str) and "type" in arg.kwargs:
                                value = [arg.kwargs["type"](v) for v in value]
                    known[arg.dest] = value
        return known, unknown

    def dump_yaml(self, path: str | None = None) -> str | None:
        """Dump arguments to YAML.

        Args:
            path (`str`, *optional*, defaults to `None`):
                Path to dump YAML to. If `None`, returns the dumped YAML string.

        Returns:
            `str` or `None`:
                If `path` is `None`, returns the dumped YAML string. Otherwise, returns `None`.
        """
        return dump_yaml(self.to_dict(), path=path)

    def dump_toml(self, path: str | None = None) -> str | None:
        """Dump arguments to TOML.

        Args:
            path (`str`, *optional*, defaults to `None`):
                Path to dump TOML to. If `None`, returns the dumped TOML string

        Returns:
            `str` or `None`:
                If `path` is `None`, returns the dumped TOML string. Otherwise, returns `None`.
        """
        return dump_toml(self.to_dict(), path=path)
