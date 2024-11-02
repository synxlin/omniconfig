# -*- coding: utf-8 -*-
"""Parser class."""

import argparse
import os
import typing as tp

from .args import Arguments
from .utils import dump_toml, dump_yaml, format_scope_and_prefix, load_toml, load_yaml, update_dict

__all__ = ["ConfigParser"]


_T = tp.TypeVar("_T")


class ConfigType(tp.Type[_T]):
    def get_arguments(
        cls: tp.Type[_T],
        /,
        *,
        scope: str = None,
        prefix: str = None,
        overwrites: dict[str, tp.Callable[[Arguments], None] | None] | None = None,
        **defaults,
    ) -> Arguments: ...

    def from_dict(cls: tp.Type[_T], /, parsed_args: dict[str, tp.Any], **defaults) -> _T: ...


class ConfigParser:
    """Parser for config classes."""

    FILE_SCOPE: str = "cfgs"
    FILE_EXTS: tuple[str] = ("yaml", "yml", "toml")

    _cfgs: dict[str, tuple[ConfigType[tp.Any], Arguments, str]]
    _extras: set[str]
    _parser: argparse.ArgumentParser

    def __init__(
        self,
        prog: str | None = None,
        usage: str | None = None,
        description: str | None = None,
        epilog: str | None = None,
        parents: tp.Sequence[argparse.ArgumentParser] = [],
        formatter_class=argparse.HelpFormatter,
        fromfile_prefix_chars: str | None = None,
        argument_default: tp.Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        exit_on_error: bool = True,
    ) -> None:
        """Initialize a parser for config classes."""
        self._cfgs = {}
        self._extras = set()
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

    def add_config(self, cfg: ConfigType[tp.Any], /, scope: str = "", prefix: str | None = "", **defaults) -> None:
        """Add a config class to the parser.

        Args:
            cfg (`ConfigType[Any]`):
                Config class to add.
            scope (`str`, *optional*, defaults to `""`):
                Scope of the config class.
            prefix (`str` or `None`, *optional*, defaults to `""`):
                Prefix of the config class. Defaults to `""`.
            **defaults:
                Defaults for the arguments.
        """
        assert isinstance(scope, str), f"{scope} is not a string"
        scope, prefix = format_scope_and_prefix(cfg, scope=scope, prefix=prefix)
        assert scope != self.FILE_SCOPE, f"scope {scope} is reserved for config files"
        assert scope not in self._cfgs, f'scope "{scope}" already exists'
        if scope:
            assert scope.isidentifier(), f"scope {scope} is not a valid identifier"
        args = cfg.get_arguments(scope=scope, prefix=prefix, **defaults)
        args.add_to_parser(self._parser, suppress=True)
        self._cfgs[scope] = (cfg, args, prefix)

    def add_extra_argument(self, *args, **kwargs) -> None:
        """Add an extra argument to the parser.

        Args:
            *args:
                Arguments to add.
            **kwargs:
                Keyword arguments to add.
        """
        self._extras.add(self._parser.add_argument(*args, **kwargs).dest)

    @staticmethod
    def _load(path: str) -> dict[str, tp.Any]:
        if path.endswith(".toml"):
            return load_toml(path)
        elif path.endswith(("yaml", "yml")):
            return load_yaml(path)
        else:
            raise ValueError(f"unsupported file type {path}")

    def _parse_args(  # noqa: C901
        self, args=None, namespace=None, **defaults
    ) -> tuple[
        dict[str, tp.Any] | tp.Any,
        argparse.Namespace,
        dict[str, dict],
        argparse.Namespace | None,
        list[str],
    ]:
        namespace, unknown_args = self._parser.parse_known_args(args, namespace)
        # region move extra arguments in parsed_args to a separate namespace
        extra_args = argparse.Namespace()
        for extra in self._extras:
            setattr(extra_args, extra, getattr(namespace, extra))
            delattr(namespace, extra)
        # endregion
        loaded: dict[str, tp.Any] = {}
        # region load config files
        import_paths: list[str] = []
        config_paths: list[str] = []
        for path in getattr(namespace, self.FILE_SCOPE, []):
            assert isinstance(path, str), f"{path} is not a string"
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
        filenames: list[str] = []
        default_paths: list[str] = []
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
            loaded = update_dict(loaded, self._load(path), strict=False)
        for path in config_paths:
            loaded = update_dict(loaded, self._load(path), strict=False)
        # endregion
        namespaced: dict[str, tp.Any] = vars(namespace)
        namespaced.pop(self.FILE_SCOPE, None)
        parsed: dict[str, dict] = {}
        cfgs: dict[str, tp.Any] = {}
        for scope, (cfg, args, prefix) in self._cfgs.items():
            _parsed = args.to_dict()
            _loaded = loaded.pop(scope, {}) if scope else loaded
            if _loaded:
                _parsed_loaded, _loaded = args.parse(_loaded, flatten=False, parsed=False, prefix=prefix)
                update_dict(_parsed, _parsed_loaded, strict=True)
                if scope:
                    if _loaded:
                        loaded[scope] = _loaded
                else:
                    loaded = _loaded
                del _parsed_loaded
            if namespaced:
                _parsed_namespaced, namespaced = args.parse(namespaced, flatten=True, parsed=True, prefix=prefix)
                update_dict(_parsed, _parsed_namespaced, strict=True)
                del _parsed_namespaced
            parsed[scope] = _parsed
            del _parsed, _loaded
            prefix_ = f"{prefix}_" if prefix else ""
            len_prefix_ = len(prefix_)
            cfgs[scope] = cfg.from_dict(
                parsed[scope], **{k[len_prefix_:]: v for k, v in defaults.items() if k.startswith(prefix_)}
            )
        unused_args = None
        if len(namespaced) > 0:
            unused_args = argparse.Namespace()
            for k, v in namespaced.items():
                setattr(unused_args, k, v)
        if len(self._cfgs) == 1:
            cfgs = next(iter(cfgs.values()))
            parsed = next(iter(parsed.values()))
        return cfgs, extra_args, loaded, unused_args, unknown_args

    def parse_args(
        self, args=None, namespace=None, **defaults
    ) -> tuple[dict[str, tp.Any] | tp.Any, argparse.Namespace]:
        """Parse arguments.

        Args:
            args (list[str] | None, optional): Arguments to parse. Defaults to ``None``.
            namespace (argparse.Namespace | None, optional): Namespace to parse. Defaults to ``None``.
            **defaults: Defaults for constructing the config class.

        Returns:
            tuple[dict[str, Any] | Any, argparse.Namespace]: Configs and extra arguments.
        """
        cfgs, extra_args, unused_cfgs, unused_args, unknown_args = self._parse_args(
            args=args, namespace=namespace, **defaults
        )
        assert len(unused_cfgs) == 0, f"unused loaded configs {unused_cfgs}"
        assert unused_args is None, f"unused parsed arguments {unused_args}"
        assert len(unknown_args) == 0, f"unknown arguments {unknown_args}"
        return cfgs, extra_args

    def parse_known_args(
        self, args=None, namespace=None, **defaults
    ) -> tuple[
        dict[str, tp.Any] | tp.Any,
        argparse.Namespace,
        dict[str, dict],
        argparse.Namespace | None,
        list[str],
    ]:
        """Parse arguments.

        Args:
            args (`list[str]` or `None`, *optional*, defaults to `None`):
                Arguments to parse.
            namespace (`argparse.Namespace` or `None`, *optional*, defaults to `None`):
                Namespace to parse.
            **defaults:
                Defaults for constructing the config class.

        Returns:
            tuple[
                dict[str, Any] | Any,
                argparse.Namespace,
                dict[str, dict],
                argparse.Namespace | None,
                list[str]
            ]:
                Configs from the parsed arguments, extra arguments,
                unused loaded configs, unused parsed arguments, and unknown arguments.
        """
        return self._parse_args(args=args, namespace=namespace, **defaults)

    def dump_default(self, path: str) -> None:
        """Dump default config file.

        Args:
            path (str | None, optional): Path to dump the file.
        """
        default: dict[str, dict] = {}
        for _, (_, args, _) in self._cfgs.items():
            default.update(args.to_dict())
        if path.endswith(("yaml", "yml")):
            return dump_yaml(default, path=path)
        elif path.endswith("toml"):
            return dump_toml(default, path=path)
        else:
            raise ValueError(f"unsupported file type {path}")
