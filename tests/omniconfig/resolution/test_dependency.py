"""Tests for DependencyGraph implementation."""

import pytest

from omniconfig.core.exceptions import (
    CircularReferenceError,
    ConfigParseError,
    ConfigReferenceError,
)
from omniconfig.resolution.dependency import DependencyGraph
from omniconfig.resolution.node import ResolutionNode


class TestDependencyGraphConstruction:
    """Test DependencyGraph construction and node collection."""

    def test_simple_graph(self):
        """Test building graph from simple node tree."""
        child1 = ResolutionNode(content="v1", path=("root", "c1"))
        child2 = ResolutionNode(content="v2", path=("root", "c2"))
        root = ResolutionNode(content={"c1": child1, "c2": child2}, path=("root",))

        graph = DependencyGraph(root)

        assert "::root" in graph.nodes
        assert "::root::c1" in graph.nodes
        assert "::root::c2" in graph.nodes
        assert len(graph.nodes) == 3

    def test_nested_graph(self):
        """Test building graph from nested structure."""
        grandchild = ResolutionNode(content="deep", path=("root", "child", "grand"))
        child = ResolutionNode(content={"grand": grandchild}, path=("root", "child"))
        root = ResolutionNode(content={"child": child}, path=("root",))

        graph = DependencyGraph(root)

        assert "::root" in graph.nodes
        assert "::root::child" in graph.nodes
        assert "::root::child::grand" in graph.nodes
        assert len(graph.nodes) == 3

    def test_list_nodes(self):
        """Test graph with list nodes."""
        item1 = ResolutionNode(content="first", path=("items", 0))
        item2 = ResolutionNode(content="second", path=("items", 1))
        items = ResolutionNode(content=[item1, item2], path=("items",))

        graph = DependencyGraph(items)

        assert "::items" in graph.nodes
        assert "::items::0" in graph.nodes
        assert "::items::1" in graph.nodes
        assert len(graph.nodes) == 3

    def test_path_name_mapping(self):
        """Test path to name mapping."""
        child = ResolutionNode(content="value", path=("parent", "child"))
        parent = ResolutionNode(content={"child": child}, path=("parent",))

        graph = DependencyGraph(parent)

        assert graph.names[("parent",)] == "::parent"
        assert graph.names[("parent", "child")] == "::parent::child"

    def test_duplicate_node_error(self):
        """Test that duplicate nodes raise error."""
        # Create two different node objects with same path
        child1 = ResolutionNode(content="v1", path=("root", "dup"))
        child2 = ResolutionNode(content="v2", path=("root", "dup"))
        root = ResolutionNode(content={"dup": child1, "dup2": child2}, path=("root",))

        # Manually set duplicate path
        child2.path = ("root", "dup")
        child2.name = "::root::dup"

        with pytest.raises(ConfigParseError, match="Duplicate node found"):
            DependencyGraph(root)


