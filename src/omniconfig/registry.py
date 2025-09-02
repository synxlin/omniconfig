"""Type registry for custom types in OmniConfig."""

import json
from dataclasses import is_dataclass
from typing import Any, Callable, Optional, Sequence, Type, TypeVar, Union

import yaml

from .core.reference import translate_empty_scope_references
from .core.registry import _ALIAS_REGISTRY, _VALUE_REGISTRY, register, register_alias, retrieve
from .core.types import _GLOBAL_TYPE_SYSTEM, TypeInfo, TypeSystem
from .parsing.file_loader import FileLoader
from .resolution.reducer import ReducerSystem
from .resolution.state import ResolutionState

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
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
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
        type_system.register(type_, type_hint, factory, reducer)

    @staticmethod
    def is_type_registered(type_: Type, type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM) -> bool:
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
        return type_system.is_registered(type_)

    @staticmethod
    def retrieve_type_info(
        type_: Any, default: T = None, type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM
    ) -> Union[TypeInfo, T]:
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
        return type_system.retrieve(type_, default=default)

    @staticmethod
    def clear_type_registry(type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM) -> None:
        """Clear all registered types."""
        type_system.clear()

    @staticmethod
    def serialize(
        obj: Any, datacls: Optional[type[T]] = None, type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM
    ) -> Any:
        """Serialize an dataclass instance.

        Parameters
        ----------
        obj : Any
            The object to serialize.
        datacls : Optional[type[T]]
            The dataclass type to use for serialization.

        Returns
        -------
        Any
            The serialized object.
        """
        if datacls is None:
            if not is_dataclass(obj) or isinstance(obj, type):
                raise TypeError("Invalid dataclass instance")
            return ReducerSystem.apply(obj, type_system=type_system)
        else:
            if not isinstance(datacls, type) or not is_dataclass(datacls):
                raise TypeError("Invalid dataclass type")
            if not isinstance(obj, datacls):
                raise TypeError("Invalid dataclass instance")
            return ReducerSystem.apply(
                obj, type_info=type_system.retrieve(datacls, None), type_system=type_system
            )

    @staticmethod
    def deserialize(
        datacls: type[T],
        /,
        data: Union[str, dict[str, Any]],
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
    ) -> T:
        """Create an instance of a dataclass from a data dictionary.

        Parameters
        ----------
        datacls : type[T]
            The dataclass type to instantiate.
        data : Union[str, dict[str, Any]]
            The data to use for instantiation,
            either as a JSON/YAML string
            or a dictionary parsed from such a string.

        Returns
        -------
        T
            An instance of the dataclass.
        """
        if not isinstance(datacls, type) or not is_dataclass(datacls):
            raise TypeError("Invalid dataclass type")
        if isinstance(data, str):
            try:
                data = FileLoader().load_file(data)
            except Exception:
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    try:
                        data = yaml.safe_load(data)
                    except yaml.YAMLError:
                        raise ValueError("Invalid YAML or JSON data string") from None
        if not isinstance(data, dict):
            raise ValueError("Invalid data format")
        data = translate_empty_scope_references(data)
        state = ResolutionState(data={"": data}, configs={"": datacls}, type_system=type_system)
        node = state.resolve_and_factory().root
        assert isinstance(node.content, dict)
        return node.content[""].value

    @staticmethod
    def serialize_defaults(datacls: type[T], type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM) -> Any:
        """Serialize default values for a dataclass.

        Parameters
        ----------
        datacls : type[T]
            The dataclass type to serialize defaults for.

        Returns
        -------
        Dict[str, Any]
            Dictionary with field names and their default values.
        """
        if not isinstance(datacls, type) or not is_dataclass(datacls):
            raise TypeError("Invalid dataclass type")
        return ReducerSystem.apply_for_defaults(datacls, type_system=type_system)


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
        _VALUE_REGISTRY.clear()
        _ALIAS_REGISTRY.clear()
