"""CLI argument parsing for OmniConfig."""

import argparse
import json
from collections import defaultdict
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Type, Union, get_origin

from ..core.exceptions import ConfigError, ConfigParseError
from ..core.reference import is_reference_format, path_to_reference
from ..core.types import _GLOBAL_TYPE_SYSTEM, TypeCategory, TypeSystem

__all__ = ["CLIParser"]


class CLIParser:
    """Handles CLI argument parsing for configclasses."""

    def __init__(
        self,
        parser: Optional[argparse.ArgumentParser] = None,
        keep_flag_underscores: bool = False,
        keep_private_flag_underscores: bool = True,
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
    ):
        """Initialize CLI parser.

        Parameters
        ----------
        parser : Optional[argparse.ArgumentParser], default: None
            Existing parser to use, or None to create new one.
        keep_flag_underscores : bool, default: False
            If True, keeps underscores in the flag name.
            If False, converts all underscores to hyphens.
        keep_private_flag_underscores : bool, default: True
            If True, keeps underscores for private flags
            (starting with a single underscore).
        """
        parser = parser or argparse.ArgumentParser()
        self._parser = parser
        self._type_system = type_system
        self._keep_flag_underscores = keep_flag_underscores
        self._keep_private_flag_underscores = keep_private_flag_underscores
        self._field_map: Dict[str, Tuple[str, Tuple[str, ...], Dict[TypeCategory, Set[Any]]]] = {}
        self._depth_map: Dict[int, List[str]] = defaultdict(list)
        self._flag_name_sep = "-" if "-" in parser.prefix_chars else parser.prefix_chars[0]
        self._flag_prefix = self._flag_name_sep * 2

    def add_config(
        self,
        cls: Type,
        /,
        scope: str,
        flag_name: Optional[str] = None,
        help: str = "",
    ) -> None:
        """Add a configclass to the parser.

        Parameters
        ----------
        cls : Type
            Dataclass to add.
        scope : str
            Scope for the dataclass.
        flag_name : Optional[str], default: None
            Flag name for CLI arguments.
            If None, uses scope as flag name.
        help : str, default: ""
            Help message for the configclass.
        """
        if flag_name is None:
            flag_name = scope

        # Add reference flag if flag is not empty
        if flag_name:
            cli_dest = scope
            flag_name = format_cli_flag_name(
                flag_name,
                keep_underscores=self._keep_flag_underscores,
                keep_private_underscores=self._keep_private_flag_underscores,
            )
            help_msg = f"Scope {scope} ({cls.__name__})"
            help = f"{help} ({help_msg})" if help else help_msg
            self._parser.add_argument(
                f"{self._flag_prefix}{flag_name}",
                type=str,
                nargs="*",
                dest=cli_dest,
                default=argparse.SUPPRESS,
                help=help,
            )
            if cli_dest in self._field_map:
                raise ConfigError(f"Scope destination '{cli_dest}' is already registered.")
            self._field_map[cli_dest] = (
                flag_name,
                (scope,),
                {TypeCategory.DATACLASS: {cls}},
            )
            self._depth_map[0].append(cli_dest)

        # Add arguments for fields
        self._add_fields_to_parser(
            cls, dest_prefix=scope, flag_name_prefix=flag_name, path=(scope,)
        )

    def _add_fields_to_parser(
        self, cls: Any, dest_prefix: str, flag_name_prefix: str, path: Tuple[str, ...]
    ) -> None:
        """Recursively add fields to argument parser.

        Parameters
        ----------
        cls : Any
            Dataclass type.
        dest_prefix : str
            Prefix for argument destination.
        flag_name_prefix : str
            Prefix for argument flag name.
        path : List[str]
            Path to the current field in the config hierarchy.
        """
        for field in self._type_system.scan(cls).values():
            if not field.init or field.metadata.get("suppress", False):
                continue

            field_path = path + (field.name,)

            field_flag_name = field.metadata.get("flag_name", field.name)
            flag_name = format_cli_flag_name(
                field_flag_name,
                flag_name_prefix=flag_name_prefix,
                flag_name_sep=self._flag_name_sep,
                keep_underscores=self._keep_flag_underscores,
                keep_private_underscores=self._keep_private_flag_underscores,
            )
            cli_dest = format_cli_dest(field.name, dest_prefix=dest_prefix)

            if cli_dest in self._field_map:
                raise ConfigError(
                    format_cli_error_message(
                        f"Destination '{cli_dest}' is already registered.",
                        action="adding",
                        flag=flag_name,
                        path=field_path,
                    )
                )
            cli_help = format_cli_help_message(field.docstring, path=field_path, type=field.type)

            # Get type category
            buckets = field.type_hint_buckets
            if (
                TypeCategory.CONTAINER in buckets
                or len(buckets.get(TypeCategory.DATACLASS, set())) > 1
            ):
                if not field_flag_name:
                    raise ConfigError(
                        format_cli_error_message(
                            f"Container field ('{field.name}' in '{cls.__name__})"
                            " must have a non-empty flag name.",
                            action="adding",
                            path=field_path,
                        )
                    )
                self._parser.add_argument(
                    f"{self._flag_prefix}{flag_name}",
                    type=str,
                    nargs="*",
                    dest=cli_dest,
                    default=argparse.SUPPRESS,
                    help=cli_help,
                )
                self._field_map[cli_dest] = (flag_name, field_path, buckets)
                self._depth_map[len(field_path)].append(cli_dest)

            elif TypeCategory.DATACLASS in buckets:
                if field_flag_name:
                    self._parser.add_argument(
                        f"{self._flag_prefix}{flag_name}",
                        type=str,
                        nargs="*",
                        dest=cli_dest,
                        default=argparse.SUPPRESS,
                        help=cli_help,
                    )
                    self._field_map[cli_dest] = (flag_name, field_path, buckets)
                    self._depth_map[len(field_path)].append(cli_dest)

                # Recursively add nested fields
                self._add_fields_to_parser(
                    next(iter(buckets[TypeCategory.DATACLASS])),
                    dest_prefix=cli_dest,
                    flag_name_prefix=flag_name,
                    path=field_path,
                )

            else:
                # Primitive types
                self._parser.add_argument(
                    f"{self._flag_prefix}{flag_name}",
                    type=str,
                    dest=cli_dest,
                    default=argparse.SUPPRESS,
                    help=cli_help,
                )
                self._field_map[cli_dest] = (flag_name, field_path, buckets)
                self._depth_map[len(field_path)].append(cli_dest)

    def parse_namespace(
        self, namespace: argparse.Namespace, remove_parsed: bool = True
    ) -> Dict[str, Any]:
        """Convert parsed namespace to universal data structure.

        Parameters
        ----------
        namespace : argparse.Namespace
            Parsed arguments.
        remove_parsed : bool, default: True
            If True, remove parsed attributes from namespace.

        Returns
        -------
        Dict[str, Any]
            Universal data structure.
        """
        result = {}
        for depth in sorted(self._depth_map.keys()):
            for dest in self._depth_map[depth]:
                flag_name, field_path, flat_type_map = self._field_map[dest]
                if hasattr(namespace, dest):
                    value = getattr(namespace, dest)
                    field_flag = f"{self._flag_prefix}{flag_name}"
                    if isinstance(value, str):
                        value = parse_cli_value(value)
                    else:
                        allow_list = TypeCategory.CONTAINER in flat_type_map and any(
                            get_origin(t) in (list, List, set, Set, tuple, Tuple)
                            for t in flat_type_map[TypeCategory.CONTAINER]
                        )
                        value = parse_cli_values(
                            value, allow_list=allow_list, flag=field_flag, path=field_path
                        )
                        if (
                            isinstance(value, list)
                            and len(value) == 1
                            and TypeCategory.PRIMITIVE in flat_type_map
                            and type(value[0]) in flat_type_map[TypeCategory.PRIMITIVE]
                        ):
                            value = value[0]
                    prev, current = {}, result
                    for part in field_path[:-1]:
                        if part not in current:
                            current[part] = {}
                        prev = current
                        current = current[part]
                    if isinstance(current, str):
                        if not is_reference_format(current):
                            raise ConfigParseError(
                                format_cli_error_message(
                                    f"Invalid reference string {current}",
                                    flag=field_flag,
                                    path=field_path,
                                )
                            )
                        current = {"_reference_": current}
                        prev[part] = current
                    if not isinstance(current, dict):
                        raise ConfigParseError(
                            format_cli_error_message(
                                f"Expected Dict, got {type(current)}",
                                flag=field_flag,
                                path=field_path,
                            )
                        )
                    current[field_path[-1]] = value  # type: ignore
                    if remove_parsed:
                        delattr(namespace, dest)
        return result


