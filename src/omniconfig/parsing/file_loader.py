"""File loading functionality for OmniConfig."""

import json
import os
from itertools import chain
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Tuple, Union

import yaml

from ..core.exceptions import ConfigParseError

__all__ = ["FileLoader"]


class FileLoader:
    """Handles loading configuration from files."""

    CONFIG_FILE_EXTS: ClassVar[Tuple[str, ...]] = ("yaml", "yml", "json", "jsonl")
    RECIPE_FILE_EXTS: ClassVar[Tuple[str, ...]] = ("recipe",)

    def load_with_defaults(self, files: List[str]) -> List[Dict[str, Any]]:
        """Load configuration files with hierarchical defaults.

        Parameters
        ----------
        config_files : List[str]
            List of configuration files.

        Returns
        -------
        List[Dict[str, Any]]
            List of configurations in loading order.
        """
        config_files: List[str] = []

        # Resolve recipe files
        for file in files:
            if file.endswith(self.RECIPE_FILE_EXTS):
                if not os.path.isfile(file):
                    raise ConfigParseError(f"Recipe file not found: {file}")
                with open(file, "r") as f:
                    for config_file in f.readlines():
                        config_file = config_file.strip()
                        if not os.path.isfile(config_file):
                            raise ConfigParseError(
                                f"Config file in recipe {file} not found: {config_file}"
                            )
                        if not config_file.endswith(self.CONFIG_FILE_EXTS):
                            raise ConfigParseError(
                                f"Unsupported config file in recipe {file}: {config_file}"
                            )
                        config_files.append(config_file)
            elif file.endswith(self.CONFIG_FILE_EXTS):
                if not os.path.isfile(file):
                    raise ConfigParseError(f"Config file not found: {file}")
                config_files.append(file)
            else:
                raise ConfigParseError(f"Unsupported file type: {file}")
        if not config_files:
            raise ConfigParseError("No valid configuration files provided.")

        # Discover default files
        default_files = self.discover_default_files(config_files)

        # Load all files in order
        return [self.load_file(f) for f in chain(default_files, config_files)]

    def discover_default_files(self, files: List[str]) -> List[Path]:
        """Discover default files in directory hierarchy.

        Parameters
        ----------
        config_files : List[str]
            List of configuration files.

        Returns
        -------
        List[Path]
            List of default files to load in order.
        """
        default_files = []
        seen_dirs = set()
        cwd = Path.cwd()

        for file in files:
            path = Path(file).resolve()

            # Check if file is under current directory
            try:
                parts = path.relative_to(cwd).parts[:-1]  # Exclude filename
            except ValueError:
                # File is outside current directory, skip discovery
                continue

            # Collect default files from root to file's directory
            current = cwd
            for part in parts:
                current = current / part
                if current not in seen_dirs:
                    seen_dirs.add(current)
                    # Check for default files
                    for ext in self.CONFIG_FILE_EXTS:
                        default_path = current / f"__default__.{ext}"
                        if default_path.exists() and default_path.is_file():
                            if default_path not in default_files:
                                default_files.append(default_path)
                            break  # Only use first found default file per directory

        return default_files

    def load_file(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Load configuration from a file.

        Parameters
        ----------
        path : Union[str, Path]
            Path to the configuration file.

        Returns
        -------
        Dict[str, Any]
            Loaded configuration.

        Raises
        ------
        ConfigParseError
            If file cannot be loaded or parsed.
        """
        path = Path(path)

        if not path.exists():
            raise ConfigParseError(f"Configuration file not found: {path}")

        if not path.is_file():
            raise ConfigParseError(f"Path is not a file: {path}")

        # Determine file type by extension
        suffix = path.suffix.lower()

        try:
            if suffix in (".yaml", ".yml"):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            elif suffix in (".json", ".jsonl"):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                raise ConfigParseError(
                    f"Unsupported file type: {suffix}."
                    f" Supported types are: {self.CONFIG_FILE_EXTS}"
                )
        except Exception as e:
            raise ConfigParseError(f"Failed to load file {path}: {e}") from e

        if not isinstance(data, dict):
            raise ConfigParseError(
                f"Configuration file must contain a dictionary, got {type(data).__name__}"
            )

        return data
