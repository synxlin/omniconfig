"""OmniConfig Reference Utilities"""

from typing import Any, Iterable, Union

__all__ = [
    "REFERENCE_SEPARATOR",
    "is_reference_format",
    "is_reference_str",
    "path_to_reference",
    "translate_empty_scope_references",
]


REFERENCE_SEPARATOR = "::"
DUAL_REFERENCE_SEPARATOR = REFERENCE_SEPARATOR + REFERENCE_SEPARATOR


def is_reference_format(value: str) -> bool:
    """Check if a string is in reference format.

    Parameters
    ----------
    value : str
        String to check.

    Returns
    -------
    bool
        True if the string is in reference format.
    """
    return value.startswith(REFERENCE_SEPARATOR)


def is_reference_str(value: Any) -> bool:
    """Check if a value is a reference string.

    Parameters
    ----------
    value : Any
        Value to check.

    Returns
    -------
    bool
        True if value is a reference string.
    """
    return isinstance(value, str) and is_reference_format(value)


def path_to_reference(path: Iterable[Union[str, int]]) -> str:
    """Build a reference string from path components.

    Parameters
    ----------
    path : Iterable[Union[str, int]]
        Path components.

    Returns
    -------
    str
        Reference string.
    """
    if not path:
        return ""
    return REFERENCE_SEPARATOR + REFERENCE_SEPARATOR.join(map(str, path))


def translate_empty_scope_references(data: Any, recover: bool = False) -> Any:
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
        return {k: translate_empty_scope_references(v, recover=recover) for k, v in data.items()}
    elif isinstance(data, list):
        return [translate_empty_scope_references(item, recover=recover) for item in data]
    else:
        return data