def format_cli_flag_name(
    flag_name: str,
    flag_name_prefix: str = "",
    flag_name_sep: str = "-",
    keep_underscores: bool = False,
    keep_private_underscores: bool = True,
) -> str:
    """Convert field flag name to CLI argument flag.

    Rules:
    - Flag must start with a letter or single underscore
    - Only single leading underscore is allowed (for private flags)
    - All letters are converted to lowercase
    - Empty flag returns empty string
    - If prefix is provided, it is added before the flag name

    Parameters
    ----------
    flag_name : str
        Flag name (e.g., "my_FLAG" or "_private").
    flag_name_prefix : str, default: ""
        Prefix to add before the flag name.
    flag_name_sep : str, default: "-"
        Separator to use between flag name prefix and flag name.
    keep_underscores : bool, default: False
        If True, keeps underscores in the flag name.
        If False, converts all underscores to hyphens.
    keep_private_underscores : bool, default: True
        If True, keeps underscores for private flags
        (starting with a single underscore).

    Returns
    -------
    str
        CLI argument flag name (e.g., "my-flag" or "_private_flag").

    Raises
    ------
    ValueError
        If flag name is invalid.
    """
    if not flag_name:
        return ""
    flag_name = flag_name.strip().lower()
    if flag_name.startswith("_"):  # Private flag
        if len(flag_name) == 1:
            raise ConfigError(f"Flag name cannot be just underscore: {flag_name}")
        if not flag_name[1].isalpha():
            raise ConfigError(f"After underscore, flag must start with a letter: {flag_name}")
        if not keep_underscores and not keep_private_underscores:
            # Convert all underscores to hyphens
            flag_name = flag_name.replace("_", "-")
    else:
        # Must start with letter
        if not flag_name[0].isalpha():
            raise ConfigError(
                f"Flag name must start with a letter or single underscore: {flag_name}"
            )
        if not keep_underscores:
            # Convert all underscores to hyphens
            flag_name = flag_name.replace("_", "-")
    return f"{flag_name_prefix}{flag_name_sep}{flag_name}" if flag_name_prefix else flag_name


