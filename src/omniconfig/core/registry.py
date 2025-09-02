# -*- coding: utf-8 -*-
"""Universal registry to support registration and loading."""

from abc import ABCMeta
from collections import defaultdict
from dataclasses import MISSING
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
    overload,
)

__all__ = [
    "register_alias",
    "register",
    "retrieve",
    "RegistryMeta",
    "RegistryABCMeta",
    "RegistryMixin",
]

T = TypeVar("T")

_VALUE_REGISTRY: Dict[type, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
_ALIAS_REGISTRY: Dict[type, Dict[str, Dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
_KEY_REGISTRY: Dict[type, Dict[int, Set[Tuple[str, str]]]] = defaultdict(lambda: defaultdict(set))


def _standardize_name(name: str) -> str:
    """Standardize a registry name by converting it to lowercase
    and replacing spaces and hyphens.

    Parameters
    ----------
    name : str
        The name to standardize.

    Returns
    -------
    str
        The standardized name.
    """
    return name.lower().replace("-", "_").replace(" ", "_")


def _standardize_alias(alias: Union[str, Sequence[str]]) -> List[str]:
    """Standardize a registry alias by converting it to lowercase
    and replacing spaces and hyphens.

    Parameters
    ----------
    alias : Union[str, Sequence[str]]
        The alias or aliases to standardize.

    Returns
    -------
    List[str]
        The standardized aliases.
        If `alias` is None or empty, returns an empty list.
    """
    if not alias:
        return []
    if isinstance(alias, str):
        alias = [alias]
    return [_standardize_name(a) for a in alias]


def register_alias(
    cls: type,
    name: str,
    *,
    alias: Union[str, Sequence[str]],
    subregistry: str = "",
    overwrite: bool = False,
) -> None:
    """Register an alias in the global registry.

    Parameters
    ----------
    cls : type
        The registry class.
    name : str
        The name of the value to register.
    alias : Union[str, Sequence[str]]
        Aliases for the registered value.
    subregistry : str, default: ""
        The subregistry to which the alias belongs.
    overwrite : bool, default: False
        If True, allow overwriting an existing alias.

    Raises
    -------
    ValueError
        If the alias is already registered.
    """
    alias = _standardize_alias(alias)

    if not alias:
        raise ValueError("Alias must not be empty")

    name = _standardize_name(name)
    subregistry = _standardize_name(subregistry)
    if name not in _VALUE_REGISTRY[cls][subregistry]:
        raise ValueError(
            f"Cannot register alias for unregistered name '{name}'"
            f" in {cls.__name__} '{subregistry}' subregistry"
        )

    source = _ALIAS_REGISTRY[cls][subregistry]
    for a in alias:
        if overwrite or a not in source:
            source[a] = name
        elif source[a] != name:
            raise ValueError(
                f"Alias '{a}' is already registered for {source[a]}"
                f" in {cls.__name__} '{subregistry}' registry"
            )


def register(
    cls: type,
    value: Any,
    name: str = "",
    *,
    alias: Union[str, Sequence[str]] = "",
    subregistry: str = "",
    as_fallback: bool = False,
    subclass_only: Union[bool, type] = False,
    instance_only: Union[bool, type] = False,
    overwrite: bool = False,
) -> None:
    """Register a class or function in the global registry.

    Parameters
    ----------
    cls : type
        The registry class.
    value : Any
        The value to register (can be a class, function, or instance).
    name : str, default: ""
        The name of the value to register.
        If not provided, it will be derived from the value's `__name__`.
    alias : Union[str, Sequence[str]], default: ""
        Aliases for the registered value.
    subregistry : str, default: ""
        The subregistry to which the value belongs.
    as_fallback : bool, default: False
        If True, the value will be registered as the fallback value
        for the given registry class.
    subclass_only : Union[bool, type], default: False
        If True, the value must be a subclass of `cls`.
        If a type is provided, value must be a subclass of that type.
        If False, no subclass restriction is applied.
    instance_only: Union[bool, type], default: False
        If True, the value must be an instance of `cls`.
        If a type is provided, value must be an instance of that type.
        If False, no instance restriction is applied.
    overwrite : bool, default: False
        If True, allow overwriting an existing registration.
    """
    if not name:
        if not hasattr(value, "__name__"):
            raise RuntimeError(f"Cannot register value {value} without a name.")
        name = value.__name__
    name = _standardize_name(name)
    subregistry = _standardize_name(subregistry)
    assert name, "Name must not be empty"

    if subclass_only:
        if instance_only:
            raise ValueError("Cannot set both subclass_only and instance_only to True")
        superclass = cls if isinstance(subclass_only, bool) else subclass_only
        if not issubclass(value, superclass):
            raise TypeError(f"Value {value} is not a subclass of {superclass.__name__}")

    if instance_only:
        instance_cls = cls if isinstance(instance_only, bool) else instance_only
        if not isinstance(value, instance_cls):
            raise TypeError(f"Value {value} is not an instance of {instance_cls.__name__}")

    source = _VALUE_REGISTRY[cls][subregistry]
    if overwrite and name in source:
        orig = source[name]
        source[name] = value
        _KEY_REGISTRY[cls][id(orig)].discard((subregistry, name))
        _KEY_REGISTRY[cls][id(value)].add((subregistry, name))
    elif name not in source:
        source[name] = value
        _KEY_REGISTRY[cls][id(value)].add((subregistry, name))
    else:
        registered_value = source[name]
        if registered_value is not value:
            raise ValueError(
                f"{name} is already registered with {registered_value}."
                " Use `overwrite=True` to replace it."
            )

    if as_fallback:
        alias_source = _ALIAS_REGISTRY[cls][subregistry]
        if overwrite or "" not in alias_source:
            alias_source[""] = name
        else:
            registered_name = alias_source[""]
            if registered_name is not name:
                raise ValueError(
                    f'Fallback value is already registered as "{registered_name}".'
                    " Use `overwrite=True` to replace it."
                )

    _ALIAS_REGISTRY[cls][subregistry][name] = name  # Register the name itself as its own alias
    if alias:
        register_alias(cls, name, alias=alias, subregistry=subregistry, overwrite=overwrite)


def retrieve(
    cls: type, name: str, *, subregistry: str = "", fallback: bool = False, default: T = None
) -> Union[Any, T]:
    """Retrieve a registered value from the global registry.

    Parameters
    ----------
    cls : type
        The registry class.
    name : str
        The name of the value to retrieve.
    subregistry : str, default: ""
        The subregistry from which to retrieve the value.
    fallback: bool, default: False
        If True, returns the fallback value if the name is not found.
    default: T, default: None
        The default value to return if the name is not found
        and fallback is False or fallback value is not set.

    Returns
    -------
    Union[Any, T]
        The registered value if found, otherwise the default value.
    """
    name = _standardize_name(name)
    subregistry = _standardize_name(subregistry)
    alias_source = _ALIAS_REGISTRY[cls][subregistry]
    if name in alias_source:
        key = alias_source[name]
    elif fallback and "" in alias_source:
        key = alias_source[""]
    else:
        return default
    return _VALUE_REGISTRY[cls][subregistry][key]


def identify(cls: type, value: Any) -> FrozenSet[Tuple[str, str]]:
    """Identify the registry entry for a given value.

    Parameters
    ----------
    cls : type
        The registry class.
    value : Any
        The value to identify.

    Returns
    -------
    FrozenSet[Tuple[str, str]]
        A set of (name, subregistry) tuples for the registered value,
        or an empty set if not found.
    """
    return frozenset(_KEY_REGISTRY[cls].get(id(value), set()))


class RegistryMeta(type):
    _REGISTRY_NAME_FIELD: str
    _REGISTRY_SUBREGISTRY_FIELD: str
    _REGISTRY_SUBCLASS_ONLY: Dict[str, Union[bool, type]]
    _REGISTRY_INSTANCE_ONLY: Dict[str, Union[bool, type]]

    def __new__(mcls, name, bases, namespace, /, **kwargs):
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        if not hasattr(cls, "_REGISTRY_NAME_FIELD"):
            cls._REGISTRY_NAME_FIELD = "name"
        if not hasattr(cls, "_REGISTRY_SUBREGISTRY_FIELD"):
            cls._REGISTRY_SUBREGISTRY_FIELD = "subregistry"
        if not hasattr(cls, "_REGISTRY_SUBCLASS_ONLY"):
            cls._REGISTRY_SUBCLASS_ONLY = defaultdict(lambda: False)
        if not hasattr(cls, "_REGISTRY_INSTANCE_ONLY"):
            cls._REGISTRY_INSTANCE_ONLY = defaultdict(lambda: False)
        return cls

    @overload
    def register(
        cls,
        value: Any,
        /,
        *,
        name: str = "",
        alias: Union[str, Sequence[str]] = "",
        subregistry: str = "",
        as_fallback: bool = False,
        overwrite: bool = False,
    ) -> None:
        """Register a class or function to the base class registry.

        Parameters
        ----------
        value : Any
            The value to register.
        name : str, default: ""
            The name of the value to register.
            If empty, it will be derived from the value's `__name__`.
        alias : Union[str, Sequence[str]], default: ""
            Aliases for the registered value.
        subregistry : str, default: ""
            The subregistry to which the value belongs.
        as_fallback : bool, default: False
            If True, the value will be registered as the fallback value
            for the given registry class.
        overwrite : bool, default: False
            If True, allow overwriting an existing registration.
        """
        ...

    @overload
    def register(
        cls,
        /,
        *,
        name: str = "",
        alias: Union[str, Sequence[str]] = "",
        subregistry: str = "",
        as_fallback: bool = False,
        overwrite: bool = False,
    ) -> Callable:
        """Decorator to register a class or function to the registry.

        Parameters
        ----------
        name : str, default: ""
            The name of the value to register.
            If empty, it will be derived from the value's `__name__`.
        alias : Union[str, Sequence[str]], default: ""
            Aliases for the registered value.
        subregistry : str, default: ""
            The subregistry to which the value belongs.
        as_fallback : bool, default: False
            If True, the value will be registered as the fallback value
            for the given registry class.
        overwrite : bool, default: False
            If True, allow overwriting an existing registration.

        Returns
        -------
        Callable
            A decorator that registers the decorated class or function.
        """
        ...

    def register(
        cls,
        value: Any = MISSING,
        /,
        *,
        name: str = "",
        alias: Union[str, Sequence[str]] = "",
        subregistry: str = "",
        as_fallback: bool = False,
        overwrite: bool = False,
    ) -> Optional[Callable]:
        """Register a class or function to the base class registry.

        Parameters
        ----------
        value : Any, optional
            The value to register.
            If not provided, the method will return a decorator.
        name : str, default: ""
            The name of the value to register.
            If empty, it will be derived from the value's `__name__`.
        alias : Union[str, Sequence[str]], default: ""
            Aliases for the registered value.
        subregistry : str, default: ""
            The subregistry from which to retrieve the value.
        as_fallback : bool, default: False
            If True, the value will be registered as the fallback value
            for the given registry class.
        overwrite : bool, default: False
            If True, allow overwriting an existing registration.

        Returns
        -------
        Optional[Callable]
            If `value` is provided, returns None.
            Otherwise, returns a decorator that
            registers the decorated class or function.
        """

        if value is MISSING:

            def decorator(value):
                register(
                    cls,
                    value,
                    name=name,
                    alias=alias,
                    subregistry=subregistry,
                    as_fallback=as_fallback,
                    subclass_only=cls._REGISTRY_SUBCLASS_ONLY[subregistry],
                    instance_only=cls._REGISTRY_INSTANCE_ONLY[subregistry],
                    overwrite=overwrite,
                )
                return value

            return decorator
        else:
            register(
                cls,
                value,
                name=name,
                alias=alias,
                subregistry=subregistry,
                as_fallback=as_fallback,
                subclass_only=cls._REGISTRY_SUBCLASS_ONLY[subregistry],
                instance_only=cls._REGISTRY_INSTANCE_ONLY[subregistry],
                overwrite=overwrite,
            )

    def retrieve(
        cls, name: str, *, subregistry: str = "", fallback: bool = False, default: T = None
    ) -> Union[Any, T]:
        """Retrieve a registered value from the global registry.

        Parameters
        ----------
        name : str
            The name of the value to retrieve.
        subregistry : str, default: ""
            The subregistry from which to retrieve the value.
        fallback: bool, default: False
            If True, returns the fallback value if name is not found.
        default: T, default: None
            The default value to return if the name is not found
            and fallback is False or fallback value is not set.

        Returns
        -------
        Union[Any, T]
            The registered value if found, otherwise the default value.
        """
        return retrieve(cls, name, subregistry=subregistry, fallback=fallback, default=default)

    def identify(cls: type, value: Any) -> FrozenSet[Tuple[str, str]]:
        """Identify the registered name and subregistry for a value.

        Parameters
        ----------
        cls : type
            The registry class.
        value : Any
            The value to identify.

        Returns
        -------
        FrozenSet[Tuple[str, str]]
            A set of (name, subregistry) tuples for registered value,
            or an empty set if not found.
        """
        return identify(cls, value)

    def register_alias(
        cls,
        name: str,
        *,
        alias: Union[str, Sequence[str]],
        subregistry: str = "",
        overwrite: bool = False,
    ) -> None:
        """Register an alias for a registered value.

        Parameters
        ----------
        cls : type
            The registry class.
        name : str
            The name of the registered value.
        alias : Union[str, Sequence[str]]
            The alias or aliases to register.
        subregistry : str, default: ""
            The subregistry to which the alias belongs.
        overwrite : bool, default: False
            If True, allow overwriting an existing alias.
        """
        register_alias(cls, name, alias=alias, subregistry=subregistry, overwrite=overwrite)


class RegistryABCMeta(RegistryMeta, ABCMeta):  # type: ignore
    abc_register = ABCMeta.register


class RegistryMixin(metaclass=RegistryMeta):
    __slots__ = ()


class RegistryABC(metaclass=RegistryABCMeta):
    __slots__ = ()
