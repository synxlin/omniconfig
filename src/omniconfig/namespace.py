"""Main OmniConfigParser implementation."""

from dataclasses import is_dataclass
from types import SimpleNamespace
from typing import Any, TypeVar, Union

T = TypeVar("T")


class OmniConfigNamespace(SimpleNamespace):
    """Namespace for holding configuration objects."""

    def __contains__(self, name: str) -> bool:
        """Check if configuration exists.

        Parameters
        ----------
        name : str
            Configuration name.

        Returns
        -------
        bool
            True if configuration exists.
        """
        return name in self.__dict__

    def __getitem__(self, name: str) -> Any:
        """Get configuration by index access.

        Parameters
        ----------
        name : str
            Configuration name.

        Returns
        -------
        Any
            Configuration object.
        """
        return self.__dict__[name]

    def __setitem__(self, name: str, value: Any) -> None:
        """Set configuration by index access.

        Parameters
        ----------
        name : str
            Configuration name.
        value : Any
            Configuration value.
        """
        if not name and not is_dataclass(value):
            raise ValueError("Root configuration must be a dataclass instance.")
        self.__dict__[name] = value

    def get(self, name: str = "", default: T = None) -> Union[Any, T]:
        """Get configuration by name.

        Parameters
        ----------
        name : str, default: ""
            Configuration name. Defaults to "" (root configuration).
        default : T, default: None
            Default value if configuration does not exist.

        Returns
        -------
        Union[Any, T]
            Configuration object or default value.
        """
        return self.__dict__.get(name, default)
