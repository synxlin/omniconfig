"""Type classification system for OmniConfig."""

import enum
import inspect
from collections import OrderedDict, defaultdict
from dataclasses import (
    _FIELDS,  # type: ignore
    _MISSING_TYPE,
    MISSING,
    Field,
    InitVar,
    dataclass,
    is_dataclass,
)
from types import MappingProxyType, NoneType, UnionType
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from .exceptions import TypeRegistrationError
from .utils import get_fields, get_fields_docstrings

__all__ = [
    "TypeCategory",
    "is_primitive_type",
    "is_union_type",
    "CustomTypeInfo",
    "TypeInfo",
    "TypeSystem",
    "_GLOBAL_TYPE_SYSTEM",
    "try_prune_type_chains",
]


_PRIMITIVE_TYPES = {bool, int, float, str, NoneType}
_UNION_TYPES = frozenset([Union, UnionType])
_RAW_LIST_CONTAINER_TYPES = frozenset([list, set, tuple, frozenset])
_RAW_DICT_CONTAINER_TYPES = frozenset([dict, MappingProxyType])
_RAW_CONTAINER_TYPES = _RAW_LIST_CONTAINER_TYPES.union(_RAW_DICT_CONTAINER_TYPES)
_LIST_CONTAINER_TYPES = frozenset([list, List, tuple, Tuple, set, Set, frozenset, FrozenSet])
_DICT_CONTAINER_TYPES = frozenset([dict, Dict, MappingProxyType, Mapping, MutableMapping])
_CONTAINER_TYPES = _LIST_CONTAINER_TYPES.union(_DICT_CONTAINER_TYPES)

_T = TypeVar("_T")


class TypeCategory(enum.Enum):
    """Type hint classification categories."""

    PRIMITIVE = "primitive"
    DATACLASS = "dataclass"
    CONTAINER = "container"
    UNION = "union"
    CUSTOM = "custom"


def is_primitive_type(type_: Any) -> bool:
    """Check if a type is primitive.

    Parameters
    ----------
    type_ : Any
        Type to check.

    Returns
    -------
    bool
        True if type is primitive.
    """
    if type_ in _PRIMITIVE_TYPES:
        return True
    if inspect.isclass(type_) and issubclass(type_, enum.Enum):
        return True
    return False


def is_container_type(type_: Any) -> bool:
    """Check if a type is a container (list, dict, set, tuple).

    Parameters
    ----------
    type_ : Any
        Type to check.

    Returns
    -------
    bool
        True if type is a container.
    """
    return get_origin(type_) in _CONTAINER_TYPES or type_ in _RAW_CONTAINER_TYPES


def is_union_type(type_: Any) -> bool:
    """Check if a type is a Union/Optional.

    Parameters
    ----------
    type_ : Any
        Type to check.

    Returns
    -------
    bool
        True if type is a Union/Optional.
    """
    return get_origin(type_) in _UNION_TYPES


@dataclass
class CustomTypeInfo:
    """Information about a custom type."""

    type_hint: Any
    """The type hint used for parsing (e.g., str, dict[str, int])."""
    factory: Callable[[Any], Any]
    """Convert from type_hint to type_."""
    reducer: Callable[[Any], Any]
    """Convert from type_ to type_hint for serialization."""

    def __post_init__(self):
        """Validate that factory and reducer are callable."""
        if self.factory is None:
            pass


@dataclass
class TypeInfo:
    """Information about a registered type."""

    type_: Any
    """The type."""
    custom: Optional[CustomTypeInfo] = None
    """Optional custom type information."""

    @property
    def type_hint(self) -> Any:
        """Get the type hint for this type."""
        return self.type_ if self.custom is None else self.custom.type_hint


@dataclass
class DataclassFieldInfo:
    """Information about a field in a dataclass."""

    cls: Type
    """The dataclass type this field belongs to."""
    field: Field
    """The dataclass field."""
    type_info: TypeInfo
    """Type information for the field."""
    type_category: TypeCategory
    """The category of the field's type."""
    type_hint_buckets: Dict[TypeCategory, Set[Any]]
    """The classified type hint buckets."""
    docstring: str
    """Docstring for the field, if available."""

    @property
    def name(self) -> str:
        """Get the name of the field."""
        return self.field.name

    @property
    def type(self) -> Any:
        """Get the type of the field."""
        return self.type_info.type_

    @property
    def type_hint(self) -> Any:
        """Get the type hint of the field."""
        return self.type_info.type_hint

    @property
    def default(self) -> Any:
        """Get the default value of the field."""
        return self.field.default

    @property
    def default_factory(self) -> Union[Callable[[], Any], _MISSING_TYPE]:
        """Get the default factory of the field."""
        return self.field.default_factory

    @property
    def init(self) -> bool:
        """Check if the field is included in the dataclass __init__."""
        return self.field.init

    @property
    def metadata(self) -> MappingProxyType[str, Any]:
        """Get the metadata of the field."""
        return self.field.metadata


