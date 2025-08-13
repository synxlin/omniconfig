"""Dependency graph management for node-based resolution.

This module provides dependency tracking and resolution ordering
using a unified dependency graph with topological sorting.
"""

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple, Union

from ..core.exceptions import CircularReferenceError, ConfigParseError, ConfigReferenceError
from .node import ResolutionNode

__all__ = ["DependencyGraph"]


class DependencyGraph:
    """Unified dependency graph for efficient resolution.

    This class builds a complete dependency graph capturing both
    reference dependencies and factory dependencies, then computes
    a topological order for processing nodes.

    Attributes
    ----------
    nodes : Dict[str, ResolutionNode]
        Mapping from node name to ResolutionNode.
    dependencies : Dict[str, Set[str]]
        Adjacency list representation of dependencies.
        If A depends on B, then dependencies[A] contains B.
    dependents : Dict[str, Set[str]]
        Reverse adjacency list.
        If A depends on B, then dependents[B] contains A.
    queue : List[ResolutionNode]
        Topologically sorted list of nodes to process.
    """

    def __init__(self, root: ResolutionNode):
        """Initialize dependency graph with topological sorting.

        Parameters
        ----------
        root : ResolutionNode
            The root node of the tree.

        Raises
        ------
        CircularReferenceError
            If circular dependencies are detected.
        """
        self.names: Dict[Tuple[Union[str, int], ...], str] = {}
        self.nodes: Dict[str, ResolutionNode] = {}
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.dependents: Dict[str, Set[str]] = defaultdict(set)
        self.queue: List[ResolutionNode] = []

        # Build the complete graph
        self._collect_nodes(root)
        self._build_unified_dependencies()
        self._compute_topological_order()

    def _collect_nodes(self, node: ResolutionNode) -> None:
        """Recursively collect all nodes in the tree.

        Parameters
        ----------
        node : ResolutionNode
            Current node being processed.
        """
        if node.name in self.nodes:
            exist_node = self.nodes[node.name]
            if exist_node is not node:  # Allow same node object
                raise ConfigParseError(
                    f"Error adding node {node.name}: Duplicate node found"
                    f" for path '{node.path}' and '{exist_node.path}'"
                )
            return  # Already processed this node

        # Add this node
        self.names[node.path] = node.name
        self.nodes[node.name] = node

        # Recurse into children
        if isinstance(node.content, dict):
            for child in node.content.values():
                if isinstance(child, ResolutionNode):
                    self._collect_nodes(child)
        elif isinstance(node.content, list):
            for child in node.content:
                if isinstance(child, ResolutionNode):
                    self._collect_nodes(child)

    def _build_unified_dependencies(self) -> None:
        """Build unified dependency graph with both reference and
        factory dependencies.
        """
        for node_name, node in self.nodes.items():
            # Add reference dependencies
            # A node depends on its reference target being resolved
            if node.is_reference:
                self._add_dependency(node_name, node.reference)
            # Add factory dependencies
            # Parent depends on child being factoried
            if isinstance(node.content, dict):
                for child in node.content.values():
                    self._add_dependency(node_name, child.name)
            elif isinstance(node.content, list):
                for child in node.content:
                    self._add_dependency(node_name, child.name)

    def _add_dependency(self, dependent: str, dependency: str) -> None:
        """Add a dependency edge to the graph.

        Parameters
        ----------
        dependent : str
            The node that depends on another.
        dependency : str
            The node being depended upon.
        """
        # Skip if dependency doesn't exist (e.g., external reference)
        if dependency not in self.nodes:
            raise ConfigReferenceError(
                f"Dependency '{dependency}' does not exist for node '{dependent}'"
            )
        # Add to adjacency lists
        self.dependencies[dependent].add(dependency)
        self.dependents[dependency].add(dependent)

    def _compute_topological_order(self) -> None:
        """Compute topological order using Kahn's algorithm.

        This determines the exact order in which nodes should
        be processed, ensuring all dependencies are satisfied.

        Raises
        ------
        CircularReferenceError
            If circular dependencies are detected.
        """
        # Calculate initial in-degrees
        in_degree = {}
        for node_name in self.nodes:
            in_degree[node_name] = len(self.dependencies.get(node_name, set()))

        # Find all nodes with no dependencies
        queue = deque()
        for node_name, degree in in_degree.items():
            if degree == 0:
                queue.append(node_name)

        # Process nodes in topological order
        processed = []
        while queue:
            node_name = queue.popleft()
            processed.append(node_name)

            # Update in-degrees of dependent nodes
            for dependent in self.dependents.get(node_name, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycles
        if len(processed) != len(self.nodes):
            # Find nodes involved in cycles
            unprocessed = set(self.nodes.keys()) - set(processed)
            cycle = self._find_cycle(unprocessed)
            if cycle:
                raise CircularReferenceError(f"Circular dependency detected: {' → '.join(cycle)}")
            else:
                raise CircularReferenceError(
                    f"Circular dependencies detected involving nodes: {unprocessed}"
                )

        # Build resolution order
        self.queue = []
        for node_name in processed:
            self.queue.append(self.nodes[node_name])

    def _find_cycle(self, nodes: Set[str]) -> Optional[List[str]]:
        """Find a cycle in the given set of nodes using DFS.

        Parameters
        ----------
        nodes : Set[str]
            Set of nodes to search for cycles.

        Returns
        -------
        Optional[List[str]]
            List of node names forming a cycle,
            or None if no cycle found.
        """
        visited = set()
        rec_stack = []
        rec_stack_set = set()

        def dfs(node_name: str) -> Optional[List[str]]:
            if node_name in rec_stack_set:
                # Found a cycle
                idx = rec_stack.index(node_name)
                return rec_stack[idx:] + [node_name]

            if node_name in visited:
                return None

            visited.add(node_name)
            rec_stack.append(node_name)
            rec_stack_set.add(node_name)

            # Visit dependencies
            for dep in self.dependencies.get(node_name, set()):
                if dep in nodes:  # Only consider nodes in the given set
                    cycle = dfs(dep)
                    if cycle:
                        return cycle

            rec_stack.pop()
            rec_stack_set.remove(node_name)
            return None

        # Try to find a cycle starting from any unvisited node
        for node_name in nodes:
            if node_name not in visited:
                cycle = dfs(node_name)
                if cycle:
                    return cycle

        return None

    def set_node(self, path: Tuple[Union[str, int], ...], node: ResolutionNode) -> None:
        """Set a node at a specific path.

        Parameters
        ----------
        path : Tuple[Union[str, int], ...]
            Path where the node should be set.
        node : ResolutionNode
            The node to set.
        """
        if path not in self.names:
            raise KeyError(f"Node path {path} does not exist in the graph")
        name = self.names[path]
        parent_path, field_name = path[:-1], path[-1]
        if parent_path not in self.names:
            raise KeyError(f"Parent path {parent_path} does not exist in the graph")
        parent = self.nodes[self.names[parent_path]]

        self.nodes[name] = node
        if isinstance(parent.content, dict):
            parent.content[field_name] = node
        elif isinstance(parent.content, list):
            parent.content[int(field_name)] = node
