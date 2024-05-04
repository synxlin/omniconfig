# -*- coding: utf-8 -*-
"""Parser class."""

import argparse
import os
from typing import Any, Callable, Sequence, Type, TypeVar

from .args import Arguments
from .utils import dump_toml, dump_yaml, format_scope_and_prefix, load_toml, load_yaml, update_dict

__all__ = ["ConfigParser"]


_T = TypeVar("_T")


class ConfigType(Type[_T]):
    def get_arguments(
        cls: Type[_T],
        /,
        *,
        scope: str = None,
        prefix: str = None,
        overwrites: dict[str, Callable[[Arguments], None] | None] | None = None,
        **defaults,
    ) -> Arguments: ...

    def from_dict(cls: Type[_T], /, parsed_args: dict[str, Any], **defaults) -> _T: ...


class ConfigParser:
    """Parser for config classes."""

    FILE_SCOPE: str = "cfgs"
    FILE_EXTS: tuple[str] = ("yaml", "yml", "toml")

    _cfgs: dict[str, tuple[ConfigType[Any], Arguments, str]]
    _parser: argparse.ArgumentParser

    def __init__(
        self,
        prog: str | None = None,
        usage: str | None = None,
        description: str | None = None,
        epilog: str | None = None,
        parents: Sequence[argparse.ArgumentParser] = [],
        formatter_class=argparse.HelpFormatter,
        fromfile_prefix_chars: str | None = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        exit_on_error: bool = True,
    ) -> None:
        """Initialize a parser for config classes."""
        self._cfgs = {}
        self._parser = argparse.ArgumentParser(
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            formatter_class=formatter_class,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            exit_on_error=exit_on_error,
        )
        self._parser.add_argument(type(self).FILE_SCOPE, nargs="*", help="config file(s)", default=[])

    def add_config(
        self, cfg: ConfigType[Any], /, scope: str | None = None, prefix: str | None = "", **defaults
    ) -> None:
        """Add a config class to the parser.

        Args:
            cfg (ConfigType[Any]): Config class to add.
            scope (str | None, optional): Scope of the config class. Defaults to ``None``.
            prefix (str | None, optional): Prefix of the config class. Defaults to ``""``.
            **defaults: Defaults for the arguments.
        """
        scope, prefix = format_scope_and_prefix(cfg, scope=scope, prefix=prefix)
        assert scope != self.FILE_SCOPE, f"scope {scope} is reserved for config files"
        assert scope not in self._cfgs, f"scope {scope} already exists"
        if len(self._cfgs) == 1:
            _s = next(iter(self._cfgs))
            assert _s.isidentifier(), f"scope {_s} is not a valid identifier"
        if len(self._cfgs) >= 1:
            assert scope.isidentifier(), f"scope {scope} is not a valid identifier"
        args = cfg.get_arguments(scope=scope, prefix=prefix, **defaults)
        args.add_to_parser(self._parser, suppress=True)
        self._cfgs[scope] = (cfg, args, prefix)

    @staticmethod
    def _load(path: str) -> dict[str, Any]:
        if path.endswith(".toml"):
            return load_toml(path)
        elif path.endswith(("yaml", "yml")):
            return load_yaml(path)
        else:
            raise ValueError(f"unsupported file type {path}")

    def _parse_args(  # noqa: C901
        self, args=None, namespace=None, **defaults
    ) -> tuple[dict[str, Any] | Any, dict[str, Any], list[str]]:
        parsed_args, unknown_args = self._parser.parse_known_args(args, namespace)
        import_paths: list[str] = []
        config_paths: list[str] = []
        for path in getattr(parsed_args, self.FILE_SCOPE, []):
            if path.endswith(self.FILE_EXTS):
                config_paths.append(path)
            else:
                import_paths.append(path)
        imported_config_paths: list[str] = []
        for import_path in import_paths:
            assert os.path.isfile(import_path), f"{import_path} is not a file"
            with open(import_path, "r") as f:
                for path in f.readlines():
                    path = path.strip()
                    assert os.path.isfile(path), f"{path} is not a file"
                    assert path.endswith(self.FILE_EXTS), f"{path} is not a config file"
                    imported_config_paths.append(path)
        config_paths = imported_config_paths + config_paths
        del imported_config_paths
        assert len(config_paths) > 0, "no config file(s) provided"
        loaded, filenames = {}, []
        default_paths = []
        for path in config_paths:
            assert os.path.isfile(path), f"{path} is not a file"
            assert path.endswith(self.FILE_EXTS), f"{path} is not a config file"
            # make sure config_path is under the current working directory
            rel_path = os.path.relpath(path, os.getcwd())
            assert not rel_path.startswith(".."), f"{path} is not under {os.getcwd()}"
            # config file should place under a subdirectory of the current working directory
            _paths = rel_path.split(os.sep)
            assert len(_paths) > 1, f"{path} is not under a subfolder of {os.getcwd()}"
            filename = _paths[-1]
            len_ext = len(filename.split(".")[-1]) + 1
            filenames.append(filename[:-len_ext])
            cfg_dir = ""
            for dirname in _paths[:-1]:
                cfg_dir = os.path.join(cfg_dir, dirname)
                for ext in self.FILE_EXTS:
                    default_path = os.path.join(cfg_dir, f"__default__.{ext}")
                    if os.path.isfile(default_path) and default_path not in default_paths:
                        default_paths.append(default_path)
                        break
        for path in default_paths:
            loaded = update_dict(loaded, self._load(path))
        for path in config_paths:
            loaded = update_dict(loaded, self._load(path))
        parsed, single = {}, len(self._cfgs) == 1
        if single:
            loaded[next(iter(self._cfgs))] = loaded
        cfg_name = "[" + "]+[".join(filenames) + "]"
        for scope, (cfg, args, prefix) in self._cfgs.items():
            parsed[scope] = args.parse(loaded[scope], reduced=False)
        cfgs = {}
        for scope, (cfg, args, prefix) in self._cfgs.items():
            prefix_ = f"{prefix}_" if prefix else ""
            _n = len(prefix_)
            update_dict(parsed[scope], args.to_dict(parsed_args, prefix=prefix, reduced=True), strict=True)
            cfgs[scope] = cfg.from_dict(
                parsed[scope], **{k[_n:]: v for k, v in defaults.items() if k.startswith(prefix_)}
            )
        if single:
            cfgs = next(iter(cfgs.values()))
            parsed = next(iter(parsed.values()))
        assert self.FILE_SCOPE not in parsed, f"scope {self.FILE_SCOPE} is reserved for config files"
        parsed[self.FILE_SCOPE] = dict(name=cfg_name, paths=config_paths)
        return cfgs, parsed, unknown_args

    def parse_args(self, args=None, namespace=None, **defaults) -> tuple[dict[str, Any] | Any, dict[str, Any]]:
        """Parse arguments.

        Args:
            args (list[str] | None, optional): Arguments to parse. Defaults to ``None``.
            namespace (argparse.Namespace | None, optional): Namespace to parse. Defaults to ``None``.
            **defaults: Defaults for constructing the config class.

        Returns:
            tuple[dict[str, Any] | Any, dict[str, Any]]: Configs from the parsed arguments, and parsed yaml configs.
        """
        cfgs, parsed, unknown_args = self._parse_args(args=args, namespace=namespace, **defaults)
        assert len(unknown_args) == 0, f"unknown arguments {unknown_args}"
        return cfgs, parsed

    def parse_known_args(
        self, args=None, namespace=None, **defaults
    ) -> tuple[dict[str, Any] | Any, dict[str, Any], list[str]]:
        """Parse arguments.

        Args:
            args (list[str] | None, optional): Arguments to parse. Defaults to ``None``.
            namespace (argparse.Namespace | None, optional): Namespace to parse. Defaults to ``None``.
            **defaults: Defaults for constructing the config class.

        Returns:
            tuple[dict[str, Any] | Any, dict[str, Any], list[str]]: Configs from the parsed arguments,
                                                                    parsed yaml configs, and unknown arguments.
        """
        return self._parse_args(args=args, namespace=namespace, **defaults)

    def dump_default(self, path: str) -> None:
        """Dump default config file.

        Args:
            path (str | None, optional): Path to dump the file.
        """
        default: dict[str, dict] = {}
        for scope, (cfg, args, prefix) in self._cfgs.items():
            default[scope] = args.to_dict(detailed=False)
        if len(self._cfgs) == 1:
            default = next(iter(default.values()))
        if path.endswith(("yaml", "yml")):
            return dump_yaml(default, path=path)
        elif path.endswith("toml"):
            return dump_toml(default, path=path)
        else:
            raise ValueError(f"unsupported file type {path}")