def format_cli_dest(dest: str, dest_prefix: str = "") -> str:
    """Convert field destination to CLI argument destination.

    Rules:
    - Must be a valid Python identifier
    - Empty destination returns empty string
    - If prefix is provided, it is added before the destination

    Parameters
    ----------
    dest : str
        Destination name.
    dest_prefix : str, default: ""
        Prefix to add before the destination.

    Returns
    -------
    str
        CLI argument destination name.
    """
    if not dest:
        return ""
    return f"{dest_prefix}_{dest}" if dest_prefix else dest


def format_cli_help_message(message: str, path: Tuple[str, ...], type: Any) -> str:
    """Format a help message for CLI argument parsing.

    Parameters
    ----------
    message : str
        The message to include in the help text.
    path : Tuple[str, ...]
        The path to the field to include in the message.
    type : Any
        The type to include in the message.

    Returns
    -------
    str
        Formatted help message.
    """
    s = f"Field '{path_to_reference(path)}' ({type})"
    if message:
        s += f": {message}"
    return s


def format_cli_error_message(
    message: str,
    action: Literal["adding", "parsing"] = "parsing",
    flag: Optional[str] = None,
    path: Optional[Tuple[Union[str, int], ...]] = None,
) -> str:
    """Format an error message for CLI argument parsing.

    Parameters
    ----------
    message : str
        The error message to format.
    action : Literal["adding", "parsing"], default: "parsing"
        The action being performed.
    flag : Optional[str], default: None
        The flag name to include in the message.
    path : Optional[Tuple[Union[str, int], ...]], default: None
        The path to the field to include in the message.

    Returns
    -------
    str
        Formatted error message.
    """
    s = f"Error {action} CLI arguments"
    if flag:
        s += f" of flag '{flag}'"
    if path:
        s += f" for field '{path_to_reference(path)}'"
    s += f": {message}"
    return s


