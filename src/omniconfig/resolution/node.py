"""Resolution tree node for OmniConfig."""

from dataclasses import _MISSING_TYPE, MISSING, dataclass, field, is_dataclass
from typing import Any, Dict, List, Sequence, Set, Tuple, Union

from ..core.exceptions import ConfigParseError, ConfigReferenceError
from ..core.reference import is_reference_format, path_to_reference
from ..core.types import _GLOBAL_TYPE_SYSTEM, TypeInfo, TypeSystem, try_prune_type_chains
from ..core.utils import get_fields

__all__ = ["ResolutionNode"]


@dataclass
class ResolutionNode:
    """Resolution node with separated structure and factoried value.

    This node maintains both the tree structure (content) and
    the factoried value separately, allowing for efficient resolution
    without data contamination.

    Attributes
    ----------
    content : Any | Dict[str, ResolutionNode] | List[ResolutionNode]
        The tree structure - primitives, dict of nodes, list of nodes.
    reference : str, default: ""
        The reference string if this node is a reference, else empty.
    value : Any, default: MISSING
        The factoried object (ConfigClass/CustomClass instance).
        Set after factory application.
    type_chains : List[Tuple[TypeInfo, ...]], default: []
        Possible type hint chains for this node.
    path : Tuple[Union[str, int], ...], default: ()
        The path to this node in the tree.
    name : str, init: False
        The full reference name for this node.
    aliases : List[str], default: set()
        List of name aliases for this node.
    resolved : str, init: False, default: ""
        The reference path this node was resolved from, if any.
    """

    content: Union[
        Union[bool, int, float, str, None],  # Primitives
        Dict[Union[str, int], "ResolutionNode"],  # Node tree for dicts
        List["ResolutionNode"],  # Node list for lists
    ]
    reference: str = ""

    value: Any = field(default_factory=lambda: MISSING)

    type_chains: List[Tuple[TypeInfo, ...]] = field(default_factory=list)

    path: Tuple[Union[str, int], ...] = ()
    name: str = field(init=False)
    aliases: Set[str] = field(default_factory=set)

    resolved: str = field(init=False, default="")

    def __post_init__(self):
        """Detect references."""
        self.name = path_to_reference(self.path)
        if not isinstance(self.reference, str):
            raise ConfigReferenceError(f"Reference must be a string, got {type(self.reference)}")
        if self.reference and not is_reference_format(self.reference):
            raise ConfigReferenceError(f"Invalid reference format: {self.reference}")
        if self.reference and self.reference.startswith(self.name):
            raise ConfigReferenceError(
                f"Reference '{self.reference}' cannot start with its own name '{self.name}'"
            )

    @property
    def is_root(self) -> bool:
        """Check if this node is the root node."""
        return not self.path

    @property
    def is_reference(self) -> bool:
        """Check if this node is a reference."""
        return bool(self.reference)

    @property
    def is_factoried(self) -> bool:
        """Check if this node has been factoried."""
        return self.value is not MISSING

    def matches_name(self, name: str) -> bool:
        """Check if this node matches a given name.

        Parameters
        ----------
        name : str
            The name to check against this node's name.

        Returns
        -------
        bool
            True if the names match, False otherwise.
        """
        return self.name == name or name in self.aliases

    def get_references(self) -> Set[str]:
        """Get all references from this node and descendants.

        Returns
        -------
        Set[str]
            Set of reference paths.
        """
        references = set()

        if self.reference:
            references.add(self.reference)

        # Recursively check children
        if isinstance(self.content, dict):
            for child in self.content.values():
                if isinstance(child, ResolutionNode):
                    references.update(child.get_references())
        elif isinstance(self.content, list):
            for child in self.content:
                if isinstance(child, ResolutionNode):
                    references.update(child.get_references())

        return references

    def resolve_reference(self, target_node: "ResolutionNode") -> "ResolutionNode":
        if not self.is_reference:
            raise ConfigReferenceError("Cannot resolve reference on a non-reference node.")
        if self.is_factoried:
            raise ConfigReferenceError(
                "Cannot resolve reference on a node that has already been factoried."
            )
        if not target_node.matches_name(self.reference):
            raise ConfigReferenceError(
                f"Target path '{target_node.path}' does not match"
                f" reference path '{self.reference}'"
            )
        if target_node.is_reference:
            raise ConfigReferenceError(
                "Cannot resolve reference to a target node that is also a reference."
            )
        if not isinstance(self.content, dict):
            # If this is a reference string node, return the target node
            target_node.aliases.add(self.name)
            return target_node
        if (
            len(self.content)
            - int("_reference_" in self.content)
            - int("_overwrite_" in self.content)
            <= 0
        ):
            # No updates to apply, just return the target node
            target_node.aliases.add(self.name)
            return target_node
        resolved = self.reference
        resolved_node = target_node.copy_with_update(update_node=self)
        if resolved_node is not target_node:
            resolved_node.resolved = resolved
        return resolved_node

    def copy_with_update(  # noqa: C901
        self: "ResolutionNode", update_node: "ResolutionNode"
    ) -> "ResolutionNode":  # noqa: C901
        if not isinstance(update_node.content, dict):
            if update_node.is_reference:
                raise ConfigReferenceError("Cannot apply a reference node as an update.")
            return update_node
        if (
            len(update_node.content)
            - int("_reference_" in update_node.content)
            - int("_overwrite_" in update_node.content)
            <= 0
        ):
            # This the lowest level update, just return the update node
            if update_node.is_reference:
                raise ConfigReferenceError("Cannot apply a reference node as an update.")
            return update_node
        if isinstance(self.content, dict):
            new_content = {}
            # First, process existing keys
            for key, value in self.content.items():
                if key in ("_reference_", "_overwrite_"):
                    continue
                if key not in update_node.content:
                    # Key not in original, shallow copy as is
                    value.aliases.add(path_to_reference(update_node.path + (key,)))
                    new_content[key] = value
                    continue
                new_content[key] = value.copy_with_update(update_node=update_node.content[key])
            # Add any keys from updates that don't exist in original
            for key, value in update_node.content.items():
                if key in ("_reference_", "_overwrite_"):
                    continue
                if key not in self.content:
                    new_content[key] = value
        elif isinstance(self.content, list):
            new_content = []
            # Process existing items
            for index, value in enumerate(self.content):
                key = index
                if key not in update_node.content:
                    key = str(index)
                    if key not in update_node.content:
                        # Key not in original, shallow copy as is
                        value.aliases.add(path_to_reference(update_node.path + (index,)))
                        new_content.append(value)
                        continue
                new_content.append(value.copy_with_update(update_node=update_node.content[key]))  # type: ignore
            start_index = len(new_content)
            # Add any items from updates that don't exist in original
            try:
                max_index = max(
                    int(k) for k in update_node.content if k not in ("_reference_", "_overwrite_")
                )
                for index in range(start_index, max_index + 1):
                    key = index
                    if key not in update_node.content:
                        key = str(index)
                        if key not in update_node.content:
                            raise KeyError  # TODO: better error message
                    new_content.append(update_node.content[key])  # type: ignore
            except:  # noqa: E722
                raise KeyError(f"Key {key} not found in node content") from None
        else:
            return update_node
        return ResolutionNode(
            content=new_content,
            value=MISSING,
            type_chains=update_node.type_chains,
            path=update_node.path,
            aliases=update_node.aliases,
        )

    def materialize(self, after_factory: bool = True) -> Any:
        """Materialize the node tree into a standard data structure.

        This is used to get the dict/list/primitive form for
        serialization or inspection.

        Returns
        -------
        Any
            The materialized data structure.
        """
        if after_factory and self.value is not MISSING:
            return self.value

        if isinstance(self.content, dict):
            content = {
                key: value.materialize(after_factory=after_factory)
                for key, value in self.content.items()
                if key not in ("_reference_", "_overwrite_")
            }
            if not after_factory and self.is_reference:
                content["_reference_"] = self.reference
            return content
        elif isinstance(self.content, list):
            return [value.materialize(after_factory=after_factory) for value in self.content]
        elif not after_factory and self.is_reference:
            return self.reference
        else:
            return self.content

    @staticmethod
    def build(  # noqa: C901
        data: Any,
        /,
        type_infos: Dict[Tuple[Union[str, int], ...], TypeInfo],
        path: Tuple[Union[str, int], ...] = (),
        parent_type_chains: Sequence[Tuple[TypeInfo, ...]] = (),
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
    ) -> "ResolutionNode":
        """Build a node tree with type hint propagation.

        Parameters
        ----------
        data : Dict[str, Any]
            The configuration data to build from.
        type_infos : Dict[Tuple[Union[str, int], ...], TypeInfo]
            Mapping of paths to type information for fields.
        path : Tuple[Union[str, int], ...], default: ()
            The current path in the tree (for recursion).
        parent_type_chains : Sequence[Tuple[TypeInfo, ...]], default: ()
            Type chains from the parent node
            (for type hint propagation).

        Returns
        -------
        ResolutionNode
            The root node of the tree.
        """
        # Check if this is a reference
        reference: str = ""
        if isinstance(data, str) and is_reference_format(data):
            reference = data
        elif isinstance(data, dict) and "_reference_" in data:
            reference = data["_reference_"]
            if not isinstance(reference, str) or not is_reference_format(reference):
                raise ConfigParseError(
                    f"Error building resolution node for path {path_to_reference(path)}:"
                    f" Invalid reference format: {reference}"
                )

        # Determine this node's type info
        if path in type_infos:
            # This is a field node with explicit type info
            type_chains = type_system.flatten(type_infos[path])
        elif parent_type_chains:
            # Try to extract element type from parent
            type_chains = []
            for parent_type_path in parent_type_chains:
                type_hint = type_system.extract_container_element_type(
                    parent_type_path[-1].type_hint, key=path[-1]
                )
                if type_hint is Any:
                    type_chains.append((TypeInfo(type_=Any),))
                else:
                    type_chains.extend(
                        type_system.flatten(
                            type_system.retrieve(type_hint, default=TypeInfo(type_=type_hint))
                        )
                    )
        else:
            # No type information available
            if path:
                raise ConfigParseError(
                    f"Error building resolution node for path {path_to_reference(path)}:"
                    " No type information available."
                )
            type_chains = []

        # Try to prune type chains for non-reference values
        if not bool(reference) and len(type_chains) > 1:
            type_chains = try_prune_type_chains(data, type_chains=type_chains)

        if isinstance(data, dict):
            # Build dict of nodes
            return ResolutionNode(
                content={
                    key: ResolutionNode.build(
                        value,
                        type_infos=type_infos,
                        path=path + (key,),
                        parent_type_chains=type_chains,
                    )
                    for key, value in data.items()
                    if key not in ("_reference_", "_overwrite_")
                },
                reference=reference,
                type_chains=type_chains,
                path=path,
            )

        elif isinstance(data, list):
            # Build list of nodes
            return ResolutionNode(
                content=[
                    ResolutionNode.build(
                        value,
                        type_infos=type_infos,
                        path=path + (i,),
                        parent_type_chains=type_chains,
                    )
                    for i, value in enumerate(data)
                ],
                reference=reference,
                type_chains=type_chains,
                path=path,
            )

        else:
            # Primitive
            return ResolutionNode(
                content=data,
                reference=reference,
                type_chains=type_chains,
                path=path,
            )

    def split(  # noqa: C901
        self, data: Any
    ) -> Tuple[Union[Any, _MISSING_TYPE], Union[Any, _MISSING_TYPE]]:
        """Extract unused data from this node.

        Parameters
        ----------
        data : Dict[str | int, Any]
            The original data to split into used and unused parts.

        Returns
        -------
        Tuple[Union[Any, _MISSING_TYPE], Union[Any, _MISSING_TYPE]]
            A tuple containing the used data and the unused data.
        """
        if not self.is_factoried:
            raise ConfigParseError("Cannot split used/unused data based on a non-factoried node.")
        if not isinstance(data, (dict, list)):
            return data, MISSING
        if is_dataclass(self.value):
            cls = type(self.value)
            if not isinstance(data, dict):
                raise ConfigParseError(
                    f"Expected dict data for {cls} at {self.name}, got {type(data)}"
                )
            unused_keys = {k for k in data.keys() if k not in ("_reference_", "_overwrite_")}
            if not unused_keys:
                return data, MISSING
            if not isinstance(self.content, dict):
                raise ConfigParseError(
                    f"Expected dict content for {cls} at {self.name}, got {type(self.content)}"
                )
            used, unused = {}, {}
            for field in get_fields(cls, init_only=True, exclude_pseudo=False):
                if field.name in data:
                    field_used, field_unused = self.content[field.name].split(
                        data=data[field.name]
                    )
                    if field_unused is MISSING:
                        unused_keys.discard(field.name)
                    else:
                        unused[field.name] = field_unused
                    if field_used is not MISSING:
                        used[field.name] = field_used
            for key in unused_keys:
                unused[key] = data[key]
            return used if used else MISSING, unused if unused else MISSING
        elif isinstance(self.value, dict):
            if not isinstance(data, dict):
                raise ConfigParseError(
                    f"Expected dict data for dict value at {self.name}, got {type(data)}"
                )
            keys = {k for k in data.keys() if k not in ("_reference_", "_overwrite_")}
            if not keys:
                return data, MISSING
            if not isinstance(self.content, dict):
                raise ConfigParseError(
                    f"Expected dict content for dict at {self.name}, got {type(self.content)}"
                )
            used, unused = {}, {}
            for key in keys:
                if key in self.content:
                    key_used, key_unused = self.content[key].split(data=data[key])
                    if key_unused is not MISSING:
                        unused[key] = key_unused
                    if key_used is not MISSING:
                        used[key] = key_used
                else:
                    unused[key] = data[key]
            return used if used else MISSING, unused if unused else MISSING
        elif isinstance(self.value, list):
            if not isinstance(self.content, list):
                raise ConfigParseError(
                    f"Expected list content for list at {self.name}, got {type(self.content)}"
                )
            if isinstance(data, dict):
                keys = {k for k in data.keys() if k not in ("_reference_", "_overwrite_")}
            elif isinstance(data, list):
                keys = set(range(len(data)))
            else:
                raise ConfigParseError(
                    f"Expected dict or list data for list at {self.name}, got {type(self.content)}"
                )
            if not keys:
                return data, MISSING
            used, unused = {}, {}
            for key in keys:
                if key < len(self.content):
                    key_used, key_unused = self.content[key].split(data=data[key])  # type: ignore
                    if key_unused is not MISSING:
                        unused[key] = key_unused
                    if key_used is not MISSING:
                        used[key] = key_used
                else:
                    unused[key] = data[key]
            if isinstance(data, list):
                if all(key in used for key in keys):
                    used = [used[key] for key in range(len(data))]
                if all(key in unused for key in keys):
                    unused = [unused[key] for key in range(len(data))]
            return used if used else MISSING, unused if unused else MISSING
        else:
            return data, MISSING