class TypeSystem:
    """Type registration and classification system."""

    _registry: Dict[Type, TypeInfo]
    _buckets_cache: Dict[Type, Dict[TypeCategory, Set[Any]]]
    _dataclass_cache: Dict[Type, OrderedDict[str, DataclassFieldInfo]]

    def __init__(self):
        """Initialize the type registry."""
        self._registry = {}
        self._buckets_cache = {}
        self._dataclass_cache = defaultdict(OrderedDict)

    def register(
        self,
        type_: Type,
        type_hint: Any,
        factory: Callable[[Any], Any],
        reducer: Callable[[Any], Any],
    ) -> None:
        """Register a custom type with its factory and reducer.

        Parameters
        ----------
        type_ : Type
            The custom type to register.
        type_hint : Any
            The type hint to use for parsing (e.g., str, dict).
        factory : Callable[[Any], Any]
            Function to convert type_hint to type_.
        reducer : Callable[[Any], Any]
            Function to convert type_ to type_hint for serialization.

        Raises
        ------
        TypeRegistrationError
            If the type is already registered with different handlers.
        """
        if is_primitive_type(type_):
            raise TypeRegistrationError(
                f"Cannot register primitive type {type_}. Use field metadata for primitive types."
            )
        if is_dataclass(type_):
            raise TypeRegistrationError(
                f"Cannot register dataclass type {type_}. Use field metadata for dataclasses."
            )
        if is_container_type(type_):
            raise TypeRegistrationError(
                f"Cannot register container type {type_}. Use field metadata for containers."
            )
        if is_union_type(type_):
            raise TypeRegistrationError(
                f"Cannot register Union type {type_}. Use field metadata for unions."
            )
        if not callable(factory):
            raise TypeRegistrationError("Factory must be callable.")
        if not callable(reducer):
            raise TypeRegistrationError("Reducer must be callable.")
        if type_ in self._registry:
            existing = self._registry[type_]
            # Different parameters - raise error
            if (
                existing.custom is None
                or existing.custom.type_hint != type_hint
                or str(existing.custom.factory) != str(factory)
                or str(existing.custom.reducer) != str(reducer)
            ):
                raise TypeRegistrationError(
                    f"Type '{type_.__name__}' already registered. "
                    "Use field-level metadata to override."
                )
            return  # Already registered with same params, skip

        self._registry[type_] = TypeInfo(
            type_=type_,
            custom=CustomTypeInfo(
                type_hint=type_hint,
                factory=factory,
                reducer=reducer,
            ),
        )

    def retrieve(self, type_: Type, default: _T = None) -> Union[TypeInfo, _T]:
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
        return self._registry.get(type_, default)

    def is_registered(self, type_: Type) -> bool:
        """Check if a type is registered.

        Parameters
        ----------
        type_ : Type
            The type to check.

        Returns
        -------
        bool
            True if the type is registered.
        """
        return type_ in self._registry

    def clear(self) -> None:
        """Clear all registered types."""
        self._registry.clear()

    def classify(self, type_: Any, metadata: Optional[Mapping[str, Any]] = None) -> TypeCategory:
        """Classify a type hint into one of the type categories.

        Parameters
        ----------
        type_ : Any
            The type to classify.

        metadata : Optional[Mapping[str, Any]], default: None
            Field metadata that may contain custom type information.

        Returns
        -------
        TypeCategory
            The classification of the type.
        """
        # Handle None and NoneType
        if type_ is None or type_ is NoneType:
            return TypeCategory.PRIMITIVE

        # Check for custom type in metadata
        if metadata and "type_hint" in metadata:
            # If metadata specifies type_hint, this is a custom type
            return TypeCategory.CUSTOM

        # Check if it's a registered custom type
        if type_ in self._registry:
            return TypeCategory.CUSTOM

        # Get origin for generic types
        origin = get_origin(type_)

        # Handle Union/Optional
        if origin in _UNION_TYPES:
            return TypeCategory.UNION

        # Handle containers
        if origin in _CONTAINER_TYPES:
            return TypeCategory.CONTAINER

        # Handle untyped containers
        if type_ in _RAW_CONTAINER_TYPES:
            return TypeCategory.CONTAINER

        # Check if it's a dataclass
        if inspect.isclass(type_) and is_dataclass(type_):
            return TypeCategory.DATACLASS

        # Check for primitive types
        if is_primitive_type(type_):
            return TypeCategory.PRIMITIVE

        # Everything else is custom
        return TypeCategory.CUSTOM

    def classify_into_buckets(
        self, type_hint: Any, buckets: Optional[Dict[TypeCategory, Set[Any]]] = None
    ) -> Dict[TypeCategory, Set[Any]]:
        """Classify a type hint into buckets.

        A bucket is a mapping from TypeCategory to a set of type hints
        that fall into that category.

        Parameters
        ----------
        type_hint : Any
            The type hint to classify.
        buckets : Optional[Dict[TypeCategory, Set[Any]]]
            The buckets to populate.

        Returns
        -------
        Dict[TypeCategory, Set[Any]]
            The classified type hint buckets.
        """
        if type_hint in self._buckets_cache:
            updates = self._buckets_cache[type_hint]
        else:
            category = self.classify(type_hint)
            if category == TypeCategory.CUSTOM:
                type_info = self.retrieve(type_hint)
                if type_info is None:
                    raise ValueError(f"Type hint {type_hint} is not registered.")
                updates = self.classify_into_buckets(type_info.type_hint)
            elif category == TypeCategory.UNION:
                updates = {}
                args = get_args(type_hint)
                for arg in args:
                    self.classify_into_buckets(arg, buckets=updates)
            else:
                updates = {category: {type_hint}}
            self._buckets_cache[type_hint] = updates
        if buckets is None:
            return updates
        for category, types in updates.items():
            if category not in buckets:
                buckets[category] = set()
            buckets[category].update(types)
        return buckets

    def flatten(self, type_info: TypeInfo) -> List[Tuple[TypeInfo, ...]]:
        """Flatten a type info into all possible type chains.

        A type chain is a sequence of TypeInfo objects representing the
        hierarchy of types leading to a primitive or non-custom type.

        Parameters
        ----------
        type_info : TypeInfo
            The type information to flatten.

        Returns
        -------
        List[Tuple[TypeInfo, ...]]
            List of type chains.
        """

        def dfs(
            type_hint: Any, chain: Tuple[TypeInfo, ...], chains: List[Tuple[TypeInfo, ...]]
        ) -> List[Tuple[TypeInfo, ...]]:
            category = self.classify(type_hint)
            if category == TypeCategory.CUSTOM:
                type_info = self.retrieve(type_hint)
                if type_info is None:
                    raise ValueError(f"Type hint {type_hint} is not registered.")
                dfs(type_info.type_hint, chain=chain + (type_info,), chains=chains)
            elif category == TypeCategory.UNION:
                args = get_args(type_hint)
                for arg in args:
                    dfs(arg, chain=chain, chains=chains)
            else:
                chains.append(chain + (TypeInfo(type_=type_hint),))
            return chains

        if type_info.custom is None:
            return dfs(type_info.type_, chain=(), chains=[])
        return dfs(type_info.custom.type_hint, chain=(type_info,), chains=[])

    def extract_container_element_type(
        self, container_type: Optional[Any], key: Union[str, int]
    ) -> Any:
        """Extract element type from a container type hint.

        This supports:
        - Standard containers: List[T], Dict[K, V], Set[T]
        - Nested containers: Dict[str, List[int]]
        - Raw containers: list, dict -> Any
        - Union types: Union[List[T], Dict[K, V]] -> Union[T, V]
        - Custom types registered with container type_hint
        - Non-containers: returns Any

        Parameters
        ----------
        container_type : Optional[Type]
            The container type to extract from.

        Returns
        -------
        Any
            The element type, or Any if not determinable.
        """
        if container_type is None or container_type is Any:
            return Any

        # Check if it's a custom type with container type_hint
        type_info = self.retrieve(container_type)
        if type_info:
            # Recursively extract from the registered type_hint
            return self.extract_container_element_type(type_info.type_hint, key)

        # If the container type is a dataclass, check its fields
        if is_dataclass(container_type):
            type_hints = get_type_hints(container_type)
            if key in type_hints:
                return type_hints[key]
            fields: Dict[str, Field] = getattr(container_type, _FIELDS)
            if key in fields:
                return fields[key].type
            return Any

        # Check raw container types first
        if container_type in _RAW_CONTAINER_TYPES:
            return Any

        # Get origin and args
        origin = get_origin(container_type)
        args = get_args(container_type)

        # Handle Union types
        if origin in _UNION_TYPES:
            union_element_types = tuple(
                self.extract_container_element_type(arg, key)
                for arg in args
                if arg is not NoneType
            )
            return (
                Union[union_element_types]
                if union_element_types and Any not in union_element_types
                else Any
            )
        # Handle typed containers
        elif origin in (list, List, set, Set, frozenset, FrozenSet):
            return args[0] if args else Any
        elif origin in (dict, Dict):
            # For dict, return value type
            return args[1] if len(args) > 1 else Any
        elif origin in (tuple, Tuple):
            if len(args) == 0:
                return Any
            key = int(key)
            if key < len(args):
                while key >= 0:
                    arg = args[key]
                    if arg is not Ellipsis:
                        return arg
                    key -= 1
            # If key is out of bounds, return Any
            return Any

        # Not a container, return Any
        return Any

    def scan(self, cls: Type, /) -> OrderedDict[str, DataclassFieldInfo]:  # noqa: C901
        """Scan a dataclass and cache its field information.

        Parameters
        ----------
        cls : Type
            The dataclass type to scan.
        """
        if cls in self._dataclass_cache:
            return self._dataclass_cache[cls]

        if not is_dataclass(cls):
            raise TypeError(f"{cls} is not a dataclass.")

        for base in reversed(cls.__mro__[1:-1]):  # Skip object and current class
            if is_dataclass(base) and base not in self._dataclass_cache:
                self.scan(base)

        fields = get_fields(cls, init_only=False, exclude_pseudo=False)
        type_hints = get_type_hints(cls)
        docstrings = get_fields_docstrings(cls)

        for field in fields:
            type_ = type_hints.get(field.name, field.type)
            if isinstance(type_, InitVar):
                type_ = type_.type

            if "type_hint" in field.metadata:
                type_info = TypeInfo(
                    type_,
                    custom=CustomTypeInfo(
                        type_hint=field.metadata["type_hint"],
                        factory=field.metadata["factory"],
                        reducer=field.metadata["reducer"],
                    ),
                )
                type_category = TypeCategory.CUSTOM
            else:
                type_info = self.retrieve(type_, TypeInfo(type_=type_))
                type_category = self.classify(type_info.type_hint)

            if "help" in field.metadata:
                docstring = field.metadata["help"]
            elif field.name in docstrings:
                docstring = docstrings[field.name]
            else:
                docstring = ""
                for base in cls.__mro__[1:-1]:  # Skip object and current class
                    base_cache = self._dataclass_cache.get(base, None)
                    if base_cache and field.name in base_cache:
                        docstring = base_cache[field.name].docstring
                        break

            buckets = self.classify_into_buckets(type_info.type_hint)

            self._dataclass_cache[cls][field.name] = DataclassFieldInfo(
                cls=cls,
                field=field,
                type_info=type_info,
                type_category=type_category,
                type_hint_buckets=buckets,
                docstring=docstring,
            )

            if TypeCategory.DATACLASS in buckets:
                for type_ in buckets[TypeCategory.DATACLASS]:
                    self.scan(type_)  # Recursively scan nested dataclasses

        return self._dataclass_cache[cls]

    def build_type_infos(
        self,
        cls: Type,
        /,
        path: Tuple[Union[str, int], ...],
        type_infos: Dict[Tuple[Union[str, int], ...], TypeInfo],
    ) -> Dict[Tuple[Union[str, int], ...], TypeInfo]:
        """Build type infos for a dataclass and its nested fields.

        Parameters
        ----------
        cls : Type
            The dataclass type to process.
        path : Tuple[Union[str, int], ...]
            The current path in the dataclass hierarchy.
        type_infos : Dict[Tuple[Union[str, int], ...], TypeInfo]
            Accumulator for type infos.

        Returns
        -------
        Dict[Tuple[Union[str, int], ...], TypeInfo]
            Updated type infos dictionary.
        """
        if not is_dataclass(cls):
            return type_infos

        for field in self._dataclass_cache[cls].values():
            field_path = path + (field.name,)
            type_infos[field_path] = field.type_info

            buckets = field.type_hint_buckets
            if TypeCategory.DATACLASS in buckets and len(buckets[TypeCategory.DATACLASS]) == 1:
                self.build_type_infos(
                    next(iter(buckets[TypeCategory.DATACLASS])), field_path, type_infos
                )

        return type_infos

    def serialize(self, obj: Any, type_info: Optional[TypeInfo] = None) -> Any:
        """Serialize an object.

        Parameters
        ----------
        obj : Any
            The object to serialize.
        type_info : Optional[TypeInfo]
            Optional type information for the object.

        Returns
        -------
        Any
            Serializable representation of the object.
        """

        if type_info and type_info.custom:
            return self.serialize(type_info.custom.reducer(obj))

        # Handle None
        if obj is None:
            return None

        # Handle primitives
        if isinstance(obj, (bool, int, float, str)):
            return obj

        if isinstance(obj, enum.Enum):
            return obj.name

        if obj is MISSING:
            return "MISSING"

        # Handle dataclass instances
        if is_dataclass(obj):
            result = {}
            for field in self.scan(type(obj)).values():
                if not field.init:
                    continue
                result[field.name] = self.serialize(
                    getattr(obj, field.name), type_info=field.type_info
                )
            return result

        # Handle containers
        if isinstance(obj, (dict, MappingProxyType)):
            return {k: self.serialize(v) for k, v in obj.items()}

        if isinstance(obj, (list, tuple)):
            return [self.serialize(item) for item in obj]

        if isinstance(obj, (set, frozenset)):
            return list(obj)

        # Handle custom types with reducer
        type_info = self.retrieve(type(obj))
        if type_info and type_info.custom:
            return self.serialize(type_info.custom.reducer(obj))

        return obj

    def serialize_defaults(self, cls: Type) -> Dict[str, Any]:
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
        for field in self.scan(cls).values():
            if field.default is not MISSING:
                defaults[field.name] = self.serialize(field.default, type_info=field.type_info)
            elif field.default_factory is not MISSING:
                defaults[field.name] = self.serialize(
                    field.default_factory(), type_info=field.type_info
                )
            else:
                buckets = field.type_hint_buckets
                if TypeCategory.DATACLASS in buckets and len(buckets[TypeCategory.DATACLASS]) == 1:
                    nested_cls = next(iter(buckets[TypeCategory.DATACLASS]))
                    defaults[field.name] = self.serialize_defaults(nested_cls)
                else:
                    defaults[field.name] = "MISSING"
        return defaults