class TestDependencyRelationships:
    """Test dependency relationship building."""

    def test_factory_dependencies(self):
        """Test factory dependencies (parent depends on children)."""
        child1 = ResolutionNode(content="v1", path=("root", "c1"))
        child2 = ResolutionNode(content="v2", path=("root", "c2"))
        root = ResolutionNode(content={"c1": child1, "c2": child2}, path=("root",))

        graph = DependencyGraph(root)

        # Root depends on its children
        assert "::root::c1" in graph.dependencies["::root"]
        assert "::root::c2" in graph.dependencies["::root"]

        # Children have root as dependent
        assert "::root" in graph.dependents["::root::c1"]
        assert "::root" in graph.dependents["::root::c2"]

    def test_reference_dependencies(self):
        """Test reference dependencies."""
        target = ResolutionNode(content="target", path=("shared",))
        ref_node = ResolutionNode(content="ref", reference="::shared", path=("myref",))
        root = ResolutionNode(content={"shared": target, "myref": ref_node}, path=())

        graph = DependencyGraph(root)

        # Reference node depends on its target
        assert "::shared" in graph.dependencies["::myref"]
        assert "::myref" in graph.dependents["::shared"]

    def test_nested_dependencies(self):
        """Test nested dependency chains."""
        gc1 = ResolutionNode(content="gc1", path=("root", "child", "gc1"))
        gc2 = ResolutionNode(content="gc2", path=("root", "child", "gc2"))
        child = ResolutionNode(content={"gc1": gc1, "gc2": gc2}, path=("root", "child"))
        root = ResolutionNode(content={"child": child}, path=("root",))

        graph = DependencyGraph(root)

        # Check transitive dependencies
        assert "::root::child" in graph.dependencies["::root"]
        assert "::root::child::gc1" in graph.dependencies["::root::child"]
        assert "::root::child::gc2" in graph.dependencies["::root::child"]

    def test_list_dependencies(self):
        """Test dependencies with list nodes."""
        item1 = ResolutionNode(content="first", path=("items", 0))
        item2 = ResolutionNode(content="second", path=("items", 1))
        items = ResolutionNode(content=[item1, item2], path=("items",))

        graph = DependencyGraph(items)

        # List node depends on its items
        assert "::items::0" in graph.dependencies["::items"]
        assert "::items::1" in graph.dependencies["::items"]

    def test_missing_reference_target(self):
        """Test error when reference target doesn't exist."""
        ref_node = ResolutionNode(content="ref", reference="::nonexistent", path=("myref",))
        root = ResolutionNode(content={"myref": ref_node}, path=())

        with pytest.raises(ConfigReferenceError, match="does not exist"):
            DependencyGraph(root)


class TestTopologicalSorting:
    """Test topological sorting and resolution order."""

    def test_simple_topological_order(self):
        """Test simple topological ordering."""
        child1 = ResolutionNode(content="v1", path=("root", "c1"))
        child2 = ResolutionNode(content="v2", path=("root", "c2"))
        root = ResolutionNode(content={"c1": child1, "c2": child2}, path=("root",))

        graph = DependencyGraph(root)

        # Children should come before parent in queue
        queue_names = []
        for item in graph.queue:
            if isinstance(item, tuple):
                queue_names.append(item[0].name)
            else:
                queue_names.append(item.name)

        c1_idx = queue_names.index("::root::c1")
        c2_idx = queue_names.index("::root::c2")
        root_idx = queue_names.index("::root")

        assert c1_idx < root_idx
        assert c2_idx < root_idx

    def test_reference_resolution_order(self):
        """Test resolution order with references."""
        target = ResolutionNode(content="target", path=("shared",))
        ref1 = ResolutionNode(content="r1", reference="::shared", path=("ref1",))
        ref2 = ResolutionNode(content="r2", reference="::shared", path=("ref2",))
        root = ResolutionNode(content={"shared": target, "ref1": ref1, "ref2": ref2}, path=())

        graph = DependencyGraph(root)

        # Target should be processed before references
        queue_names = []
        for item in graph.queue:
            if isinstance(item, tuple):
                queue_names.append(item[0].name)
            else:
                queue_names.append(item.name)

        shared_idx = queue_names.index("::shared")
        ref1_idx = queue_names.index("::ref1")
        ref2_idx = queue_names.index("::ref2")

        assert shared_idx < ref1_idx
        assert shared_idx < ref2_idx

    def test_complex_dependencies(self):
        """Test complex dependency graph."""
        # Create a diamond dependency pattern
        #    root
        #   /    \
        #  b1    b2
        #   \    /
        #     c
        c = ResolutionNode(content="c", path=("root", "c"))
        b1 = ResolutionNode(content={"c_ref": c}, path=("root", "b1"))
        b2 = ResolutionNode(content={"c_ref": c}, path=("root", "b2"))
        root = ResolutionNode(content={"b1": b1, "b2": b2, "c": c}, path=("root",))

        graph = DependencyGraph(root)

        # c should be processed first, then b1 and b2, then root
        queue_names = []
        for item in graph.queue:
            if isinstance(item, tuple):
                queue_names.append(item[0].name)
            else:
                queue_names.append(item.name)

        c_idx = queue_names.index("::root::c")
        b1_idx = queue_names.index("::root::b1")
        b2_idx = queue_names.index("::root::b2")
        root_idx = queue_names.index("::root")

        assert c_idx < b1_idx
        assert c_idx < b2_idx
        assert b1_idx < root_idx
        assert b2_idx < root_idx