def is_integer_key(key: str) -> bool:
    """Check if a string represents an integer key for dict indexing.

    Parameters
    ----------
    key : str
        String to check.

    Returns
    -------
    bool
        True if the string represents a valid integer.
    """
    # Handle positive integers (including those with leading zeros)
    if key.isdigit():
        return True
    # Handle negative integers
    if key.startswith("-") and len(key) > 1 and key[1:].isdigit():
        return True
    return False


def try_container_json_syntax(
    value: str, flag: Optional[str] = None, path: Optional[Tuple[Union[str, int], ...]] = None
) -> Tuple[Any, bool]:
    """Try to parse a string as JSON container syntax.

    Parameters
    ----------
    value : str
        String to parse.
    flag : Optional[str], default: None
        Flag name for error messages.
        Only used for formatting errors.
    path : Optional[Tuple[Union[str, int], ...]], default: None
        Path to the field for error messages.
        Only used for formatting errors.

    Returns
    -------
    Tuple[Any, bool]
        Parsed value and success flag.
        If parsing fails, returns original string and False.
    """
    if not (
        (value.startswith("{") and value.endswith("}"))
        or (value.startswith("[") and value.endswith("]"))
    ):
        return value, False
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            parsed["_overwrite_"] = True
        elif not isinstance(parsed, list):
            raise ConfigParseError(
                format_cli_error_message(
                    f"Invalid JSON container syntax '{value}'", flag=flag, path=path
                )
            )
        return parsed, True
    except (json.JSONDecodeError, TypeError):
        return value, False


