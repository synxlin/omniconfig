"""Type registry for custom types in OmniConfig."""

from typing import Any, Callable, Type, TypeVar, Union

from .core.types import _GLOBAL_TYPE_SYSTEM, TypeInfo

__all__ = ["OmniConfig"]


T = TypeVar("T")


class OmniConfig:
    """Main class for global OmniConfig operations."""

    @classmethod
    def register_type(
        cls,
        type_: Type,
        type_hint: Any,
        factory: Callable[[Any], Any],
        reducer: Callable[[Any], Any],
    ) -> None:
        """Register a custom type globally.

        Parameters
        ----------
        type_ : Type
            The custom type to register.
        type_hint : Any
            The type hint to use for parsing.
        factory : Callable[[Any], Any]
            Function to convert from type_hint to type_.
        reducer : Callable[[Any], Any]
            Function to convert from type_ to type_hint.
        """
        _GLOBAL_TYPE_SYSTEM.register(type_, type_hint, factory, reducer)

    @classmethod
    def is_type_registered(cls, type_: Type) -> bool:
        """Check if a type is registered globally.

        Parameters
        ----------
        type_ : Type
            The type to check.

        Returns
        -------
        bool
            True if the type is registered.
        """
        return _GLOBAL_TYPE_SYSTEM.is_registered(type_)

    @classmethod
    def get_type_info(cls, type_: Any, default: T = None) -> Union[TypeInfo, T]:
        """Get registered information for a type.

        Parameters
        ----------
        type_ : Type
            The type to look up.
        default : T, default: None
            Default value to return if type is not registered.

        Returns
        -------
        Union[TypeInfo, T]
            Type information if registered, or default value.
        """
        return _GLOBAL_TYPE_SYSTEM.retrieve(type_, default=default)

    @classmethod
    def clear_type_registry(cls) -> None:
        """Clear all registered types."""
        _GLOBAL_TYPE_SYSTEM.clear()
