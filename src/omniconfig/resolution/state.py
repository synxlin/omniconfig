"""Resolution state management using node-based architecture.

This module provides the central state manager for the resolution
using the dependency graph with topological sorting.
"""

from typing import Any, Dict, List, Type

from ..core.types import _GLOBAL_TYPE_SYSTEM, TypeInfo, TypeSystem
from .dependency import DependencyGraph
from .factory import FactorySystem
from .node import ResolutionNode

__all__ = ["ResolutionState"]


class ResolutionState:
    """Central state manager for configuration resolution.

    This class manages the resolution process using a pre-computed
    topological order from the dependency graph.

    Attributes
    ----------
    root : ResolutionNode
        The root node of the configuration tree.
    graph : DependencyGraph
        Dependency graph with pre-computed resolution order.
    """

    def __init__(
        self,
        data: Dict[str, Any],
        configs: Dict[str, Type],
        type_system: TypeSystem = _GLOBAL_TYPE_SYSTEM,
    ):
        """Initialize resolution state with optimized dependency graph.

        Parameters
        ----------
        data : Dict[str, Any]
            Initial configuration data.
        configs : Dict[str, Type]
            Registered configclass types by scope.
        type_system : TypeSystem
            Type system for type information and validation.

        Raises
        ------
        CircularReferenceError
            If circular dependencies are detected during graph building.
        """
        for config in configs.values():
            type_system.scan(config)
        self._configs = configs
        self._type_system = type_system

        # Build complete type hints from registered configs
        self._type_infos = {}
        for scope, config in self._configs.items():
            self._type_infos[(scope,)] = TypeInfo(type_=config)
            self._type_system.build_type_infos(config, path=(scope,), type_infos=self._type_infos)

        # Build the node tree with type infos
        self.root = ResolutionNode.build(
            data, type_infos=self._type_infos, type_system=self._type_system
        )

        # Build dependency graph with topological sorting
        # This will raise CircularReferenceError if cycles are detected
        self.graph = DependencyGraph(self.root)

    def get_resolution_queue(self) -> List[ResolutionNode]:
        """Get the pre-computed resolution order.

        Returns
        -------
        List[ResolutionNode]
            A list containing nodes in topological order for processing.
        """
        return self.graph.queue

    def apply_factory(self, node: ResolutionNode) -> None:
        """Apply factory to a node.

        Parameters
        ----------
        node : ResolutionNode
            The node to apply the factory to.
        """
        FactorySystem.apply(node=node)

    def resolve_reference(self, node: ResolutionNode) -> None:
        """Resolve a reference node.

        Parameters
        ----------
        node : ResolutionNode
            The node to update with the resolved reference.
        """
        path = node.path
        resolved_node = node.resolve_reference(target_node=self.graph.nodes[node.reference])
        self.apply_factory(node=resolved_node)
        self.graph.set_node(path=path, node=resolved_node)