def parse_cli_value(value: str) -> Any:
    """Parse a single CLI value as JSON if possible.

    This allows users to control types explicitly:
    - '128' -> 128 (int)
    - '"128"' -> "128" (str)
    - '3.14' -> 3.14 (float)
    - 'true' -> True (bool)
    - 'none' -> None (NoneType)
    - 'null' -> None (NoneType)
    - 'hello' -> "hello" (str, not valid JSON)

    Parameters
    ----------
    value : str
        The CLI value to parse.

    Returns
    -------
    Any
        Parsed value with appropriate type.
    """
    # Handle reference string
    if is_reference_format(value):
        return value
    # Special cases
    _value = value.lower()
    if _value == "none":
        return None
    elif _value == "true":
        return True
    elif _value == "false":
        return False
    try:
        # Try parsing as JSON
        # e.g., "128" -> 128, '"128"' -> "128", "null" -> None.
        return json.loads(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        # Not valid JSON, keep as string
        return value


def parse_cli_values(  # noqa: C901
    values: List[str],
    allow_list: bool,
    flag: Optional[str] = None,
    path: Optional[Tuple[Union[str, int], ...]] = None,
) -> Union[str, List[Any], Dict[Union[str, int], Any]]:
    """Parse a list of CLI arguments into a nested dictionary or list.

    Parameters
    ----------
    values : List[str]
        List of CLI arguments.
    allow_list : bool
        Whether to allow returning a list.
    flag : Optional[str], default: None
        Flag name for error messages.
    path : Optional[Tuple[Union[str, int], ...]], default: None
        Path to the field for error messages.

    Returns
    -------
    Union[str,List[Any], Dict[Union[str, int], Any]]
        Parsed result as a reference string, a list or dictionary.
    """

    def err_msg(msg: str) -> str:
        """Format error message for CLI parsing."""
        return format_cli_error_message(msg, action="parsing", flag=flag, path=path)

    num_pairs: int = 0
    content: List[Any] = []
    updates: Dict[Union[str, int], Any] = {}
    relpaths: List[List[Union[str, int]]] = []
    references: List[str] = []
    overwrite: Optional[Union[List, Dict]] = None
    duplicate_keys: List[str] = []
    for item in values:
        if is_reference_format(item):
            # Reference string
            references.append(item)
            continue
        # Try to parse as JSON container syntax
        value, success = try_container_json_syntax(item, flag=flag, path=path)
        if success:
            if overwrite is not None:
                raise ConfigParseError(err_msg("Multiple JSON container syntax found."))
            overwrite = value
            continue
        if "=" in item:  # Possible key-value pair
            # Try regular key-value pair
            key, value = item.split("=", 1)
            parts = key.split(".")
            subpath = []
            current = updates
            for part in parts[:-1]:
                part = int(part) if is_integer_key(part) else part
                subpath.append(part)
                current = current.setdefault(part, {})
            part = parts[-1]
            part = int(part) if is_integer_key(part) else part
            subpath.append(part)
            if part in current:
                duplicate_keys.append(key)
            relpaths.append(subpath)
            value, success = try_container_json_syntax(value, flag=flag, path=path)
            if not success:
                value = parse_cli_value(value)
            current[part] = value
            num_pairs += 1
        content.append(parse_cli_value(item))
    if len(references) == len(values):
        # If all were references, no JSON container or key-value pairs
        if len(references) == 1:
            return references[0]
        if not allow_list:
            raise ConfigParseError(err_msg("Multiple reference strings not allowed here."))
        return references
    if overwrite is not None:
        if references:
            raise ConfigParseError(
                err_msg(
                    "Cannot have both reference and JSON container. Write reference inside JSON."
                )
            )
        if num_pairs + 1 != len(values):
            raise ConfigParseError(err_msg("Cannot have both JSON container and non key=value."))
        if duplicate_keys:
            raise ConfigParseError(
                err_msg(f"Duplicate keys found in JSON container: {', '.join(duplicate_keys)}")
            )
        for relpath in relpaths:
            if relpath[0] == "_overwrite_":
                raise ConfigParseError(
                    err_msg("Cannot use '_overwrite_' as a key if JSON container is used.")
                )
            source, target = updates, overwrite
            for part in relpath[:-1]:
                source = source[part]
                if isinstance(target, list):
                    if not isinstance(part, int):
                        raise ConfigParseError(
                            err_msg(f"Cannot use non-integer key '{part}' to update list.")
                        )
                    if part >= len(target):
                        raise ConfigParseError(err_msg(f"Index {part} out of range for list"))
                    target = target[part]
                elif isinstance(target, dict):
                    target = target.setdefault(part, {})
                else:
                    raise ConfigParseError(
                        err_msg(f"Cannot update non-container: {type(target)} with key '{part}'")
                    )
            part = relpath[-1]
            if isinstance(target, list):
                if not isinstance(part, int):
                    raise ConfigParseError(
                        err_msg("Cannot use non-integer keys if JSON list is used.")
                    )
                if part >= len(target):
                    raise ConfigParseError(err_msg(f"Index {part} out of range for list"))
                target[part] = source[part]
            elif isinstance(target, dict):
                target[part] = source[part]
            else:
                raise ConfigParseError(
                    err_msg(f"Cannot update non-container: {type(target)} with key '{part}'")
                )
        return overwrite
    if references:
        if len(references) > 1 or "_reference_" in updates:
            raise ConfigParseError(err_msg("Multiple reference strings found."))
        if num_pairs + 1 != len(values):
            raise ConfigParseError(err_msg("Cannot have both reference and non key=value."))
        if duplicate_keys:
            raise ConfigParseError(
                err_msg(f"Duplicate keys found in JSON container: {', '.join(duplicate_keys)}")
            )
        if num_pairs == 0:
            return references[0]
        updates["_reference_"] = references[0]
        return updates
    if num_pairs == len(values):
        # If all values were key-value pairs, return as dict
        if duplicate_keys:
            raise ConfigParseError(
                err_msg(f"Duplicate keys found in key-value pairs: {', '.join(duplicate_keys)}")
            )
        return updates
    if not allow_list:
        if len(content) > 1:
            raise ConfigParseError(err_msg("Multiple values not allowed here."))
        return content[0]
    # Otherwise return as list
    return content