# Global registry instance
_GLOBAL_TYPE_SYSTEM = TypeSystem()


def try_prune_type_chains(  # noqa: C901
    value: Any, type_chains: List[Tuple[TypeInfo, ...]]
) -> List[Tuple[TypeInfo, ...]]:
    """Prune type chains based on the actual value.

    This function narrows down the type chains based on the actual value
    provided. It tries to match the value against the type chains and
    returns only those that are applicable.

    Parameters
    ----------
    value : Any
        The actual value to check against.
    type_chains : List[Tuple[TypeInfo, ...]]
        The list of type chains to prune.

    Returns
    -------
    List[Tuple[TypeInfo, ...]]
        Pruned list of type chains that match the value.
    """
    if isinstance(value, dict):
        dict_chains: List[Tuple[TypeInfo, ...]] = []
        dataclass_chains: List[Tuple[TypeInfo, ...]] = []
        for chain in type_chains:
            type_ = chain[-1].type_
            if is_dataclass(type_):
                dataclass_chains.append(chain)
                dict_chains.append(chain)
            origin = get_origin(type_)
            if origin in _DICT_CONTAINER_TYPES or type_ in _RAW_DICT_CONTAINER_TYPES:
                dict_chains.append(chain)
        if len(dict_chains) == 1:
            return dict_chains
        if dataclass_chains:
            matches: List[Tuple[TypeInfo, ...]] = []
            for chain in dataclass_chains:
                cls = chain[-1].type_
                required_fields = {
                    f.name
                    for f in get_fields(cls, init_only=True)
                    if f.default is MISSING and f.default_factory is MISSING
                }
                if required_fields.issubset(value.keys()):
                    matches.append(chain)
            if matches:
                return matches
        if len(dict_chains) == len(dataclass_chains):
            return dict_chains
        return [chain for chain in dict_chains if not is_dataclass(chain[-1].type_)]
    elif isinstance(value, list):
        pruned = []
        for chain in type_chains:
            type_ = chain[-1].type_
            if get_origin(type_) in _LIST_CONTAINER_TYPES or type_ in _RAW_LIST_CONTAINER_TYPES:
                pruned.append(chain)
        return pruned
    else:
        # return all type chains that match the value's type
        pruned = []
        for chain in type_chains:
            type_ = chain[-1].type_
            if issubclass(type_, enum.Enum):
                # For enums, check if value is a member
                if isinstance(value, type_) or value in type_:
                    pruned.append(chain)
            elif isinstance(value, type_):
                pruned.append(chain)
        return pruned
