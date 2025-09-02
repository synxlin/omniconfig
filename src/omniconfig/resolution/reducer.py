# -*- coding: utf-8 -*-
"""Reducer System for serializing objects."""

from dataclasses import MISSING, is_dataclass
from enum import Enum
from types import MappingProxyType, NoneType
from typing import Any, Dict, Optional, Tuple, Type, get_origin

from ..core.exceptions import ConfigReducerError
from ..core.types import _GLOBAL_TYPE_SYSTEM, TypeCategory, TypeInfo, TypeSystem

__all__ = ["ReducerSystem"]


class ReducerSystem:
    @staticmethod
    def apply(
        obj: Any,
        type_info: Optional[TypeInfo] = None,
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
    ) -> Any:
        """Apply the reducer to the object.

        This method will traverse the possible type chains from type
        information to serialize the object.

        Parameters
        ----------
        obj : Any
            The object to serialize.
        type_info : Optional[TypeInfo]
            The type information for the object.
        type_system : TypeSystem
            The type system to use for serialization.

        Returns
        -------
        Any
            The serialized object.
        """

        # shortcut
        if obj is None:
            return None

        if obj is MISSING:
            return "MISSING"

        if type_info and type_info.type_ is not Any:
            last_error = None
            any_chain: Optional[Tuple[TypeInfo, ...]] = None
            for chain in type_system.flatten(type_info):
                if not chain:  # Skip empty chains
                    continue
                if chain[0].type_ is Any:
                    any_chain = chain
                    continue  # Skip Any type chains
                try:
                    return ReducerSystem._apply_type_chain(obj, chain, type_system=type_system)
                except Exception as e:
                    last_error = e
                    continue

            if last_error and any_chain is None:
                raise ConfigReducerError(
                    f"Failed to apply reducer with type info {type_info}: {last_error}"
                ) from last_error

            return obj

        else:
            try:
                return ReducerSystem._apply_builtin_type(obj, type_=None, type_system=type_system)
            except Exception as e:
                raise ConfigReducerError(f"Failed to apply built-in reducer: {e}") from e

    @staticmethod
    def _apply_type_chain(
        obj: Any,
        type_chain: Tuple[TypeInfo, ...],
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
    ) -> Any:
        """Apply a type chain to reduce an object.

        This method will traverse the type chain and apply the proper
        reduction for each type information.

        Parameters
        ----------
        obj : Any
            The object to reduce.
        type_chain : Tuple[TypeInfo, ...]
            The type chain to apply.
        type_system : TypeSystem
            The type system to use for reduction.

        Returns
        -------
        Any
            The reduced object.
        """
        result = obj
        for type_info in type_chain:
            if not isinstance(result, get_origin(type_info.type_) or type_info.type_):
                raise ConfigReducerError(
                    f"Object type {type(result).__name__} is not compatible with {type_info.type_}"
                )
            try:
                if type_info and type_info.custom:
                    result = type_info.custom.reducer(result)
                else:
                    result = ReducerSystem._apply_builtin_type(
                        result, type_=type_info.type_, type_system=type_system
                    )
            except Exception as e:
                raise ConfigReducerError(f"Cannot serialize {type(result).__name__}: {e}") from e
        return result

    @staticmethod
    def _apply_builtin_type(
        obj: Any,
        type_: Optional[Type] = None,
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
    ) -> Any:
        """Apply the built-in reducer to the object.

        Parameters
        ----------
        obj : Any
            The object to reduce.
        type_ : Optional[Type]
            The target type to reduce to.
        type_system : TypeSystem
            The type system to use for reduction.

        Returns
        -------
        Any
            The reduced object.
        """
        # Handle None
        if obj is None:
            return obj

        if obj is MISSING:
            return "MISSING"

        # Handle primitives
        if isinstance(obj, (bool, int, float, str)):
            return obj

        if isinstance(obj, Enum):
            return obj.name

        # Handle dataclass instances
        if is_dataclass(obj):
            result = {}
            for field in type_system.scan(type(obj)).values():
                if not field.init:
                    continue
                if hasattr(obj, field.name):
                    result[field.name] = ReducerSystem.apply(
                        getattr(obj, field.name),
                        type_info=field.type_info,
                        type_system=type_system,
                    )
                else:
                    result[field.name] = "MISSING"
            return result

        if isinstance(obj, (dict, MappingProxyType)):
            if not type_ or type_ is Any:
                return {
                    k: ReducerSystem.apply(v, type_info=None, type_system=type_system)
                    for k, v in obj.items()
                }
            result = {
                k: ReducerSystem.apply(
                    v,
                    type_info=TypeInfo(type_system.extract_container_element_type(type_, key=k)),
                    type_system=type_system,
                )
                for k, v in obj.items()
            }
            return result

        if isinstance(obj, (list, tuple, set, frozenset)):
            if not type_ or type_ is Any:
                return [
                    ReducerSystem.apply(item, type_info=None, type_system=type_system)
                    for item in obj
                ]
            return [
                ReducerSystem.apply(
                    v,
                    type_info=TypeInfo(type_system.extract_container_element_type(type_, key=k)),
                    type_system=type_system,
                )
                for k, v in enumerate(obj)
            ]

        raise ConfigReducerError(f"Unsupported object type: {type(obj).__name__}")

    @staticmethod
    def apply_for_defaults(
        datacls: Type, /, type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM
    ) -> Dict[str, Any]:
        """Serialize default values for a dataclass.

        Parameters
        ----------
        cls : Type
            The dataclass type to serialize defaults for.

        Returns
        -------
        Dict[str, Any]
            Dictionary with field names and their default values.
        """
        defaults = {}
        for field in type_system.scan(datacls).values():
            if not field.init:
                continue
            if field.default is not MISSING:
                defaults[field.name] = ReducerSystem.apply(
                    field.default, type_info=field.type_info, type_system=type_system
                )
            elif field.default_factory is not MISSING:
                defaults[field.name] = ReducerSystem.apply(
                    field.default_factory(),
                    type_info=field.type_info,
                    type_system=type_system,
                )
            else:
                buckets = field.type_hint_buckets
                if (
                    TypeCategory.PRIMITIVE in buckets
                    and NoneType in buckets[TypeCategory.PRIMITIVE]
                ):
                    defaults[field.name] = None
                elif (
                    TypeCategory.DATACLASS in buckets and len(buckets[TypeCategory.DATACLASS]) == 1
                ):
                    nested_cls = next(iter(buckets[TypeCategory.DATACLASS]))
                    defaults[field.name] = ReducerSystem.apply_for_defaults(
                        nested_cls, type_system=type_system
                    )
                else:
                    defaults[field.name] = "MISSING"
        return defaults
