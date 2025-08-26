"""Type registry for custom types in OmniConfig."""

from typing import Any, Callable, Sequence, Type, TypeVar, Union

from .core.registry import _ALIAS_REGISTRY, _GLOBAL_REGISTRY, register, register_alias, retrieve
from .core.types import _GLOBAL_TYPE_SYSTEM, TypeInfo
from .namespace import OmniConfigNamespace

__all__ = ["OmniConfig", "OmniRegistry"]


T = TypeVar("T")


class OmniConfig:
    """Main class for global OmniConfig operations."""

    @staticmethod
    def register_type(
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

    @staticmethod
    def is_type_registered(type_: Type) -> bool:
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

    @staticmethod
    def retrieve_type_info(type_: Any, default: T = None) -> Union[TypeInfo, T]:
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

    @staticmethod
    def clear_type_registry() -> None:
        """Clear all registered types."""
        _GLOBAL_TYPE_SYSTEM.clear()

    @staticmethod
    def serialize(obj: Any) -> Any:
        """Serialize an object."""
        if isinstance(obj, OmniConfigNamespace):
            results = {}
            for scope, value in obj.__dict__.items():
                results[scope] = _GLOBAL_TYPE_SYSTEM.serialize(value)
            if "" in obj.__dict__:
                results = results[""]
            return results
        return _GLOBAL_TYPE_SYSTEM.serialize(obj)


class OmniRegistry:
    @staticmethod
    def register_alias(
        cls: type,  # type: ignore
        /,
        name: str,
        *,
        alias: str | Sequence[str],
        subregistry: str = "",
        overwrite: bool = False,
    ) -> None:
        register_alias(cls, name, alias=alias, subregistry=subregistry, overwrite=overwrite)

    @staticmethod
    def register(
        cls: type,  # type: ignore
        /,
        value: Any,
        name: str = "",
        *,
        alias: str | Sequence[str] = "",
        subregistry: str = "",
        as_fallback: bool = False,
        subclass_only: bool | type = False,
        instance_only: bool | type = False,
        overwrite: bool = False,
    ) -> None:
        register(
            cls,
            value,
            name=name,
            alias=alias,
            subregistry=subregistry,
            as_fallback=as_fallback,
            subclass_only=subclass_only,
            instance_only=instance_only,
            overwrite=overwrite,
        )

    @staticmethod
    def retrieve(
        cls: type,  # type: ignore
        /,
        name: str,
        *,
        subregistry: str = "",
        fallback: bool = False,
        default: T = None,
    ) -> Any | T:
        return retrieve(cls, name, subregistry=subregistry, fallback=fallback, default=default)

    @staticmethod
    def clear_registry() -> None:
        """Clear all registered dataclasses."""
        _GLOBAL_REGISTRY.clear()
        _ALIAS_REGISTRY.clear()