class TestCycleDetection:
    """Test circular dependency detection."""

    def test_simple_cycle(self):
        """Test simple circular reference."""
        ref1 = ResolutionNode(content="r1", reference="::ref2", path=("ref1",))
        ref2 = ResolutionNode(content="r2", reference="::ref1", path=("ref2",))
        root = ResolutionNode(content={"ref1": ref1, "ref2": ref2}, path=())

        with pytest.raises(CircularReferenceError, match="Circular dependency detected"):
            DependencyGraph(root)

    def test_self_reference(self):
        """Test self-referencing node."""
        # Note: This should already be caught in node creation,
        # but test graph handling
        ref = ResolutionNode(content="self", reference="::other", path=("test",))
        # Manually set self-reference after creation
        # to bypass node validation
        ref.reference = "::test"
        root = ResolutionNode(content={"test": ref}, path=())

        with pytest.raises(CircularReferenceError, match="Circular"):
            DependencyGraph(root)

    def test_three_node_cycle(self):
        """Test three-node circular dependency."""
        ref1 = ResolutionNode(content="r1", reference="::ref2", path=("ref1",))
        ref2 = ResolutionNode(content="r2", reference="::ref3", path=("ref2",))
        ref3 = ResolutionNode(content="r3", reference="::ref1", path=("ref3",))
        root = ResolutionNode(content={"ref1": ref1, "ref2": ref2, "ref3": ref3}, path=())

        with pytest.raises(CircularReferenceError) as exc_info:
            DependencyGraph(root)

        # Should detect and report the cycle
        assert "Circular" in str(exc_info.value)

    def test_indirect_cycle(self):
        """Test indirect circular dependency through nested structs."""
        # Create a struct where a parent references a child's descendant
        grandchild = ResolutionNode(
            content="gc", reference="::parent", path=("parent", "child", "gc")
        )
        child = ResolutionNode(content={"gc": grandchild}, path=("parent", "child"))
        parent = ResolutionNode(content={"child": child}, path=("parent",))
        root = ResolutionNode(content={"parent": parent}, path=())

        with pytest.raises(CircularReferenceError):
            DependencyGraph(root)

    def test_no_cycle_complex(self):
        """Test complex graph without cycles."""
        # Create complex but acyclic graph
        shared = ResolutionNode(content="shared", path=("shared",))
        ref1 = ResolutionNode(content="r1", reference="::shared", path=("ref1",))
        ref2 = ResolutionNode(content="r2", reference="::shared", path=("ref2",))
        ref3 = ResolutionNode(content="r3", reference="::ref1", path=("ref3",))
        root = ResolutionNode(
            content={"shared": shared, "ref1": ref1, "ref2": ref2, "ref3": ref3}, path=()
        )

        # Should not raise error
        graph = DependencyGraph(root)
        assert len(graph.queue) > 0

    def test_cycle_path_finding(self):
        """Test that cycle detection finds the actual cycle path."""
        ref1 = ResolutionNode(content="r1", reference="::b", path=("a",))
        ref2 = ResolutionNode(content="r2", reference="::c", path=("b",))
        ref3 = ResolutionNode(content="r3", reference="::a", path=("c",))
        root = ResolutionNode(content={"a": ref1, "b": ref2, "c": ref3}, path=())

        with pytest.raises(CircularReferenceError) as exc_info:
            DependencyGraph(root)

        error_msg = str(exc_info.value)
        # Should mention the nodes involved
        assert "::a" in error_msg or "::b" in error_msg or "::c" in error_msg


