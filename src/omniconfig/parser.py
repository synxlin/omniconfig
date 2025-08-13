"""Main OmniConfigParser implementation."""

import argparse
import logging
import sys
from collections import OrderedDict
from dataclasses import MISSING, is_dataclass
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type

from .core.exceptions import ConfigError
from .core.reference import REFERENCE_SEPARATOR
from .core.types import _GLOBAL_TYPE_SYSTEM, TypeSystem
from .core.utils import dumps_to_json, dumps_to_yaml
from .namespace import OmniConfigNamespace
from .parsing.cli_parser import CLIParser
from .parsing.file_loader import FileLoader
from .parsing.merger import ConfigMerger
from .resolution.node import ResolutionNode
from .resolution.state import ResolutionState

DUAL_REFERENCE_SEPARATOR = REFERENCE_SEPARATOR + REFERENCE_SEPARATOR


class OmniConfigParser:
    """Main parser for OmniConfig."""

    FILE_SCOPE: ClassVar[str] = "cfgs"
    FILE_EXTS: ClassVar[Tuple[str, ...]] = (
        FileLoader.CONFIG_FILE_EXTS + FileLoader.RECIPE_FILE_EXTS
    )

    def __init__(
        self,
        prog: Optional[str] = None,
        usage: Optional[str] = None,
        description: Optional[str] = None,
        epilog: Optional[str] = None,
        parents: Optional[List[argparse.ArgumentParser]] = None,
        formatter_class: Type[argparse.HelpFormatter] = argparse.HelpFormatter,
        prefix_chars: str = "-",
        fromfile_prefix_chars: Optional[str] = None,
        exit_on_error: bool = True,
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
        parser: Optional[argparse.ArgumentParser] = None,
        suppress_cli: bool = False,
        keep_cli_flag_underscores: bool = False,
        keep_cli_private_flag_underscores: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize OmniConfigParser.

        Parameters
        ----------
        parser : Optional[argparse.ArgumentParser]
            Existing argument parser to use.
        """
        self._type_system = type_system

        # Set up logging
        self._logger = logger or logging.getLogger(__name__)

        # Initialize components
        self._parser = parser or argparse.ArgumentParser(
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=[] if parents is None else parents,
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            allow_abbrev=False,
            exit_on_error=exit_on_error,
        )
        if suppress_cli:
            self._cli_parser = None
        else:
            self._cli_parser = CLIParser(
                self._parser,
                keep_flag_underscores=keep_cli_flag_underscores,
                keep_private_flag_underscores=keep_cli_private_flag_underscores,
                type_system=self._type_system,
            )
        self._file_loader = FileLoader()

        # Set up trackers
        # Track registered configs: scope -> (config_cls, flag)
        self._configs: OrderedDict[str, Tuple[Type, str]] = OrderedDict()
        # Track extras for additional arguments
        self._extras = set()

        # Add file loading argument
        self._parser.add_argument(
            self.FILE_SCOPE,
            nargs="*",
            help="Configuration files to load. Can be YAML, JSON, or recipe files.",
            metavar="CONFIG_FILES",
        )

    @property
    def debug(self) -> bool:
        """Get debug mode status."""
        return self._logger.isEnabledFor(logging.DEBUG)

    def set_logging_level(self, level: int | str) -> None:
        self._logger.setLevel(level)

    def add_config(
        self, cls: Type, /, scope: str = "", flag: Optional[str] = None, help: str = ""
    ) -> None:
        """Add a dataclass to the parser.

        Parameters
        ----------
        cls : Type
            Dataclass to add.
        scope : str, default: ""
            Scope for the config.
            Empty scope can only be used when it's the only config.
        flag : Optional[str], default: None
            Flag prefix for CLI arguments. If None, defaults to scope.
        help : str, default: ""
            Help text for the config.

        Raises
        ------
        ConfigError
            If scope is already used or config is invalid.
            If mixing empty scope with non-empty scopes.
        """
        # Validate dataclass
        if not is_dataclass(cls):
            raise ConfigError(f"{cls.__name__} is not a dataclass. Use @dataclass decorator.")

        # Check mutual exclusivity for empty scope
        if scope:
            # If adding non-empty scope, check if empty scope exists
            if "" in self._configs:
                raise ConfigError(
                    "Cannot add non-empty scope config when empty scope exists. "
                    "Empty scope must be the only config."
                )
            if not scope.isidentifier():
                raise ConfigError(f"Scope '{scope}' is not a valid identifier")
        else:
            # If adding empty scope, no other configs should exist
            if self._configs:
                raise ConfigError(
                    "Cannot add empty scope config when non-empty scopes exist. "
                    "Empty scope is only allowed when it's the only config."
                )

        # Check for duplicate scope
        if scope in self._configs:
            raise ConfigError(f"Scope '{scope}' is already registered")

        # Infer flag if not provided
        if flag is None:
            flag = scope

        # Register with all components
        self._configs[scope] = (cls, flag)
        if self._cli_parser is not None:
            self._cli_parser.add_config(cls, scope=scope, flag_name=flag, help=help)

        if self.debug:
            self._logger.debug(
                f"Registered config {cls.__name__} with"
                f" scope='{scope}', flag='{flag}', help='{help}'"
            )

    def add_extra_argument(self, *args, **kwargs) -> None:
        """Add extra argument to the parser.

        Parameters
        ----------
        *args : Any
            Positional arguments for argparse.add_argument.
        **kwargs : Any
            Keyword arguments for argparse.add_argument.
        """
        self._extras.add(self._parser.add_argument(*args, **kwargs).dest)

    def parse_known_args(  # noqa: C901
        self, args: Optional[List[str]] = None, namespace: Optional[argparse.Namespace] = None
    ) -> Tuple[
        OmniConfigNamespace,
        argparse.Namespace,
        argparse.Namespace,
        Dict[str, Any],
        Dict[str, Any],
        List[str],
    ]:
        """Parse configuration from all sources.

        Parameters
        ----------
        args : Optional[List[str]]
            Command line arguments. If None, uses sys.argv.
        namespace : Optional[argparse.Namespace]
            Existing namespace to populate. If None, creates a new one.

        Returns
        -------
        Tuple[ConfigNamespace, argparse.Namespace, argparse.Namespace,
              Dict[str, Any], Dict[str, Any], List[str]]
            (config_namespace, extra_namespace, unused_namespace,
              used_data, unused_data, unknown)
            - config_namespace: Parsed configuration namespace
            - extra_namespace: Extra arguments namespace from argparse
            - unused_namespace: Unused fields from CLI namespace
            - used_data: Used data from universal structure
            - unused_data: Unused data from universal structure
            - unknown: Unknown CLI arguments
        """
        if self.debug:
            if args is None:
                args = sys.argv[1:]
            self._logger.debug(f"Parsing arguments: {args}")
            self._logger.debug(f"Using namespace: {namespace}")

        # Step 1: Parse CLI arguments to argparse.Namespace
        namespace, unknown_args = self._parser.parse_known_args(args, namespace)
        assert namespace is not None, "Namespace cannot be None"

        # Step 2: Extract extra arguments
        extra_namespace = argparse.Namespace()
        for extra in self._extras:
            if hasattr(namespace, extra):
                setattr(extra_namespace, extra, getattr(namespace, extra))
                delattr(namespace, extra)

        # Step 3: Extract config files from positional arguments
        if hasattr(namespace, self.FILE_SCOPE):
            files = getattr(namespace, self.FILE_SCOPE)
            delattr(namespace, self.FILE_SCOPE)
        else:
            files = []

        # Step 4: Load files with default files along directory paths
        file_configs = []
        if files:
            self._logger.debug("Loading config files with defaults: %s", files)
            # Load defaults hierarchically and then the specified files
            for file_config in self._file_loader.load_with_defaults(files):
                # Handle empty scope: wrap flat config in {"": {...}}
                if "" in self._configs and "" not in file_config:
                    file_config = {"": file_config}
                file_configs.append(file_config)
                del file_config

        # Step 5: Parse and convert CLI Namespace to universal structure
        if self._cli_parser is None:
            cli_data = {}
        else:
            self._logger.debug("Converting CLI namespace to universal structure")
            cli_data = self._cli_parser.parse_namespace(namespace, remove_parsed=True)
        unused_namespace = namespace
        del namespace

        # Step 6: Merge all sources according to priority order
        self._logger.debug("All sources merged according to priority order")
        universal_data = ConfigMerger.merge(*file_configs, cli_data)

        # Step 8: Translate references for empty scope
        if "" in self._configs:
            self._logger.debug("Translating references for empty scope configuration")
            universal_data = self._translate_empty_scope_references(universal_data)

        # Step 9: Apply factories, and resolve references
        self._logger.debug("Applying factories and resolve references iteratively")
        root = self._resolve_and_factory(universal_data)
        assert isinstance(root.content, dict), "Root content must be a dict"

        # Step 10: Output final configclass objects
        config_namespace = OmniConfigNamespace()
        used_data, unused_data = {}, {}
        # Extract configurations by scope
        for scope, (cls, _) in self._configs.items():
            if scope in root.content:
                used, unused = root.content[scope].split(data=universal_data[scope])
                if used is not MISSING:
                    used_data[scope] = used
                if unused is not MISSING:
                    unused_data[scope] = unused
                # If scope exists in root, materialize it
                config_namespace[scope] = root.content[scope].materialize()
            else:
                # If scope is not in root, create an empty instance
                config_namespace[scope] = cls()
        for key, value in universal_data.items():
            if key not in self._configs:
                unused_data[key] = value
        if "" in self._configs:
            used_data = self._translate_empty_scope_references(used_data, recover=True).get("", {})

        return (
            config_namespace,
            extra_namespace,
            unused_namespace,
            used_data,
            unused_data,
            unknown_args,
        )

    def _translate_empty_scope_references(self, data: Any, recover: bool = False) -> Any:
        """Translate references for empty scope configuration.

        When config has an empty scope, user references like "::field"
        need to be translated to "::::field" internally to properly
        reference the empty scope namespace.

        Parameters
        ----------
        data : Any
            The data structure to translate references in.

        Returns
        -------
        Any
            Data with translated references.
        """
        if isinstance(data, str):
            if recover:
                if data.startswith(DUAL_REFERENCE_SEPARATOR):
                    return data[len(REFERENCE_SEPARATOR) :]
            else:
                if data.startswith(REFERENCE_SEPARATOR):
                    if not data.startswith(DUAL_REFERENCE_SEPARATOR):
                        return REFERENCE_SEPARATOR + data
            return data
        elif isinstance(data, dict):
            return {
                k: self._translate_empty_scope_references(v, recover=recover)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._translate_empty_scope_references(item, recover=recover) for item in data]
        else:
            return data

    def _resolve_and_factory(self, data: Dict[str, Any]) -> ResolutionNode:
        """Resolve references and apply factories iteratively.

        Implements the two-phase iterative process from DESIGN.md using
        the new node-based architecture:
        - Initialize ResolutionState with node tree
        - Apply factories to nodes without references
        - Resolve references one-by-one in dependency order
        - Iterate until complete

        Parameters
        ----------
        data : Dict[str, Any]
            Universal data structure.

        Returns
        -------
        ResolutionNode
            The root node containing the final resolved data.
        """
        # Initialize resolution state with dependency graph
        # This will detect circular references immediately
        self._logger.debug("Built dependency graph with topological sorting")
        state = ResolutionState(
            data=data,
            configs={scope: cls for scope, (cls, _) in self._configs.items()},
            type_system=self._type_system,
        )

        # Get the pre-computed resolution queue
        queue = state.get_resolution_queue()

        self._logger.debug(f"Processing {len(queue)} nodes in topological order")
        # Single-pass processing in topological order
        for node in queue:
            if node.is_reference:
                # Resolve reference
                self._logger.debug(f"Processing {node.name} -> {node.reference}")
                state.resolve_reference(node=node)
            else:
                # Apply factory
                self._logger.debug(f"Processing factory application for {node.name}")
                state.apply_factory(node=node)

        # Return the root node which contains the final resolved data
        return state.root

    def dump_defaults(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Dump default values for all registered configs.

        Parameters
        ----------
        path : Optional[str], default: None
            If provided, dumps the defaults to the specified file path.

        Returns
        -------
        Dict[str, Any]
            Default values with "MISSING" for required fields.
        """
        result = {}

        for scope, (cls, _) in self._configs.items():
            defaults = self._type_system.serialize_defaults(cls)
            if scope:
                result[scope] = defaults
            else:
                result = defaults

        if path:
            if path.endswith(("yaml", "yml")):
                dumps_to_yaml(result, path)
            elif path.endswith((".json", ".jsonl")):
                dumps_to_json(result, path)
            else:
                raise ValueError("Path must end with .yaml, .yml, .json, or .jsonl")

        return result
