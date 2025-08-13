"""Factory system for node-based resolution.

This module handles type transformation and factory application
for the node-based resolution system using type chains.
"""

from dataclasses import MISSING, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import (
    Any,
    Dict,
    FrozenSet,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Set,
    Tuple,
    Type,
    get_origin,
)

from ..core.exceptions import ConfigFactoryError
from ..core.types import TypeInfo
from ..core.utils import get_fields
from .node import ResolutionNode

__all__ = ["FactorySystem"]


class FactorySystem:
    """Factory system for node-based resolution using type chains.

    The FactorySystem processes type chains to transform values,
    trying each chain and applying TypeInfo transformations.
    """

    @staticmethod
    def apply(node: ResolutionNode) -> None:
        """Apply factory to a single node.

        This method recursively applies factories to children first,
        then processes the node's type chains to transform its value.

        Parameters
        ----------
        node : ResolutionNode
            The node to apply factory to.

        Raises
        ------
        ConfigFactoryError
            If the node is a reference or factory application fails.
        """
        if node.is_factoried:
            return
        if node.is_reference:
            raise ConfigFactoryError(f"Cannot apply factory to reference node '{node.name}'")

        # First apply the factory to the node's children
        if isinstance(node.content, dict):
            for child in node.content.values():
                if isinstance(child, ResolutionNode):
                    FactorySystem.apply(child)
        elif isinstance(node.content, list):
            for child in node.content:
                if isinstance(child, ResolutionNode):
                    FactorySystem.apply(child)

        # Get the value to transform (after children are factoried)
        value = node.materialize(after_factory=True)

        # If no type chains, just store the value as-is
        if not node.type_chains:
            node.value = value
            return

        # Try each type chain in order
        last_error = None
        any_chain: Optional[Tuple[TypeInfo, ...]] = None
        for type_chain in node.type_chains:
            if not type_chain:  # Skip empty chains
                continue
            if type_chain[-1].type_ is Any:
                any_chain = type_chain
                continue  # Skip Any type chains
            try:
                result = FactorySystem._apply_type_chain(value, type_chain, node.name)
                node.value = result
                # Record which chain was successful by keeping only it
                node.type_chains = [type_chain]
                return  # Success - stop trying other chains
            except Exception as e:
                last_error = e
                continue  # Try next chain

        if last_error and any_chain is None:
            raise ConfigFactoryError(
                f"Failed to apply any type chain at '{node.name}': {last_error}"
            ) from last_error

        # Store value as-is if we have an Any chain or no errors
        node.value = value
        node.type_chains = [any_chain] if any_chain else []

    @staticmethod
    def _apply_type_chain(value: Any, type_chain: Tuple[TypeInfo, ...], name: str) -> Any:
        """Apply a type chain to transform a value.

        Type chains are processed from last to first TypeInfo,
        allowing progressive type transformations.

        Parameters
        ----------
        value : Any
            The initial value to transform.
        type_chain : Tuple[TypeInfo, ...]
            Chain of type transformations to apply.
        name : str
            Name for error reporting.

        Returns
        -------
        Any
            The transformed value.
        """
        result = value

        # Apply transformations from last to first in the chain
        for type_info in reversed(type_chain):
            if type_info.custom:
                # Use custom factory if available
                try:
                    result = type_info.custom.factory(result)
                except Exception as e:
                    raise ConfigFactoryError(
                        f"Custom factory failed for {type_info.type_} at '{name}': {e}"
                    ) from e
            else:
                # Use built-in type handling
                result = FactorySystem._apply_builtin_type(result, type_info.type_, name)

        return result

    @staticmethod
    def _apply_builtin_type(value: Any, target_type: Type, name: str) -> Any:  # noqa: C901
        """Apply built-in type transformation.

        Parameters
        ----------
        value : Any
            The value to transform.
        target_type : Type
            The target type.
        name : str
            Name for error reporting.

        Returns
        -------
        Any
            The transformed value.
        """
        # Handle None values
        if value is None:
            return None

        # Handle Any type - no transformation needed
        if target_type is Any or target_type is type(Any):
            return value

        # Get origin for generic types
        origin = get_origin(target_type)

        # Primitive types
        if target_type in (bool, int, float, str):
            return FactorySystem._convert_primitive(value, target_type, name)

        # Enum types
        if isinstance(target_type, type) and issubclass(target_type, Enum):
            return FactorySystem._convert_enum(value, target_type, name)

        # Dataclass types
        if is_dataclass(target_type):
            return FactorySystem._create_dataclass(value, target_type, name)

        # Container types
        if origin in (list, List) or target_type is list:
            if not isinstance(value, (list, tuple)):
                raise ConfigFactoryError(
                    f"Cannot create list from {type(value).__name__} at '{name}'"
                )
            return list(value)

        if origin in (dict, Dict, MutableMapping) or target_type is dict:
            if not isinstance(value, dict):
                raise ConfigFactoryError(
                    f"Cannot create dict from {type(value).__name__} at '{name}'"
                )
            return dict(value)

        if origin in (set, Set) or target_type is set:
            if not isinstance(value, (list, tuple, set)):
                raise ConfigFactoryError(
                    f"Cannot create set from {type(value).__name__} at '{name}'"
                )
            return set(value)

        if origin in (tuple, Tuple) or target_type is tuple:
            if not isinstance(value, (list, tuple)):
                raise ConfigFactoryError(
                    f"Cannot create tuple from {type(value).__name__} at '{name}'"
                )
            return tuple(value)

        if origin in (Mapping, MappingProxyType) or target_type is MappingProxyType:
            if not isinstance(value, dict):
                raise ConfigFactoryError(
                    f"Cannot create MappingProxyType from {type(value).__name__} at '{name}'"
                )
            return MappingProxyType(value)

        if origin in (frozenset, FrozenSet) or target_type is frozenset:
            if not isinstance(value, (list, tuple, set)):
                raise ConfigFactoryError(
                    f"Cannot create frozenset from {type(value).__name__} at '{name}'"
                )
            return frozenset(value)

        # No transformation needed
        return value

    @staticmethod
    def _convert_primitive(value: Any, target_type: Type, name: str) -> Any:
        """Convert value to primitive type.

        Parameters
        ----------
        value : Any
            The value to convert.
        target_type : Type
            The target primitive type.
        name : str
            Name for error reporting.

        Returns
        -------
        Any
            The converted value.
        """
        if isinstance(value, target_type):
            return value

        try:
            if target_type is bool:
                if isinstance(value, str):
                    lower = value.lower()
                    if lower in ("true", "yes", "1"):
                        return True
                    elif lower in ("false", "no", "0"):
                        return False
                    else:
                        raise ValueError(f"Cannot convert '{value}' to bool")
                return bool(value)
            elif target_type is int:
                return int(value)
            elif target_type is float:
                return float(value)
            elif target_type is str:
                return str(value)
        except (ValueError, TypeError) as e:
            raise ConfigFactoryError(
                f"Cannot convert {type(value).__name__} to {target_type.__name__} at '{name}': {e}"
            ) from e

        return value

    @staticmethod
    def _convert_enum(value: Any, enum_type: Type[Enum], name: str) -> Enum:
        """Convert value to enum type.

        Parameters
        ----------
        value : Any
            The value to convert.
        enum_type : Type[Enum]
            The target enum type.
        name : str
            Name for error reporting.

        Returns
        -------
        Enum
            The enum value.
        """
        if isinstance(value, enum_type):
            return value

        # Try by name
        if isinstance(value, str):
            try:
                return enum_type[value]
            except KeyError:
                pass

        # Try by value
        try:
            return enum_type(value)
        except (ValueError, TypeError):
            pass

        raise ConfigFactoryError(f"Cannot convert '{value}' to {enum_type.__name__} at '{name}'")

    @staticmethod
    def _create_dataclass(value: Any, cls: Type, name: str) -> Any:
        """Create a configclass instance.

        Parameters
        ----------
        value : Any
            The value to convert (should be a dict).
        cls : Type
            The configclass type.
        name : str
            Name for error reporting.

        Returns
        -------
        Any
            The configclass instance.
        """
        if isinstance(value, cls):
            return value

        if not isinstance(value, dict):
            raise ConfigFactoryError(
                f"Cannot create {cls.__name__} from {type(value).__name__} at '{name}'"
            )

        # Prepare kwargs for configclass
        kwargs = {}
        for field in get_fields(cls, init_only=True, exclude_pseudo=False):
            if field.name in value:
                kwargs[field.name] = value[field.name]
            elif field.default is not MISSING or field.default_factory is not MISSING:
                # Field has a default value, skip it
                continue
            else:
                # Required field missing
                raise ConfigFactoryError(
                    f"Missing required field '{field.name}' for {cls.__name__} at '{name}'"
                )

        try:
            return cls(**kwargs)
        except Exception as e:
            raise ConfigFactoryError(f"Failed to create {cls.__name__} at '{name}': {e}") from e