class TestNodeManagement:
    """Test node management operations."""

    def test_set_node_in_dict(self):
        """Test setting a node in dict parent."""
        child1 = ResolutionNode(content="v1", path=("root", "c1"))
        child2 = ResolutionNode(content="v2", path=("root", "c2"))
        root = ResolutionNode(content={"c1": child1, "c2": child2}, path=("root",))

        graph = DependencyGraph(root)

        # Create new node and set it
        new_node = ResolutionNode(content="new", path=("root", "c1"))
        graph.set_node(("root", "c1"), new_node)

        assert graph.nodes["::root::c1"] is new_node
        assert isinstance(root.content, dict)
        assert root.content["c1"] is new_node

    def test_set_node_in_list(self):
        """Test setting a node in list parent."""
        item1 = ResolutionNode(content="first", path=("items", 0))
        item2 = ResolutionNode(content="second", path=("items", 1))
        items = ResolutionNode(content=[item1, item2], path=("items",))

        graph = DependencyGraph(items)

        # Create new node and set it
        new_node = ResolutionNode(content="updated", path=("items", 0))
        graph.set_node(("items", 0), new_node)

        assert graph.nodes["::items::0"] is new_node
        assert isinstance(items.content, list)
        assert items.content[0] is new_node

    def test_set_node_invalid_path(self):
        """Test setting node with invalid path."""
        root = ResolutionNode(
            content={"child": ResolutionNode(content="v", path=("root", "child"))}, path=("root",)
        )
        graph = DependencyGraph(root)

        with pytest.raises(KeyError, match="does not exist"):
            graph.set_node(
                ("invalid", "path"), ResolutionNode(content="x", path=("invalid", "path"))
            )


class TestDependencyGraphIntegration:
    """Integration tests for DependencyGraph."""

    def test_large_graph(self):
        """Test with large graph structure."""
        # Create a tree with many nodes
        nodes = {}
        for i in range(10):
            for j in range(5):
                path = ("root", f"level1_{i}", f"level2_{j}")
                nodes[f"l1_{i}_l2_{j}"] = ResolutionNode(content=f"v_{i}_{j}", path=path)

        # Build level 1 nodes
        level1_nodes = {}
        for i in range(10):
            level1_nodes[f"level1_{i}"] = ResolutionNode(
                content={f"level2_{j}": nodes[f"l1_{i}_l2_{j}"] for j in range(5)},
                path=("root", f"level1_{i}"),
            )

        # Build root
        root = ResolutionNode(content=level1_nodes, path=("root",))

        graph = DependencyGraph(root)

        # Should have 1 root + 10 level1 + 50 level2 = 61 nodes
        assert len(graph.nodes) == 61

        # All nodes should be in topological order
        assert len(graph.queue) == 61

    def test_mixed_references_and_structures(self):
        """Test graph with mixed references and nested structures."""
        # Create base configs
        base1 = ResolutionNode(
            content={"param": ResolutionNode(content="base1", path=("bases", "base1", "param"))},
            path=("bases", "base1"),
        )
        base2 = ResolutionNode(
            content={"param": ResolutionNode(content="base2", path=("bases", "base2", "param"))},
            path=("bases", "base2"),
        )

        # Create references to bases
        ref1 = ResolutionNode(content="r1", reference="::bases::base1", path=("configs", "ref1"))
        ref2 = ResolutionNode(content="r2", reference="::bases::base2", path=("configs", "ref2"))

        # Create nested structure with references
        nested_ref = ResolutionNode(
            content="nr", reference="::configs::ref1", path=("configs", "nested", "ref")
        )
        nested = ResolutionNode(content={"ref": nested_ref}, path=("configs", "nested"))

        # Build structure
        bases = ResolutionNode(content={"base1": base1, "base2": base2}, path=("bases",))
        configs = ResolutionNode(
            content={"ref1": ref1, "ref2": ref2, "nested": nested}, path=("configs",)
        )
        root = ResolutionNode(content={"bases": bases, "configs": configs}, path=())

        graph = DependencyGraph(root)

        # Verify all nodes are collected
        assert len(graph.nodes) == 11

        # Verify resolution order
        queue_names = []
        for item in graph.queue:
            if isinstance(item, tuple):
                queue_names.append(item[0].name)
            else:
                queue_names.append(item.name)

        # Bases should come before their references
        base1_idx = queue_names.index("::bases::base1")
        ref1_idx = queue_names.index("::configs::ref1")
        assert base1_idx < ref1_idx

        # ref1 should come before nested_ref
        nested_ref_idx = queue_names.index("::configs::nested::ref")
        assert ref1_idx < nested_ref_idx
