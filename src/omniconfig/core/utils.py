# -*- coding: utf-8 -*-
"""Utilities for omniconfig."""

import json
import re
from dataclasses import (
    _FIELD,  # type: ignore
    _FIELD_INITVAR,  # type: ignore
    _FIELDS,  # type: ignore
    Field,
    is_dataclass,
)
from typing import Any, Dict, Optional, Tuple

import docstring_parser
import yaml

__all__ = ["get_fields", "get_fields_docstrings", "dumps_to_yaml", "dumps_to_json"]


def get_fields(
    cls: Any, /, init_only: bool = True, exclude_pseudo: bool = False
) -> Tuple[Field, ...]:
    """Get all fields of a config dataclass.

    Parameters
    ----------
    cls : Any
        dataclass type to inspect.
    init_only : bool, optional
        If True, only return fields that are required for init.
    exclude_pseudo : bool, optional
        If True, exclude pseudo-fields (fields that are
            not part of the dataclass but are used for initialization).

    Returns
    -------
    tuple[Field, ...]
        The fields of the config dataclass.
    """
    if not is_dataclass(cls):
        raise ValueError(f"{cls.__name__} is not a dataclass")
    fields = tuple(getattr(cls, _FIELDS).values())
    if exclude_pseudo:
        fields = tuple(f for f in fields if f._field_type is _FIELD)
    else:
        fields = tuple(f for f in fields if f._field_type in (_FIELD, _FIELD_INITVAR))
    if init_only:
        return tuple(f for f in fields if f.init)
    return fields


_DEFAULT_REGEX = re.compile(
    r"""
            ([,\.]?)                                    # Preceding punctuation
            \s*
            (?:
                [Dd]efault(?:\s+is|\s*=|\s*:|\s+to)
                |[Bb]y\s+default
                |[Dd]efaults\s+to
            )
            .*                                          # Rest of the line
        """,
    re.VERBOSE | re.DOTALL,
)


def _remove_default_statement(text: str) -> str:
    """Remove default statements from a docstring.

    This function removes default statements from a docstring, which are
    typically phrases like "Default is 10" or "By default, True".
    It handles various punctuation and spacing issues to ensure
    the resulting text is clean.

    Parameters
    ----------
    text : str
        The docstring text to process.

    Returns
    -------
    str
        The processed docstring with default statements removed.
    """

    lines = text.split("\n")
    result_lines = []

    for line in lines:
        # Check if this line contains a default statement

        # match = re.search(pattern, line, re.VERBOSE)
        match = _DEFAULT_REGEX.search(line)
        if match:
            # Get everything before the default statement
            before = line[: match.start()]
            preceding_punct = match.group(1) if match.group(1) else ""

            # Add period if there was punctuation
            if preceding_punct and before:
                before = before.rstrip() + "."
            elif before.strip():
                before = before.rstrip() + "."

            if before.strip():
                result_lines.append(before)
            # Don't add anything after - we're removing it all
        else:
            result_lines.append(line)

    return "\n".join(result_lines)


def get_fields_docstrings(cls: Any) -> dict[str, str]:
    """Extract all field docstrings from a dataclass.

    Parameters
    ----------
    cls : Any
        The dataclass type to inspect.

    Returns
    -------
    dict[str, str]
        A dictionary mapping field names to their docstrings.
    """
    fields = get_fields(cls, init_only=False, exclude_pseudo=False)
    if cls.__doc__:
        docs = docstring_parser.parse(cls.__doc__)
        # we first go through args
        param_docs: dict[str, str] = {}
        for param in docs.params:
            if param.args and param.args[0] == "param":
                field_name = param.arg_name
                field_doc = param.description if param.description else ""
                field_doc = _remove_default_statement(field_doc)
                if field_name and field_name in fields:
                    if field_name in param_docs:
                        raise RuntimeError(
                            f"Duplicate Parameter {field_name} in {cls.__name__} docstring"
                        )
                    param_docs[field_name] = field_doc
        # then we go through attributes
        attr_docs: Dict[str, str] = {}
        for param in docs.params:
            if param.args and param.args[0] == "attribute":
                field_name = param.arg_name
                field_doc = param.description if param.description else ""
                field_doc = _remove_default_statement(field_doc)
                if field_name and field_name in fields:
                    if field_name in attr_docs:
                        raise RuntimeError(
                            f"Duplicate Attribute {field_name} in {cls.__name__} docstring"
                        )
                    attr_docs[field_name] = field_doc
        # then we update the field docs
        attr_docs.update(param_docs)
        return attr_docs
    return {}


def dumps_to_yaml(data: Any, path: Optional[str] = None) -> str:
    """Dump data to YAML format.

    Parameters
    ----------
    data : Any
        Data to dump.
    path : Optional[Union[str, Path]]
        If provided, write to file.

    Returns
    -------
    str
        YAML string.
    """
    s = yaml.dump(data, default_flow_style=False, sort_keys=False)
    if path:
        if not path.endswith((".yaml", ".yml")):
            raise ValueError("Path must end with .yaml or .yml")
        with open(path, "w") as f:
            f.write(s)
    return s


def dumps_to_json(data: Any, path: Optional[str] = None, indent: int = 2) -> str:
    """Dump data to JSON format.

    Parameters
    ----------
    data : Any
        Data to dump.
    path : Optional[Union[str, Path]]
        If provided, write to file.
    indent : int, optional
        Indentation level for JSON output.

    Returns
    -------
    str
        JSON string.
    """
    s = json.dumps(data, indent=indent)
    if path:
        if not path.endswith((".json", ".jsonl")):
            raise ValueError("Path must end with .json or .jsonl")
        with open(path, "w") as f:
            f.write(s)
    return s
