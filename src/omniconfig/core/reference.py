"""OmniConfig Reference Utilities"""

from typing import Any, Iterable, Union

__all__ = [
    "REFERENCE_SEPARATOR",
    "is_reference_format",
    "is_reference_str",
    "path_to_reference",
]


REFERENCE_SEPARATOR = "::"


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
