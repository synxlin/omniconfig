"""Configuration merging for node-based resolution.

This module handles merging configurations from multiple sources
in the node-based architecture.
"""

import copy
from typing import Any, Dict, Tuple, Union

from ..core.exceptions import ConfigParseError
from ..core.reference import is_reference_format, path_to_reference

__all__ = ["ConfigMerger"]


class ConfigMerger:
    """Class for merging configuration dictionaries.

    This class provides methods to merge multiple configuration
    dictionaries, handling special cases like references and
    overwrites.
    """

    @staticmethod
    def merge(*configs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple configuration dictionaries.

        Later configs have higher priority and override earlier ones.
        Special handling for:
        - _overwrite_ flag: replaces entire value
        - _reference_ field: treated as replacement

        Parameters
        ----------
        *configs : Dict[str, Any]
            Configuration dictionaries to merge, in priority order.

        Returns
        -------
        Dict[str, Any]
            The merged configuration.
        """
        if not configs:
            return {}

        if len(configs) == 1:
            return copy.deepcopy(configs[0])

        result = {}
        for config in configs:
            if config:
                result = ConfigMerger._merge(result, config, path=())
        return result

    @staticmethod
    def _merge(base_value: Any, override_value: Any, path: Tuple[Union[str, int], ...]) -> Any:
        """Merge two values based on their types.

        Parameters
        ----------
        base_value : Any
            Base value.
        override_value : Any
            Override value.

        Returns
        -------
        Any
            Merged value.
        """
        # If override is a reference string, replace completely
        if isinstance(override_value, str) and is_reference_format(override_value):
            return override_value

        if isinstance(override_value, dict):
            # If override has _reference_ or _overwrite_, replace
            if override_value.get("_overwrite_") or "_reference_" in override_value:
                result = copy.deepcopy(override_value)
                # Remove _overwrite_ flag after using it
                if "_overwrite_" in result:
                    del result["_overwrite_"]
                return result

            # If base is also a dict, merge recursively
            if isinstance(base_value, dict):
                result = copy.deepcopy(base_value)
                for key, value in override_value.items():
                    if key == "_overwrite_":
                        continue
                    if key in result:
                        result[key] = ConfigMerger._merge(result[key], value, path=path + (key,))
                    else:
                        result[key] = copy.deepcopy(value)
                return result

            # If base is a list, update it with override values
            if isinstance(base_value, list):
                result = copy.deepcopy(base_value)
                for key, value in override_value.items():
                    try:
                        key = int(key)
                    except ValueError as e:
                        path_repr = path_to_reference(path)
                        raise ConfigParseError(
                            f"Error merging configs for field {path_repr}:"
                            f" Invalid list key '{key}'"
                        ) from e
                    if key >= len(result):
                        path_repr = path_to_reference(path)
                        raise ConfigParseError(
                            f"Error merging configs for field {path_repr}:"
                            f" List index {key} out of range"
                        )
                    result[key] = ConfigMerger._merge(result[key], value, path=path + (key,))
                return result

        # Otherwise, override replaces base
        return copy.deepcopy(override_value)
